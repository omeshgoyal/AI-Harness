import os

# Context window settings
CONTEXT_WINDOW = int(os.getenv("CONTEXT_WINDOW", 32000))
COMPACT_AT = 0.8
COMPACT_TO = 0.2

# Dynamic model routing
if os.getenv("GROQ_API_KEY"):
    MODEL = "llama-3.3-70b-versatile"
else:
    MODEL = "deepseek/deepseek-v4.1-flash"