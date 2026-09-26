import subprocess
from pathlib import Path

import requests

import history
import sandbox
import checkpoints
from skills import read_skill, write_skill
from todos import write_todos, TODO_SCHEMA
from subagent import task, TASK_SCHEMA

# --- TOOL FUNCTIONS ---

def bash(command: str) -> str:
    """Run a shell command and return its combined stdout and stderr."""
    try:
        import config
        result = sandbox.run(command, timeout=config.BASH_TIMEOUT)
        output = (result.stdout + result.stderr) or "(no output)"
        return history.cap(output)
    except subprocess.TimeoutExpired as expired:
        return f"Timed out after {expired.timeout}s and was killed."
    except Exception as e:
        return str(e)


def read_file(path: str) -> str:
    """Read a file and return its contents."""
    try:
        with open(path) as f:
            return history.cap(f.read())
    except Exception as e:
        return str(e)


def fetch_url(url: str) -> str:
    """Fetch a URL and return its text content formatted as clean Markdown."""
    jina_url = f"https://r.jina.ai/{url}"
    try:
        headers = {"X-Return-Format": "text"}
        response = requests.get(jina_url, headers=headers, timeout=15)
        response.raise_for_status()
        return history.cap(response.text)
    except Exception as e:
        return f"Error fetching URL: {str(e)}"


def write_file(path: str, content: str) -> str:
    """Create a file, or overwrite it if it already exists."""
    try:
        checkpoints.snapshot(path)  # so /undo can restore (or delete) it later
        with open(path, "w") as f:
            f.write(content)
        return f"Wrote {path}"
    except Exception as e:
        return str(e)


def str_replace(path: str, old_str: str, new_str: str, allow_multi_edit: bool = False) -> str:
    """Swap exact text in a file. old_str must match exactly once."""
    try:
        with open(path) as f:
            content = f.read()

        count = content.count(old_str)
        if count == 0:
            return f"Error: old_str was not found in {path}"
        if count > 1 and not allow_multi_edit:
            return (
                f"Error: old_str matches {count} times in {path}. "
                "Add surrounding lines to make it unique, "
                "or set allow_multi_edit to replace them all."
            )

        checkpoints.snapshot(path)  # before the file is actually touched
        with open(path, "w") as f:
            f.write(content.replace(old_str, new_str))
        return f"Replaced {count} match(es) in {path}"
    except Exception as e:
        return str(e)


def list_dir(path: str = ".", recursive: bool = False) -> str:
    """List a directory's contents. Cheaper than a bash 'ls' round trip for the model."""
    try:
        base = Path(path)
        if not base.is_dir():
            return f"Error: {path} is not a directory"
        entries = base.rglob("*") if recursive else base.iterdir()
        lines = []
        for entry in sorted(entries):
            marker = "/" if entry.is_dir() else ""
            lines.append(f"{entry.relative_to(base)}{marker}")
        return history.cap("\n".join(lines) or "(empty)")
    except Exception as e:
        return str(e)


def glob_files(pattern: str, path: str = ".") -> str:
    """Find files under `path` matching a glob pattern, e.g. '**/*.py'."""
    try:
        base = Path(path)
        matches = [str(p) for p in base.glob(pattern) if p.is_file()]
        return history.cap("\n".join(sorted(matches)) or "(no matches)")
    except Exception as e:
        return str(e)


TOOLS = {
    "bash": bash,
    "read_file": read_file,
    "write_file": write_file,
    "str_replace": str_replace,
    "read_skill": read_skill,
    "write_skill": write_skill,
    "fetch_url": fetch_url,
    "write_todos": write_todos,
    "task": task,
    "list_dir": list_dir,
    "glob_files": glob_files,
}


def safe_call(func_name, args):
    """Run a tool call, turning any exception (bad/missing args, unknown tool,
    the tool's own bug) into a string result instead of crashing the harness.
    Both the main loop and subagents route through this."""
    func = TOOLS.get(func_name)
    if not func:
        return "Error: Tool not found."
    try:
        return str(func(**args))
    except TypeError as e:
        return f"Error: bad arguments for {func_name}({args}): {e}"
    except Exception as e:
        return f"Error while running {func_name}: {e}"


# --- TOOL SCHEMAS ---

BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command. Each command runs in a new ephemeral shell. Do not use 'cd' alone to change directories; instead, chain commands (e.g., 'cd folder && ls') or use absolute paths.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run"}
            },
            "required": ["command"],
        },
    },
}

READ_TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file and return its contents.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read"}
            },
            "required": ["path"],
        },
    },
}

WRITE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Create a file, or overwrite it if it already exists.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File to write"},
                "content": {"type": "string", "description": "The full contents"},
            },
            "required": ["path", "content"],
        },
    },
}

STR_REPLACE_TOOL = {
    "type": "function",
    "function": {
        "name": "str_replace",
        "description": "Replace exact text in a file. old_str must appear exactly once, so include surrounding lines if needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File to edit"},
                "old_str": {"type": "string", "description": "Exact text to find"},
                "new_str": {"type": "string", "description": "Text to put in its place"},
                "allow_multi_edit": {
                    "type": "boolean",
                    "description": "Replace every match instead of failing",
                },
            },
            "required": ["path", "old_str", "new_str"],
        },
    },
}

READ_SKILL_TOOL = {
    "type": "function",
    "function": {
        "name": "read_skill",
        "description": "Open a skill and return its full instructions.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name of the skill to read"}
            },
            "required": ["name"],
        },
    },
}

WRITE_SKILL_TOOL = {
    "type": "function",
    "function": {
        "name": "write_skill",
        "description": "Create a new agent skill. Scaffolds the directory, writes the SKILL.md file with YAML frontmatter, and activates it immediately.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "A short, snake_case name for the skill (e.g., 'joke_teller')"},
                "description": {"type": "string", "description": "A concise one-sentence description of when to use this skill"},
                "instructions": {"type": "string", "description": "The full markdown instructions explaining exactly what the agent should do when using this skill"}
            },
            "required": ["name", "description", "instructions"],
        },
    },
}

FETCH_URL_TOOL = {
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": "Fetch the contents of a webpage and return it as clean Markdown. Use this to read articles, documentation, or search results.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full HTTP/HTTPS URL to fetch"}
            },
            "required": ["url"],
        },
    },
}

LIST_DIR_TOOL = {
    "type": "function",
    "function": {
        "name": "list_dir",
        "description": "List a directory's contents, optionally recursively. Cheaper than shelling out to ls/find for a simple listing.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory to list (default: current directory)"},
                "recursive": {"type": "boolean", "description": "List all nested contents, not just the top level"},
            },
        },
    },
}

GLOB_TOOL = {
    "type": "function",
    "function": {
        "name": "glob_files",
        "description": "Find files matching a glob pattern (e.g. '**/*.py', 'src/*.ts') under a base path.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern to match, relative to path"},
                "path": {"type": "string", "description": "Base directory to search from (default: current directory)"},
            },
            "required": ["pattern"],
        },
    },
}

TOOL_SCHEMAS = [
    BASH_TOOL, READ_TOOL, WRITE_TOOL, STR_REPLACE_TOOL, READ_SKILL_TOOL,
    WRITE_SKILL_TOOL, FETCH_URL_TOOL, TODO_SCHEMA, TASK_SCHEMA,
    LIST_DIR_TOOL, GLOB_TOOL,
]