import json
from rich.console import Console
from rich.panel import Panel
from llm import SYSTEM_PROMPT, call_llm
from tools import TOOLS

console = Console()

def main():
    console.print(Panel("[bold green]Chat started. Type 'exit' to quit.[/bold green]", expand=False))
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = console.input("\n[bold blue]You:[/bold blue] ")
        except (KeyboardInterrupt, EOFError):
            break
            
        if user_input.lower() in ['quit', 'exit']:
            break

        messages.append({"role": "user", "content": user_input})

        with console.status("[bold cyan]Agent is thinking...", spinner="dots"):
            while True:
                message, usage = call_llm(messages)
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