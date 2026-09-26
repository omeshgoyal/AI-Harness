import os
from openai import OpenAI
from dotenv import load_dotenv
from tools import TOOL_SCHEMAS
from skills import skills_prompt

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)
MODEL = "deepseek/deepseek-v4.1-flash"

# (Keep imports and API setup...)

def get_system_prompt():
    return f"""You are a coding agent. Your job is to code. Always code.
Use the bash tool to inspect files, write_file to create them, and str_replace to edit them.
Use write_skill to teach yourself new capabilities.

For any task that takes more than one step, call write_todos first and plan it out. 
Send the whole list every time you call it - it replaces the old one. 
Keep exactly one task in_progress, mark it done the moment it is finished, and move the next one to in_progress in the same call.

The current list is injected back to you every turn inside <todos> tags.

You have skills available. Each one is a set of instructions for a task.
If a skill matches what the user wants, call read_skill first and follow it.

{skills_prompt()}

Answer back to the user once exploration is done.
"""

# (Keep call_llm function...)

def call_llm(messages):
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOL_SCHEMAS,
        max_tokens=4096  
    )

    message = response.choices[0].message
    
    prompt_details = getattr(response.usage, "prompt_tokens_details", None)
    cached_tokens = getattr(prompt_details, "cached_tokens", 0) if prompt_details else 0

    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "cached_tokens": cached_tokens,
        "completion_tokens": response.usage.completion_tokens,
    }

    return message, usage