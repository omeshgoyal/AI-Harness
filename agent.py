import json
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text

import config
from llm import get_system_prompt, call_llm, BudgetExceeded
from tools import TOOLS, safe_call
from context import reminder
from todos import active_form
from permissions import check
import history
import compact
import checkpoints
import session

console = Console()

HELP = """[bold]Commands[/bold]
  exit / quit      leave
  /clear           reset the conversation (keeps skills/checkpoints)
  /undo            revert every file this agent changed on the last turn
  /save [name]     save this conversation so it can be resumed later
  /resume <name>   load a previously saved conversation
  /sessions        list saved conversations
  /cost            show the running token/cost estimate
  /help            show this message"""


def print_usage(usage):
    """Formats the token usage nicely at the bottom of the response."""
    if not usage:
        return

    prompt = usage.get('prompt_tokens', 0)
    cached = usage.get('cached_tokens', 0)
    completion = usage.get('completion_tokens', 0)
    cost = usage.get('cost_usd')
    session_cost = usage.get('session_cost_usd')

    cache_pct = (cached / prompt * 100) if prompt > 0 else 0
    line = f"Tokens ⬩ Prompt: {prompt} ({cache_pct:.0f}% cached) ⬩ Completion: {completion}"
    if cost is not None:
        line += f" ⬩ ~${cost:.4f} (session ~${session_cost:.2f})"
    console.print(Text(line, style="dim cyan"))


def fresh_messages():
    return [{"role": "system", "content": get_system_prompt()}]


def run_tool_calls(message, messages, status):
    """Execute every tool call the model asked for, appending results to `messages`.
    Never lets a bad/missing argument or a bug inside a tool crash the session."""
    for tool_call in message.tool_calls:
        func_name = tool_call.function.name

        if func_name not in TOOLS:
            console.print(f"[bold red]System: Model attempted to call unknown tool '{func_name}'[/bold red]")
            messages.append({
                "role": "tool", "tool_call_id": tool_call.id,
                "name": func_name, "content": "Error: Tool not found.",
            })
            continue

        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            args = {}

        status.stop()
        action, reason = check(func_name, args)

        if action == "deny":
            console.print(f"[bold red]⛔ Blocked:[/bold red] {reason}")
            tool_result = f"Blocked by policy: {reason}"
        elif action == "confirm":
            console.print(f"[bold red]🚨 DANGEROUS:[/bold red] agent wants to {reason}")
            console.print("[bold red]This is hard or impossible to undo.[/bold red]")
            ans = console.input("[bold yellow]Type 'yes' (in full) to allow, anything else to deny: [/bold yellow]")
            if ans.strip().lower() != 'yes':
                console.print("[dim red]Denied by user.[/dim red]")
                tool_result = "The user denied this dangerous tool call."
            else:
                console.print(f"[dim yellow]⚡ Executing '{func_name}'...[/dim yellow]")
                tool_result = safe_call(func_name, args)
        elif action == "ask":
            ans = console.input(f"[bold yellow]⚠️ Agent wants to {reason}. Allow? (y/n): [/bold yellow]")
            if ans.strip().lower() != 'y':
                console.print("[dim red]Denied by user.[/dim red]")
                tool_result = "The user denied this tool call."
            else:
                console.print(f"[dim yellow]⚡ Executing '{func_name}'...[/dim yellow]")
                tool_result = safe_call(func_name, args)
        else:
            console.print(f"[dim yellow]⚡ Executing '{func_name}'...[/dim yellow]")
            tool_result = safe_call(func_name, args)

        status.start()
        messages.append({
            "role": "tool", "tool_call_id": tool_call.id,
            "name": func_name, "content": str(tool_result),
        })


