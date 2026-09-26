"""Per-turn file checkpoints.

Every write_file/str_replace call snapshots the pre-edit bytes of the file it
is about to touch (once per turn, the first time that file is touched). When
the turn ends, that batch of snapshots is frozen onto a stack. `/undo` pops
the most recent turn and restores every file in it to its pre-turn state -
including deleting files that didn't exist before the turn created them.

This is deliberately independent of git: it works in a fresh directory with
no repo, it undoes exactly "what this agent turn did" rather than "the last
commit", and it costs nothing until a write actually happens.
"""

from pathlib import Path

_current_turn = []   # snapshots taken so far in the turn that hasn't ended yet
HISTORY = []          # committed turns, oldest first; HISTORY[-1] is what /undo restores
MAX_HISTORY = 50       # cap memory use in very long sessions


def begin_turn():
    """Call once at the start of handling a new user message."""
    global _current_turn
    _current_turn = []


def snapshot(path):
    """Record the pre-edit state of `path`, the first time it's touched this turn."""
    resolved = str(Path(path))
    if any(entry["path"] == resolved for entry in _current_turn):
        return  # already have this turn's "before" for this file

    p = Path(path)
    existed = p.exists()
    try:
        content = p.read_bytes() if existed else None
    except Exception:
        content = None  # unreadable (e.g. permissions) - best effort, nothing to restore
    _current_turn.append({"path": resolved, "existed": existed, "content": content})


def commit_turn():
    """Freeze this turn's snapshots as one undoable unit. Call after the turn ends."""
    global _current_turn, HISTORY
    if _current_turn:
        HISTORY.append(_current_turn)
        del HISTORY[:-MAX_HISTORY]
    _current_turn = []


def pending_files():
    """Files touched so far in the in-progress turn, for diagnostics."""
    return [e["path"] for e in _current_turn]


def undo_last_turn():
    """Restore every file from the most recently committed turn. Returns a status string."""
    if not HISTORY:
        return "Nothing to undo."

    turn = HISTORY.pop()
    lines = []
    for entry in reversed(turn):
        p = Path(entry["path"])
        try:
            if entry["existed"]:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(entry["content"])
                lines.append(f"restored {p}")
            elif p.exists():
                p.unlink()
                lines.append(f"removed {p} (this turn had created it)")
        except Exception as e:
            lines.append(f"could not restore {p}: {e}")

    return "Undid the last turn's file changes:\n" + "\n".join(lines)