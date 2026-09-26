import atexit
import json
import tempfile
from pathlib import Path
import config

CAP = 10_000  # chars of a fresh tool result the agent sees inline
STUB = 300  # chars kept once the turn that produced it is over

TRIMMED = "[output trimmed:"      # marker for a stub left by strip() or fit()
SPILLED = "[output spilled:"      # marker for cap()'s "full text is on disk" note
SUMMARY = "<summary>"             # marks the handoff note compaction leaves behind
SPILLS = []  # temp files belonging to the current turn


def spill(text):
    """Park the full output on disk for the rest of this turn."""
    handle = tempfile.NamedTemporaryFile(
        mode="w", prefix="neuralcode-", suffix=".txt", delete=False
    )
    handle.write(text)
    handle.close()
    SPILLS.append(Path(handle.name))
    return handle.name


def cap(text):
    """Trim a fresh tool result, leaving a pointer to the whole thing.

    Uses a distinct SPILLED marker (not TRIMMED) so strip() can tell "this
    still points at a live temp file" apart from "this was already
    stubbed" and re-stub it once the file is gone.
    """
    if len(text) <= CAP:
        return text

    try:
        path = spill(text)
    except OSError:
        return text[:CAP] + f"\n\n{TRIMMED} {len(text) - CAP} chars cut and the rest could not be saved.]"

    return (
        text[:CAP] + f"\n\n{SPILLED} {len(text) - CAP} of {len(text)} chars cut. "
        f"The whole output is at {path} - page through it with "
        "head, tail, sed -n or grep. It is deleted when this turn ends.]"
    )


def sweep():
    """Delete this turn's temp files. Their paths die with the tool results."""
    for path in SPILLS:
        path.unlink(missing_ok=True)
    SPILLS.clear()


atexit.register(sweep)  # best-effort cleanup even if the process dies mid-turn


def locked(messages):
    """Length of the frozen prefix - everything up to and including the newest summary."""
    for index in range(len(messages) - 1, -1, -1):
        content = messages[index].get("content")
        if isinstance(content, str) and SUMMARY in content:
            return index + 1
    return 0


def strip(messages):
    """Shrink every tool result that is no longer part of the live turn.

    A message can be in one of three states: fresh and short (leave it),
    fresh and SPILLED to a temp file (once the turn ends that file is
    deleted by sweep(), so its stub is now a dangling pointer and must be
    re-stubbed to a plain STUB-sized note), or already TRIMMED by a
    previous call (already at STUB size, nothing to do).
    """
    shrunk = 0
    for message in messages[locked(messages):]:
        content = message.get("content") or ""
        if message.get("role") != "tool" or not isinstance(content, str):
            continue
        if TRIMMED in content:
            continue  # already a stub, and does not reference a temp file

        if SPILLED in content or len(content) > STUB:
            # Either it was spilled (the temp file dies with sweep() at the
            # end of this turn, so keeping its path around is a dangling
            # pointer) or it's just long. Either way, collapse to a plain
            # stub - we don't try to preserve the exact original length,
            # since the point is just "there was more, re-run to see it".
            head = content.split(f"\n\n{SPILLED}")[0] if SPILLED in content else content
            message["content"] = (
                head[:STUB] + f"\n\n{TRIMMED} rest omitted now that the turn is over "
                "(its temp file, if any, no longer exists). Run the command again if you need it.]"
            )
            shrunk += 1
    return shrunk


def estimate(messages):
    """Rough token count. Good enough to decide whether to panic."""
    return sum(len(json.dumps(m, default=str)) for m in messages) // 4


def fit(messages):
    """Last resort: discard whole tool results, oldest first, until it fits."""
    budget = config.CONTEXT_WINDOW * config.COMPACT_AT
    dropped = 0
    for message in messages[locked(messages):]:
        if estimate(messages) <= budget:
            break
        content = message.get("content") or ""
        if message.get("role") == "tool" and isinstance(content, str) and TRIMMED not in content:
            message["content"] = f"{TRIMMED} dropped to fit the context window.]"
            dropped += 1
    return dropped