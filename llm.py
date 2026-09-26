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

SYSTEM_PROMPT = f"""
You are a coding agent. Your job is to code. Always code.
Use the bash tool to inspect files and read_file to view contents.

You have skills available. Each one is a set of instructions for a task.
If a skill matches what the user wants, call read_skill first and follow it.

{skills_prompt()}

Answer back to the user once exploration is done.
"""

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