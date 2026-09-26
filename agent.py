import json
from rich.console import Console
from rich.panel import Panel
from llm import get_system_prompt, call_llm
from tools import TOOLS
from context import reminder

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

def main():
    console.print(Panel("[bold green]Chat started. Type 'exit' to quit.[/bold green]", expand=False))
    
    messages = [{"role": "system", "content": get_system_prompt()}]

    while True:
        try:
            user_input = console.input("\n[bold blue]You:[/bold blue] ")
        except (KeyboardInterrupt, EOFError):
            break
            
        if user_input.lower() in ['quit', 'exit']:
            break

        messages.append({"role": "user", "content": user_input})
        messages = trim_history(messages)

        with console.status("[bold cyan]Agent is thinking...", spinner="dots"):
            while True:
                messages[0]["content"] = get_system_prompt()
                
                # Fetch the dynamic late injection
                injection = reminder()
                
                # Append it temporarily for this call only
                message, usage = call_llm(messages + [injection])
                messages.append(message)

                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        func_name = tool_call.function.name
                        
                        if func_name in TOOLS:
                            args = json.loads(tool_call.function.arguments)
                            console.print(f"[dim yellow]System: Executing '{func_name}' with args: {args}[/dim yellow]")
                            
                            tool_result = TOOLS[func_name](**args)
                            
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

        console.print(Panel(message.content, title="[bold purple]Agent[/bold purple]", border_style="purple"))
        console.print(f"[dim]Tokens: {usage}[/dim]")

if __name__ == "__main__":
    main()