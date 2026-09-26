import re
from fnmatch import fnmatch
from pathlib import Path

PROJECT = Path.cwd().resolve()

# Four tiers, strictest wins when a compound command has parts in different tiers:
#   allow   -> just run it
#   ask     -> simple y/n prompt
#   confirm -> dangerous but sometimes legitimate; the user must type the
#              word "yes" in full (not just 'y') to proceed - a higher bar
#              than "ask" for things that are hard or impossible to undo
#   deny    -> never runs, not even with confirmation
BASH_RULES = {
    "*": "ask",

    # --- read-only: let them through ---
    "ls*": "allow", "pwd": "allow", "cd *": "allow", "echo *": "allow",
    "sort*": "allow", "uniq*": "allow", "cut *": "allow",
    "basename *": "allow", "dirname *": "allow", "date*": "allow",
    "env": "allow", "cat *": "allow", "head *": "allow", "tail *": "allow",
    "wc *": "allow", "file *": "allow", "which *": "allow",
    "grep *": "allow", "rg *": "allow", "find *": "allow", "tree*": "allow",
    "pytest*": "allow", "python -m pytest*": "allow",

    # --- git: local + reversible, the everyday workflow -> allow ---
    "git status*": "allow", "git diff*": "allow", "git log*": "allow",
    "git show*": "allow", "git ls-files*": "allow", "git blame*": "allow",
    "git add*": "allow", "git commit*": "allow",
    "git branch": "allow", "git branch -v*": "allow", "git branch -a*": "allow",
    "git stash": "allow", "git stash list*": "allow", "git stash show*": "allow",
    "git stash push*": "allow", "git stash pop": "allow", "git stash apply*": "allow",
    "git tag": "allow", "git tag -l*": "allow",
    "git checkout -b *": "allow", "git switch -c *": "allow",
    "git remote -v": "allow", "git remote show*": "allow",

    # --- git: touches the network or rewrites what HEAD points to -> ask ---
    "git fetch*": "ask", "git pull*": "ask", "git merge*": "ask",
    "git rebase*": "ask", "git cherry-pick*": "ask",
    "git checkout *": "ask", "git switch *": "ask",
    "git remote add*": "ask", "git remote set-url*": "ask",
    "git config*": "ask",

    # --- git: hard to undo, but a real user genuinely needs these sometimes
    #     -> confirm, rather than a blanket "never" that just gets in the way
    "git push*": "confirm", "git push --force*": "confirm", "git push -f*": "confirm",
    "git reset*": "confirm", "git reset --hard*": "confirm",
    "git clean*": "confirm", "git branch -D*": "confirm", "git tag -d*": "confirm",
    "git filter-branch*": "confirm", "git rebase --onto*": "confirm",

    # --- filesystem/process mutation: dangerous, occasionally legitimate -> confirm ---
    "rm *": "confirm", "chmod *": "confirm", "chown *": "confirm",
    "kill -9*": "confirm", "kill -KILL*": "confirm", "truncate*": "confirm",
    "npm publish*": "confirm", "pip install*": "ask", "npm install*": "ask",
    "curl *": "ask", "wget *": "ask", "docker *": "ask",

    # --- never, no override: privilege escalation and whole-system destruction ---
    "sudo *": "deny", "su *": "deny", "doas *": "deny",
    "mkfs*": "deny", "dd *": "deny", "shutdown*": "deny", "reboot*": "deny",
    ":(){ :|:& };:": "deny",
}

# Files that should never be silently read or written by an "allow"-listed
# command, no matter how innocuous the command itself looks (e.g. `cat .env`).
SENSITIVE_PATTERNS = [
    "*.env", ".env*", "*id_rsa*", "*id_ed25519*", "*.pem", "*.pfx", "*.key",
    "*credentials*", "*secrets*", "*.netrc",
    ".aws/*", "*/.aws/*", ".ssh/*", "*/.ssh/*",
    # a hook is code that runs on every future git command - cover both a
    # hooks dir at the project root and one nested in a subdirectory.
    ".git/hooks/*", "*/.git/hooks/*",
]

# Absolute paths that make "confirm"-tier destructive commands catastrophic
# instead of merely risky: the root of the filesystem, home, or a core system
# directory, as opposed to some project subfolder that happens to be named
# similarly. Only checked against commands already at "confirm" or worse.
_CRITICAL_PATH = re.compile(
    r"^(?:/|~|\$HOME|/etc/?\*?|/usr/?\*?|/bin/?\*?|/boot/?\*?|/dev/?\*?|"
    r"/proc/?\*?|/sys/?\*?|/root/?\*?|/var/?\*?)$"
)

# Shell features that let a command escape simple prefix matching. Plain
# redirection (>) is common and mostly benign (`python x.py > out.txt`), so it
# only bumps a command to "ask". Command/process substitution hides a second
# command inside what looks like a harmless one (`echo $(rm -rf /)` would
# otherwise match the harmless "echo *" rule) - that's a deliberate attempt to
# smuggle something past a prefix match, so it earns the stronger "confirm".
_REDIRECT = re.compile(r"(?<!\d)>{1,2}(?!&)")
_SUBSTITUTION = re.compile(r"\$\(|`|<\(|>\(")

_TIER_RANK = {"allow": 0, "ask": 1, "confirm": 2, "deny": 3}


def split_command(command):
    """Split a compound command on separators while ignoring quoted/escaped characters."""
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


def _rule_for(part):
    action = "ask"
    for pattern, rule in BASH_RULES.items():
        if fnmatch(part, pattern):
            action = rule
    return action


def decide(command):
    """Rate every part of a compound command; the strictest verdict wins."""
    verdicts = []
    for part in split_command(command):
        if _touches_sensitive_path(part):
            verdicts.append("ask")
            continue

        if _SUBSTITUTION.search(part):
            verdicts.append("confirm")  # hides a command inside another - treat as deliberate
            continue
        if _REDIRECT.search(part):
            verdicts.append("ask")
            continue

        action = _rule_for(part)

        # A destructive command aimed at "/", "~", or a whole system directory
        # (not some project folder that merely starts with one of those
        # letters) is escalated past "confirm" - typing "yes" once should
        # never be enough to wipe a whole filesystem.
        if action == "confirm" and _touches_critical_path(part):
            action = "deny"

        verdicts.append(action)

    return max(verdicts, key=lambda v: _TIER_RANK[v]) if verdicts else "allow"


def inside_project(path):
    resolved = Path(path).resolve()
    return PROJECT in resolved.parents or PROJECT == resolved


def check(name, args):
    """Return (action, reason). Action is allow, ask, confirm or deny."""
    if name == "bash":
        return decide(args["command"]), f"run: {args['command']}"

    if name in ("write_file", "str_replace"):
        path = args.get("path", "")
        if any(fnmatch(Path(path).name, pattern) or fnmatch(path, pattern) for pattern in SENSITIVE_PATTERNS):
            return "confirm", f"{name} a sensitive-looking file: {path}"
        if not inside_project(path):
            return "ask", f"{name} outside {PROJECT}: {path}"

        import config
        if config.CONFIRM_EDITS:
            return "ask", f"{name} {path}"

    return "allow", None