import os
import json
from rich.console import Console

console = Console()
MAX_TURNS = 12 

# Structural block: these tools are completely stripped from the subagent's toolset.
# It cannot recurse (task), mess with the plan (write_todos), or edit files.
WITHHELD = {"task", "write_todos", "str_replace", "write_file", "write_skill"}

SYSTEM_PROMPT = f"""
You are an exploration subagent. You were given one question by a lead agent
and you answer it. That is the whole job.

You cannot see the conversation that spawned you, and the lead agent cannot
see anything you do here. Only your final message crosses back, so it has to
stand on its own.

You are working in {os.getcwd()}. Search inside it. Never search from / or
from the home directory - that scans the whole machine and will time out.

How to work:
- Use bash, read_file and read_skill to find out what is actually true.
  Prefer rg, grep and find to guess at where things live.
- You are here to read and report, not to change anything. Do not write or
  edit files, and do not run commands with side effects.
- Search in batches. Several greps in one turn beats one grep per turn.
- Stop as soon as you can answer. Do not keep looking to be thorough.

Your final message is the entire report, and it is the only thing that costs
the lead agent anything - so keep it short. Aim for under 150 words. Findings
only: file paths with line numbers, names, values. No preamble, no restating
the question, no long code blocks - cite the path and line and let the lead
agent open it. Say plainly what you could not find; a gap is useful, a guess
is not.
"""

def toolset():
    """Every tool except the ones a guest should not hold."""
    from tools import TOOL_SCHEMAS
    return [s for s in TOOL_SCHEMAS if s["function"]["name"] not in WITHHELD]

def task(description: str) -> str:
    """Run a fresh agent on one question and return only its final answer."""
    from history import fit
    from llm import call_llm
    from tools import TOOLS
    from permissions import check

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": description},
    ]
    
    console.print(f"\n[bold magenta]🕵️ Subagent deployed:[/bold magenta] {description}")
    report = None

    for _ in range(MAX_TURNS):
        fit(messages)

        with console.status("[bold magenta]Subagent exploring...", spinner="bouncingBar") as status:
            try:
                # Provide the restricted toolset so it cannot edit files or spawn loops
                message, usage = call_llm(messages, tools=toolset())
            except Exception as e:
                console.print(f"[bold red]Subagent API Error:[/bold red] {e}")
                break

            messages.append(message.model_dump(exclude_none=True))
            report = message.content or report

            if not message.tool_calls:
                console.print("[dim magenta]Subagent completed exploration.[/dim magenta]")
                return report or "(the subagent came back with nothing)"

            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                if func_name in TOOLS:
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    
                    status.stop()
                    action, reason = check(func_name, args)
                    
                    if action == "deny":
                        console.print(f"[bold red]⛔ Subagent Blocked:[/bold red] {reason}")
                        tool_result = f"Blocked by policy: {reason}"
                    elif action == "ask":
                        ans = console.input(f"[bold yellow]⚠️ Subagent wants to {reason}. Allow? (y/n): [/bold yellow]")
                        if ans.strip().lower() != 'y':
                            console.print("[dim red]Denied by user.[/dim red]")
                            tool_result = "The user denied this tool call."
                        else:
                            console.print(f"[dim magenta]⚡ Subagent executing '{func_name}'...[/dim magenta]")
                            tool_result = TOOLS[func_name](**args)
                    else:
                        console.print(f"[dim magenta]⚡ Subagent executing '{func_name}'...[/dim magenta]")
                        tool_result = TOOLS[func_name](**args)
                    
                    status.start()
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": str(tool_result)
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": "Error: Tool not found."
                    })

    if report:
        return (
            f"(stopped after {MAX_TURNS} turns, before finishing. Partial "
            f"findings below - narrow the question and ask again.)\n\n{report}"
        )
    return f"(stopped after {MAX_TURNS} turns with nothing to report.)"

TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "task",
        "description": (
            "Hand a self-contained exploration question to a fresh agent that "
            "has its own context window, and get back its findings. Use this "
            "to learn how the codebase works - tracing behaviour, locating "
            "where something is implemented, surveying files - so the search "
            "costs you one answer instead of dozens of tool results. It cannot "
            "see this conversation, so include every detail it needs. It reads "
            "and reports; it never edits. Do your own editing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": (
                        "The question, written to stand alone: what to find "
                        "out, where to start looking, and what the answer "
                        "should contain."
                    ),
                }
            },
            "required": ["description"],
        },
    },
}