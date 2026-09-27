import os

# --- Context window / compaction ---
CONTEXT_WINDOW = int(os.getenv("CONTEXT_WINDOW", 32000))
COMPACT_AT = float(os.getenv("COMPACT_AT", 0.8))   # rebuild when prompt exceeds this fraction
COMPACT_TO = float(os.getenv("COMPACT_TO", 0.2))   # ...and shrink the tail back down to this fraction

# --- Model routing (single source of truth — everything else imports MODEL from here) ---
# Explicit override always wins, so a user can pin a model without touching code.
if os.getenv("AGENT_MODEL"):
    MODEL = os.getenv("AGENT_MODEL")
    PROVIDER = "custom"
elif os.getenv("GROQ_API_KEY"):
    MODEL = "llama-3.3-70b-versatile"
    PROVIDER = "groq"
else:
    MODEL = "deepseek/deepseek-v4.1-flash"
    PROVIDER = "openrouter"

# A cheaper/faster model for subagents and compaction, where raw coding strength
# matters less than speed and cost. Falls back to MODEL if unset.
SUBAGENT_MODEL = os.getenv("SUBAGENT_MODEL", MODEL)

# Rough $ / 1M tokens (input, output). Best-effort, used only for the running
# cost estimate printed after each turn — not billing-accurate.
PRICES = {
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "deepseek/deepseek-v4.1-flash": (0.20, 0.80),
}
DEFAULT_PRICE = (0.50, 1.50)  # used for unrecognized models so the estimate degrades gracefully

# Hard stop: if the running session cost estimate crosses this, the agent
# refuses further LLM calls until the user acknowledges. 0 disables the cap.
BUDGET_LIMIT_USD = float(os.getenv("AGENT_BUDGET_USD", 0))

# --- Safety / execution ---
MAX_AGENT_TURNS = int(os.getenv("MAX_AGENT_TURNS", 50))     # hard stop on tool-call loops per user message
BASH_TIMEOUT = int(os.getenv("BASH_TIMEOUT", 60))
LLM_RETRIES = int(os.getenv("LLM_RETRIES", 3))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", 4096))

# When true, write_file/str_replace always pause for a diff + confirmation,
# regardless of the permissions table. "Plan mode" for cautious sessions.
CONFIRM_EDITS = os.getenv("AGENT_CONFIRM_EDITS", "0") == "1"

SESSION_DIR_NAME = ".agents/sessions"
CHECKPOINT_DIR_NAME = ".agents/checkpoints"
from pathlib import Path
# Protect the AI Harness code itself
HARNESS_DIR = Path(__file__).resolve().parent

# The active working directory for user projects (outside the harness)
WORKSPACE_DIR = Path(os.getenv("WORKSPACE", str(HARNESS_DIR.parent / "Workspace"))).resolve()

from pathlib import Path

def resolve_path(p):
    path_obj = Path(p).expanduser()
    if path_obj.is_absolute():
        return path_obj.resolve()
    return (WORKSPACE_DIR / path_obj).resolve()
