import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from todos import todos_prompt

LABELS = {"M": "modified", "D": "deleted", "A": "added", "??": "new", "R": "renamed"}
HASH_SIZE_LIMIT = 5_000_000  # don't hash huge files every turn just to watch for edits


def git(command):
    try:
        result = subprocess.run(
            ["bash", "-c", f"git {command}"], capture_output=True, text=True
        )
        return result.stdout  # stderr (e.g. "not a git repo") is swallowed on purpose
    except Exception:
        return ""


def file_hash(path):
    file = Path(path)
    try:
        if not file.is_file() or file.stat().st_size > HASH_SIZE_LIMIT:
            return None
        return hashlib.md5(file.read_bytes()).hexdigest()
    except Exception:
        return None


def _parse_porcelain_line(line):
    """Return (code, path) for one `git status --porcelain` line, handling renames
    ('R  old -> new') where a naive line[3:] split would keep the arrow and old path."""
    if len(line) < 3:
        return None, None
    code = line[:2].strip()
    rest = line[3:]
    if code.startswith("R") and " -> " in rest:
        rest = rest.split(" -> ", 1)[1]
    return code, rest.strip('"')  # git quotes paths containing unusual characters


def git_state():
    state = {}
    status_output = git("status --porcelain")
    if not status_output:
        return state

    for line in status_output.splitlines():
        code, path = _parse_porcelain_line(line)
        if not path:
            continue
        state[path] = (code, file_hash(path))
    return state


LAST_STATE = git_state()


def file_changes():
    global LAST_STATE
    now = git_state()
    changed = {p: v[0] for p, v in now.items() if LAST_STATE.get(p) != v}
    LAST_STATE = now
    return changed


def changes_note():
    changed = file_changes()
    if not changed:
        return ""
    lines = [f"{LABELS.get(code, code)}: {path}" for path, code in changed.items()]
    return (
        "\n<system-reminder>\n"
        "These files changed since your last turn. Read them again before "
        "editing:\n" + "\n".join(lines) + "\n</system-reminder>"
    )


def todos_note():
    plan = todos_prompt()
    return f"\n<todos>\n{plan}\n</todos>" if plan else ""


def reminder():
    branch = git('branch --show-current').strip() or '(no git repo / detached)'
    return {
        "role": "user",
        "content": (
            "<env>\n"
            f"time: {datetime.now():%Y-%m-%d %H:%M}\n"
            f"git branch: {branch}\n"
            "</env>" + todos_note() + changes_note()
        ),
    }