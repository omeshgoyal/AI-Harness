import json
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text

from llm import get_system_prompt, call_llm
from tools import TOOLS
from context import reminder
from todos import active_form
from permissions import check
import history
import compact

console = Console()

def print_usage(usage):
    """Formats the token usage nicely at the bottom of the response."""
    if not usage:
        return
    
    prompt = usage.get('prompt_tokens', 0)
    cached = usage.get('cached_tokens', 0)
    completion = usage.get('completion_tokens', 0)
    
    cache_pct = (cached / prompt * 100) if prompt > 0 else 0
    stats = Text(f"Tokens ⬩ Prompt: {prompt} ({cache_pct:.0f}% cached) ⬩ Completion: {completion}", style="dim cyan")
    console.print(stats)

def main():
    console.print(Panel("[bold green]Agent initialized.[/bold green]\n[dim]Type 'exit' to quit. Type '/clear' to reset history.[/dim]", expand=False))
    
    messages = [{"role": "system", "content": get_system_prompt()}]

    while True:
        try:
            user_input = console.input("\n[bold blue]You:[/bold blue] ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Shutting down...[/dim]")
            break
            
        input_lower = user_input.strip().lower()
        if input_lower in ['quit', 'exit']:
            break
        elif input_lower == '/clear':
            messages = [{"role": "system", "content": get_system_prompt()}]
            console.print("[dim green]History cleared. Starting fresh.[/dim green]")
            continue
        elif not input_lower:
            continue

        messages.append({"role": "user", "content": user_input})

        with console.status(f"[bold cyan]{active_form().capitalize()}...", spinner="dots") as status:
            while True:
                status.update(f"[bold cyan]{active_form().capitalize()}...")
                
                messages[0]["content"] = get_system_prompt()
                injection = reminder()
                
                # Check emergency fit before calling
                if history.fit(messages):
                    console.print("[dim yellow]Note: Dropped old tool output to make this request fit.[/dim yellow]")
                
                try:
                    message, usage = call_llm(messages + [injection])
                except Exception as e:
                    status.stop()
                    console.print(f"\n[bold red]API Error:[/bold red] {str(e)}")
                    
                    # FIX: Only pop if the last message was from the user. 
                    # If it was a tool result, leave the history intact so the user can type "retry".
                    if messages and messages[-1].get("role") == "user":
                        messages.pop()
                        
                    usage = None
                    message = None
                    break
                
                # Convert Pydantic object to dict so history and compact can process it cleanly
                msg_dict = message.model_dump(exclude_none=True)
                messages.append(msg_dict)

                if getattr(message, 'tool_calls', None):
                    for tool_call in message.tool_calls:
                        func_name = tool_call.function.name
                        
                        if func_name in TOOLS:
                            try:
                                args = json.loads(tool_call.function.arguments)
                            except json.JSONDecodeError:
                                args = {}
                            
                            status.stop()
                            action, reason = check(func_name, args)
                            
                            tool_result = ""
                            if action == "deny":
                                console.print(f"[bold red]⛔ Blocked:[/bold red] {reason}")
                                tool_result = f"Blocked by policy: {reason}"
                            elif action == "ask":
                                ans = console.input(f"[bold yellow]⚠️ Agent wants to {reason}. Allow? (y/n): [/bold yellow]")
                                if ans.strip().lower() != 'y':
                                    console.print("[dim red]Denied by user.[/dim red]")
                                    tool_result = "The user denied this tool call."
                                else:
                                    console.print(f"[dim yellow]⚡ Executing '{func_name}'...[/dim yellow]")
                                    tool_result = TOOLS[func_name](**args)
                            else:
                                console.print(f"[dim yellow]⚡ Executing '{func_name}'...[/dim yellow]")
                                tool_result = TOOLS[func_name](**args)
                            
                            status.start()
                            
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": func_name,
                                "content": str(tool_result)
                            })
                        else:
                            console.print(f"[bold red]System: Model attempted to call unknown tool '{func_name}'[/bold red]")
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": func_name,
                                "content": "Error: Tool not found."
                            })
                else:
                    break 

        # Turn is over: clean up temp files and shrink the tool outputs in the history array
        history.sweep()
        history.strip(messages)

        # Trigger compaction sub-agent if the window is getting too large
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