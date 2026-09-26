"""Save and resume conversations across process restarts.

Sessions are plain JSON so they're easy to inspect or hand-edit, and are
namespaced under the project's .agents dir the same way skills and
checkpoints are - each project keeps its own session list.
"""

import json
from datetime import datetime
from pathlib import Path

SESSION_DIR = Path.cwd() / ".agents" / "sessions"


def _safe_name(name):
    return "".join(c for c in name if c.isalnum() or c in "-_") or "session"


def save(messages, name=None):
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    name = _safe_name(name or datetime.now().strftime("%Y%m%d-%H%M%S"))
    path = SESSION_DIR / f"{name}.json"
    path.write_text(json.dumps({"saved_at": datetime.now().isoformat(), "messages": messages}, indent=2))
    return str(path)


def load(name):
    path = SESSION_DIR / f"{_safe_name(name)}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data.get("messages")


def list_sessions():
    if not SESSION_DIR.exists():
        return []
    return sorted(p.stem for p in SESSION_DIR.glob("*.json"))