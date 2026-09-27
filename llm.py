import os
import time
import random
from openai import OpenAI, APIError, APIConnectionError, RateLimitError
from dotenv import load_dotenv

import config
from skills import skills_prompt

load_dotenv()

if config.PROVIDER == "groq":
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_API_KEY"))
elif config.PROVIDER == "openrouter":
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"))
else:
    # Custom/AGENT_MODEL override: assume an OpenAI-compatible endpoint configured via env.
    client = OpenAI(
        base_url=os.getenv("AGENT_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=os.getenv("AGENT_API_KEY") or os.getenv("OPENROUTER_API_KEY"),
    )

MODEL = config.MODEL

# Running totals for the whole process lifetime, so the UI can show a session cost.
_TOTALS = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}


class BudgetExceeded(Exception):
    """Raised instead of calling the API once the configured spend cap is hit."""


def get_totals():
    return dict(_TOTALS)


def _price_for(model):
    return config.PRICES.get(model, config.DEFAULT_PRICE)


def _record_cost(model, usage):
    in_price, out_price = _price_for(model)
    cost = (usage["prompt_tokens"] / 1_000_000 * in_price) + (
        usage["completion_tokens"] / 1_000_000 * out_price
    )
    _TOTALS["prompt_tokens"] += usage["prompt_tokens"]
    _TOTALS["completion_tokens"] += usage["completion_tokens"]
    _TOTALS["cost_usd"] += cost
    usage["cost_usd"] = cost
    usage["session_cost_usd"] = _TOTALS["cost_usd"]
    return usage


def get_system_prompt():
    return f"""You are a coding agent. Your job is to code.
Only use the `write_file` or `str_replace` tools to modify project files if the user explicitly asks you to.
Otherwise, output the code as markdown blocks in your response. 
If the code is very long, use `write_file` to save it to `static/downloads/<filename>` and provide a markdown download link (e.g., `[Download <filename>](/static/downloads/<filename>)`) instead of polluting the chat with massive code blocks.
Use the bash tool to inspect files.
Use write_skill to teach yourself new capabilities.

For any task that takes more than one step, call write_todos first and plan it out.
Send the whole list every time you call it - it replaces the old one.
Keep exactly one task in_progress, mark it done the moment it is finished, and move the next one to in_progress in the same call.

When you need to understand how something works - where a feature lives, how data flows - send a task subagent instead of grepping your way there yourself. It explores in its own context window and hands you back just the findings.

The current list is injected back to you every turn inside <todos> tags.

You have skills available. Each one is a set of instructions for a task.
If a skill matches what the user wants, call read_skill first and follow it.

{skills_prompt()}

Answer back to the user once exploration is done.
"""


def call_llm(messages, tools=None, model=None):
    """Call the chat completion endpoint with retries and cost tracking.

    Raises BudgetExceeded if a spend cap is configured and already hit, and
    re-raises the last error if every retry is exhausted.
    """
    if config.BUDGET_LIMIT_USD and _TOTALS["cost_usd"] >= config.BUDGET_LIMIT_USD:
        raise BudgetExceeded(
            f"Session cost estimate (${_TOTALS['cost_usd']:.2f}) has reached the "
            f"configured budget cap (${config.BUDGET_LIMIT_USD:.2f})."
        )

    if tools is None:
        from tools import TOOL_SCHEMAS
        active_tools = TOOL_SCHEMAS
    else:
        active_tools = tools

    use_model = model or MODEL
    last_error = None
    for attempt in range(config.LLM_RETRIES):
        try:
            response = client.chat.completions.create(
                model=use_model,
                messages=messages,
                tools=active_tools,
                max_tokens=config.LLM_MAX_TOKENS,
            )
            break
        except (RateLimitError, APIConnectionError, APIError) as e:
            last_error = e
            if attempt == config.LLM_RETRIES - 1:
                raise
            # Exponential backoff with jitter so a burst of clients doesn't retry in lockstep.
            time.sleep(min(2 ** attempt + random.random(), 20))
    else:
        raise last_error

    message = response.choices[0].message

    prompt_details = getattr(response.usage, "prompt_tokens_details", None)
    cached_tokens = getattr(prompt_details, "cached_tokens", 0) if prompt_details else 0

    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "cached_tokens": cached_tokens,
        "completion_tokens": response.usage.completion_tokens,
    }
    usage = _record_cost(use_model, usage)

    return message, usage