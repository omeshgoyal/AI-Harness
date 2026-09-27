import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import config

PROJECT = config.WORKSPACE_DIR
PROJECT.mkdir(parents=True, exist_ok=True)
HARNESS = config.HARNESS_DIR

PROFILE = f"""(version 1)
(deny default)
(allow process-exec process-fork signal)
(allow file-read*)
(deny file-read* (subpath "{HARNESS}"))
(allow sysctl-read)
(deny network*)
(allow file-write* (subpath "{PROJECT}") (literal "/dev/null"))
(deny file-write* (subpath "{PROJECT}/.git/hooks"))
(deny file-write* (subpath "{HARNESS}"))
"""

_SECRET_NAME_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "_PAT", "AUTH")

DOCKER_IMAGE = os.getenv("AGENT_DOCKER_IMAGE", "python:3.12-slim")

_warned = False


def safe_env():
    return {k: v for k, v in os.environ.items() if not any(hint in k.upper() for hint in _SECRET_NAME_HINTS)}


def _bwrap_hooks_args():
    hooks = PROJECT / ".git" / "hooks"
    if hooks.is_dir():
        return ["--ro-bind", str(hooks), str(hooks)]
    return []


def wrap(command):
    if sys.platform == "darwin":
        profile = Path(tempfile.gettempdir()) / "neuralcode.sb"
        profile.write_text(PROFILE)
        return ["sandbox-exec", "-f", str(profile), "/bin/sh", "-c", command]

    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        return [
            "bwrap",
            "--ro-bind", "/", "/",
            "--bind", str(PROJECT), str(PROJECT),
            "--tmpfs", str(HARNESS),  # Hide the harness directory inside the container!
            *_bwrap_hooks_args(),
            "--dev", "/dev", "--proc", "/proc",
            "--unshare-net", "--die-with-parent",
            "--chdir", str(PROJECT),
            "/bin/sh", "-c", command,
        ]

    return None


def _docker_wrap(command):
    if not shutil.which("docker"):
        return None
    return [
        "docker", "run", "--rm", "-i",
        "--network", "none",
        "--memory", "512m", "--pids-limit", "256",
        "-v", f"{PROJECT}:{PROJECT}",
        # Do not mount HARNESS
        "-w", str(PROJECT),
        DOCKER_IMAGE, "/bin/sh", "-c", command,
    ]


def name():
    if sys.platform == "darwin":
        return "seatbelt"
    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        return "bubblewrap"
    if shutil.which("docker"):
        return "docker (fallback)"
    return "none"


def run(command, timeout=60):
    global _warned
    env = safe_env()

    sandboxed = wrap(command)
    if sandboxed is None:
        sandboxed = _docker_wrap(command)

    if sandboxed is None and not _warned:
        _warned = True
        try:
            from rich.console import Console
            Console().print("[bold red]No sandbox available.[/bold red]")
        except Exception:
            print(f"WARNING: no sandbox available on {sys.platform}")

    return subprocess.run(
        sandboxed or command,
        shell=sandboxed is None,
        cwd=PROJECT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
