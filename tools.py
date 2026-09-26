import subprocess
from skills import read_skill, write_skill
import requests
from todos import write_todos, TODO_SCHEMA
import sandbox

# --- TOOL FUNCTIONS ---

import subprocess
import requests
import sandbox
import history
from skills import read_skill, write_skill
from todos import write_todos, TODO_SCHEMA

# --- TOOL FUNCTIONS ---

def bash(command: str) -> str:
    """Run a shell command and return its combined stdout and stderr."""
    try:
        result = sandbox.run(command, timeout=60)
        output = (result.stdout + result.stderr) or "(no output)"
        # FIX: Route through history.cap
        return history.cap(output)
    except subprocess.TimeoutExpired as expired:
        return f"Timed out after {expired.timeout}s and was killed."
    except Exception as e:
        return str(e)

def read_file(path: str) -> str:
    """Read a file and return its contents."""
    try:
        with open(path) as f:
            # FIX: Route through history.cap
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
        # FIX: Route through history.cap
        return history.cap(response.text)
    except Exception as e:
        return f"Error fetching URL: {str(e)}"

def write_file(path: str, content: str) -> str:
    """Create a file, or overwrite it if it already exists."""
    try:
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

        with open(path, "w") as f:
            f.write(content.replace(old_str, new_str))
        return f"Replaced {count} match(es) in {path}"
    except Exception as e:
        return str(e)


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

TOOL_SCHEMAS = [BASH_TOOL, READ_TOOL, WRITE_TOOL, STR_REPLACE_TOOL, READ_SKILL_TOOL, WRITE_SKILL_TOOL, FETCH_URL_TOOL, TODO_SCHEMA]

# Add write_todos to the mapping
TOOLS = {
    "bash": bash,
    "read_file": read_file,
    "write_file": write_file,
    "str_replace": str_replace,
    "read_skill": read_skill,
    "write_skill": write_skill,
    "fetch_url": fetch_url,
    "write_todos": write_todos
}