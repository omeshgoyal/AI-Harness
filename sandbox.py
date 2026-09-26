import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path.cwd().resolve()

# Seatbelt (macOS). Writes are allowed anywhere under the project - including
# .git, which git add/commit/checkout/stash all need to update (index,
# objects, refs, HEAD) - but NOT .git/hooks, which is executable code that
# would otherwise let a single approved write persist arbitrary behaviour
# into every future git command run in this repo.
PROFILE = f"""(version 1)
(deny default)
(allow process-exec process-fork signal)
(allow file-read*)
(allow sysctl-read)
(deny network*)
(allow file-write* (subpath "{PROJECT}") (literal "/dev/null"))
(deny file-write* (subpath "{PROJECT}/.git/hooks"))
"""

# Env vars whose *name* contains one of these are stripped before a sandboxed
# (or unsandboxed-fallback) command runs, so a shell command the user approved
# can't exfiltrate the harness's own LLM/API credentials via `env`, a stray
# `curl -d "$OPENROUTER_API_KEY"`, or similar. Broad substring match on
# purpose - false positives (dropping a var a build script wanted) are a lot
# cheaper than the alternative.
_SECRET_NAME_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "_PAT", "AUTH")

DOCKER_IMAGE = os.getenv("AGENT_DOCKER_IMAGE", "python:3.12-slim")

_warned = False


def safe_env():
    """The environment a sandboxed command should see: everything except
    anything that looks like a secret belonging to this harness."""
    return {k: v for k, v in os.environ.items() if not any(hint in k.upper() for hint in _SECRET_NAME_HINTS)}


def _bwrap_hooks_args():
    """Re-bind .git/hooks read-only, after the project is bound read-write,
    so bubblewrap gives Linux the same hook protection seatbelt gives macOS."""
    hooks = PROJECT / ".git" / "hooks"
    if hooks.is_dir():
        return ["--ro-bind", str(hooks), str(hooks)]
    return []


def wrap(command):
    """Wrap a shell command in an OS sandbox. None means we have no native sandbox
    (the caller falls back to Docker if available, else runs unconfined)."""
    if sys.platform == "darwin":
        profile = Path(tempfile.gettempdir()) / "neuralcode.sb"
        profile.write_text(PROFILE)
        return ["sandbox-exec", "-f", str(profile), "/bin/sh", "-c", command]

    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        return [
            "bwrap",
            "--ro-bind", "/", "/",
            "--bind", str(PROJECT), str(PROJECT),
            *_bwrap_hooks_args(),
            "--dev", "/dev", "--proc", "/proc",
            "--unshare-net", "--die-with-parent",
            "/bin/sh", "-c", command,
        ]

    return None


def _docker_wrap(command):
    """Best-effort fallback for platforms with no native sandbox (Windows, or
    Linux without bubblewrap installed). Runs the command in a throwaway
    container with the project bind-mounted and networking disabled.

    This is meaningfully weaker than seatbelt/bwrap in one way and stronger in
    another: it can't protect .git/hooks selectively (the whole project is
    mounted read-write), but it fully isolates the filesystem outside the
    project and the host's environment/processes, which an unconfined
    subprocess.run has zero protection against. It also means commands
    needing tools not in DOCKER_IMAGE (default python:3.12-slim) will fail -
    set AGENT_DOCKER_IMAGE to something with git/node/etc. preinstalled if
    your project needs them.
    """
    if not shutil.which("docker"):
        return None
    return [
        "docker", "run", "--rm", "-i",
        "--network", "none",
        "--memory", "512m", "--pids-limit", "256",
        "-v", f"{PROJECT}:{PROJECT}",
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
    """Run a command, sandboxed when the OS lets us, with secrets stripped
    from its environment either way."""
    global _warned
    env = safe_env()

    sandboxed = wrap(command)
    if sandboxed is None:
        sandboxed = _docker_wrap(command)

    if sandboxed is None and not _warned:
        _warned = True
        try:
            from rich.console import Console
            Console().print(
                "[bold red]No sandbox available on this platform "
                f"({sys.platform}) - shell commands run with only the "
                "permissions table protecting the filesystem. Install "
                "bubblewrap (Linux) or Docker for real isolation.[/bold red]"
            )
        except Exception:
            print(f"WARNING: no sandbox available on {sys.platform}; commands run unconfined.")

    return subprocess.run(
        sandboxed or command,
        shell=sandboxed is None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )