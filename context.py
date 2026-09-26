import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from todos import todos_prompt

LABELS = {"M": "modified", "D": "deleted", "A": "added", "??": "new"}

def git(command):
    try:
        result = subprocess.run(
            f"git {command}", shell=True, capture_output=True, text=True, stderr=subprocess.DEVNULL
        )
        return result.stdout
    except Exception:
        return ""

def file_hash(path):
    file = Path(path)
    try:
        return hashlib.md5(file.read_bytes()).hexdigest() if file.is_file() else None
    except Exception:
        return None

def git_state():
    state = {}
    status_output = git("status --porcelain")
    if not status_output:
        return state
        
    for line in status_output.splitlines():
        if len(line) < 3:
            continue
        path = line[3:]
        state[path] = (line[:2].strip(), file_hash(path))
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