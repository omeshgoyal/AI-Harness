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

console = Console()

def trim_history(messages, max_length=15):
    """
    Keeps the system prompt and the most recent messages. 
    Slices cleanly at a 'user' message to avoid splitting tool calls from their results.
    """
    if len(messages) <= max_length:
        return messages
    
    safe_index = 1
    for i in range(len(messages) - max_length + 1, len(messages)):
        role = messages[i].get("role") if isinstance(messages[i], dict) else messages[i].role
        if role == "user":
            safe_index = i
            break
            
    return [messages[0]] + messages[safe_index:]

def print_usage(usage):
    """Formats the token usage nicely at the bottom of the response."""
    if not usage:
        return
    
    prompt = usage.get('prompt_tokens', 0)
    cached = usage.get('cached_tokens', 0)
    completion = usage.get('completion_tokens', 0)
    
    # Calculate cache hit percentage
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
        messages = trim_history(messages)

        with console.status(f"[bold cyan]{active_form().capitalize()}...", spinner="dots") as status:
            while True:
                status.update(f"[bold cyan]{active_form().capitalize()}...")
                
                messages[0]["content"] = get_system_prompt()
                injection = reminder()
                
                try:
                    message, usage = call_llm(messages + [injection])
                except Exception as e:
                    status.stop()
                    console.print(f"\n[bold red]API Error:[/bold red] {str(e)}")
                    # Remove the last user message so they can re-try without duplicate prompts
                    messages.pop()
                    usage = None
                    message = None
                    break
                
                messages.append(message)

                if getattr(message, 'tool_calls', None):
                    for tool_call in message.tool_calls:
                        func_name = tool_call.function.name
                        
                        if func_name in TOOLS:
                            try:
                                args = json.loads(tool_call.function.arguments)
                            except json.JSONDecodeError:
                                args = {}
                            
                            status.stop()
                            
                            # Permission check[cite: 24]
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

        if message and message.content:
            console.print(Panel(Markdown(message.content), title="[bold purple]Agent[/bold purple]", border_style="purple"))
        
        print_usage(usage)

if __name__ == "__main__":
    main()