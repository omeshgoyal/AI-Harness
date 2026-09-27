import re
from fnmatch import fnmatch
from pathlib import Path
import config

# Use the workspace from config, creating it if it doesn't exist
PROJECT = config.WORKSPACE_DIR
PROJECT.mkdir(parents=True, exist_ok=True)
HARNESS_DIR = config.HARNESS_DIR

# Four tiers, strictest wins when a compound command has parts in different tiers:
#   allow   -> just run it
#   ask     -> simple y/n prompt
#   confirm -> dangerous but sometimes legitimate; the user must type the word "yes"
#   deny    -> never runs, not even with confirmation
BASH_RULES = {
    "*": "allow", # Basic harmless commands default to allow to reduce spam

    # --- read-only: let them through ---
    "ls*": "allow", "pwd": "allow", "cd *": "allow", "echo *": "allow",
    "sort*": "allow", "uniq*": "allow", "cut *": "allow",
    "basename *": "allow", "dirname *": "allow", "date*": "allow",
    "env": "allow", "cat *": "allow", "head *": "allow", "tail *": "allow",
    "wc *": "allow", "file *": "allow", "which *": "allow",
    "grep *": "allow", "rg *": "allow", "find *": "allow", "tree*": "allow",

    # --- destructive commands: always ask or confirm ---
    "rm *": "confirm", "chmod *": "confirm", "chown *": "confirm",
    "kill *": "confirm", "truncate*": "confirm",
    "curl *": "ask", "wget *": "ask", "docker *": "ask",
    "pip install*": "ask", "npm install*": "ask",

    # --- never, no override: privilege escalation and whole-system destruction ---
    "sudo *": "deny", "su *": "deny", "doas *": "deny",
    "mkfs*": "deny", "dd *": "deny", "shutdown*": "deny", "reboot*": "deny",
    ":(){ :|:& };:": "deny",
}

SENSITIVE_PATTERNS = [
    "*.env", ".env*", "*id_rsa*", "*id_ed25519*", "*.pem", "*.pfx", "*.key",
    "*credentials*", "*secrets*", "*.netrc",
    ".aws/*", "*/.aws/*", ".ssh/*", "*/.ssh/*",
    ".git/hooks/*", "*/.git/hooks/*",
]

_CRITICAL_PATH = re.compile(
    r"^(?:/|~|\$HOME|/etc/?\*?|/usr/?\*?|/bin/?\*?|/boot/?\*?|/dev/?\*?|"
    r"/proc/?\*?|/sys/?\*?|/root/?\*?|/var/?\*?)$"
)

_REDIRECT = re.compile(r"(?<!\d)>{1,2}(?!&)")
_SUBSTITUTION = re.compile(r"\$\(|`|<\(|>\(")

_TIER_RANK = {"allow": 0, "ask": 1, "confirm": 2, "deny": 3}

def split_command(command):
    parts, current, quote = [], [], None
    index = 0
    while index < len(command):
        char = command[index]
        if quote:
            current.append(char)
            quote = None if char == quote else quote
        elif char == "\\":
            current.append(char)
            index += 1
            if index < len(command):
                current.append(command[index])
        elif char in "\"'":
            quote = char
            current.append(char)
        elif char in "&|;":
            parts.append("".join(current))
            current = []
            while index + 1 < len(command) and command[index + 1] in "&|":
                index += 1
        else:
            current.append(char)
        index += 1
    parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]

def _touches_sensitive_path(part):
    for token in part.split():
        token = token.strip("'\"")
        if any(fnmatch(token, pattern) for pattern in SENSITIVE_PATTERNS):
            return True
    return False

def _touches_critical_path(part):
    for token in part.split():
        token = token.strip("'\"").rstrip("/")
        if _CRITICAL_PATH.match(token or "/"):
            return True
    return False

# Security Boundary: Checks if the path touches the internal AI Harness code
def touches_harness_code(cmd_or_path):
    harness_str = str(HARNESS_DIR)
    
    # Check the whole string
    if harness_str in cmd_or_path or "/AI Harness" in cmd_or_path:
        return True
        
    # Check every individual token
    import shlex
    try:
        tokens = shlex.split(cmd_or_path)
    except:
        tokens = cmd_or_path.split()
        
    for token in tokens:
        if token.startswith("..") or harness_str in token or token.startswith("/Users/yuta/Desktop/AI Harness"):
            return True
        try:
            # Expand tilde and resolve relative to WORKSPACE_DIR
            p = Path(token).expanduser()
            if not p.is_absolute():
                p = config.WORKSPACE_DIR / p
            resolved = p.resolve()
            
            if HARNESS_DIR in resolved.parents or HARNESS_DIR == resolved:
                return True
        except:
            pass
            
    return False

def _rule_for(part):
    action = "ask" # fallback if not allow/confirm/deny
    for pattern, rule in BASH_RULES.items():
        if fnmatch(part, pattern):
            action = rule
    return action

def decide(command):
    verdicts = []
    
    if touches_harness_code(command):
        return "deny"

    for part in split_command(command):
        if touches_harness_code(part):
            return "deny"
            
        if _touches_sensitive_path(part):
            verdicts.append("ask")
            continue

        if _SUBSTITUTION.search(part):
            verdicts.append("confirm")
            continue
        if _REDIRECT.search(part):
            verdicts.append("ask")
            continue

        action = _rule_for(part)

        if action == "confirm" and _touches_critical_path(part):
            action = "deny"

        verdicts.append(action)

    return max(verdicts, key=lambda v: _TIER_RANK[v]) if verdicts else "allow"

def inside_project(path):
    try:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = PROJECT / p
        resolved = p.resolve()
        return PROJECT in resolved.parents or PROJECT == resolved
    except:
        return False

def check(name, args):
    if name == "bash":
        return decide(args["command"]), f"run: {args['command']}"

    if name in ("write_file", "str_replace", "view_file", "read_file"):
        path = args.get("path", "")
        
        # Security Block: Cannot touch AI Harness code
        if touches_harness_code(path):
            return "deny", "attempted to access internal AI Harness system code"
            
        if any(fnmatch(Path(path).name, pattern) or fnmatch(path, pattern) for pattern in SENSITIVE_PATTERNS):
            return "confirm", f"{name} a sensitive-looking file: {path}"
            
        if not inside_project(path):
            return "ask", f"{name} outside workspace ({PROJECT}): {path}"

        if config.CONFIRM_EDITS and name in ("write_file", "str_replace"):
            return "ask", f"{name} {path}"

    return "allow", None