def agent_turn(messages):
    """Run the model/tool loop for one user message. Returns (final_message, usage)."""
    message, usage = None, None

    with console.status(f"[bold cyan]{active_form().capitalize()}...", spinner="dots") as status:
        for turn in range(config.MAX_AGENT_TURNS):
            status.update(f"[bold cyan]{active_form().capitalize()}...")

            messages[0]["content"] = get_system_prompt()
            injection = reminder()

            if history.fit(messages):
                console.print("[dim yellow]Note: Dropped old tool output to make this request fit.[/dim yellow]")

            try:
                message, usage = call_llm(messages + [injection])
            except BudgetExceeded as e:
                status.stop()
                console.print(f"\n[bold red]Budget cap reached:[/bold red] {e}")
                console.print("[dim]Raise AGENT_BUDGET_USD, or restart, to keep going.[/dim]")
                message, usage = None, None
                break
            except Exception as e:
                status.stop()
                console.print(f"\n[bold red]API Error:[/bold red] {str(e)}")
                # Only pop if the last message was from the user - if it was a
                # tool result, leave the history intact so the user can retry.
                if messages and messages[-1].get("role") == "user":
                    messages.pop()
                message, usage = None, None
                break

            msg_dict = message.model_dump(exclude_none=True)
            messages.append(msg_dict)

            if not getattr(message, 'tool_calls', None):
                break

            run_tool_calls(message, messages, status)
        else:
            console.print(
                f"[bold yellow]Stopped after {config.MAX_AGENT_TURNS} tool-call rounds "
                "in a single turn to avoid a runaway loop. Say 'continue' to keep going.[/bold yellow]"
            )

    return message, usage


def handle_command(command, messages):
    """Returns a new `messages` list if the command changed it, else None (and
    True/False for whether the REPL should keep looping) via a tuple."""
    parts = command.split(maxsplit=1)
    cmd = parts[0]
    arg = parts[1].strip() if len(parts) > 1 else None

    if cmd == "/clear":
        console.print("[dim green]History cleared. Starting fresh.[/dim green]")
        return fresh_messages()

    if cmd == "/undo":
        console.print(checkpoints.undo_last_turn())
        return messages

    if cmd == "/save":
        path = session.save(messages, arg)
        console.print(f"[dim green]Saved to {path}[/dim green]")
        return messages

    if cmd == "/resume":
        if not arg:
            console.print("[bold red]Usage: /resume <name>[/bold red]")
            return messages
        loaded = session.load(arg)
        if loaded is None:
            console.print(f"[bold red]No saved session named '{arg}'[/bold red]")
            return messages
        console.print(f"[dim green]Resumed '{arg}' ({len(loaded)} messages).[/dim green]")
        return loaded

    if cmd == "/sessions":
        names = session.list_sessions()
        console.print("\n".join(names) if names else "[dim](no saved sessions)[/dim]")
        return messages

    if cmd == "/cost":
        from llm import get_totals
        totals = get_totals()
        console.print(f"Session so far: {totals['prompt_tokens']} prompt / "
                       f"{totals['completion_tokens']} completion tokens, "
                       f"~${totals['cost_usd']:.2f}")
        return messages

    if cmd == "/help":
        console.print(Panel(HELP, expand=False))
        return messages

    console.print(f"[bold red]Unknown command: {cmd}. Try /help[/bold red]")
    return messages


def main():
    console.print(Panel(
        "[bold green]Agent initialized.[/bold green]\n"
        "[dim]Type 'exit' to quit, '/help' for commands.[/dim]",
        expand=False,
    ))

    messages = fresh_messages()

    while True:
        try:
            user_input = console.input("\n[bold blue]You:[/bold blue] ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Shutting down...[/dim]")
            break

        stripped = user_input.strip()
        if stripped.lower() in ('quit', 'exit'):
            break
        if not stripped:
            continue
        if stripped.startswith('/'):
            messages = handle_command(stripped, messages)
            continue

        messages.append({"role": "user", "content": user_input})
        checkpoints.begin_turn()

        message, usage = agent_turn(messages)

        # Turn is over: freeze this turn's undo point, clean up temp files,
        # and shrink the tool outputs already used this turn.
        checkpoints.commit_turn()
        history.sweep()
        history.strip(messages)

        if usage and compact.needed(usage):
            console.print("[dim purple]Context window full. Compacting history...[/dim purple]")
            with console.status("[bold purple]Summarizing old context...", spinner="bouncingBar"):
                messages = compact.compact(messages)
            console.print("[dim purple]Compaction complete.[/dim purple]")

        if message and message.content:
            console.print(Panel(Markdown(message.content), title="[bold purple]Agent[/bold purple]", border_style="purple"))

        print_usage(usage)


if __name__ == "__main__":
    main()