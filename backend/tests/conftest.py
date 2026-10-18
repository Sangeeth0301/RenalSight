import os

# keep background jobs and real AI providers out of the test runs
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("GROQ_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("XAI_API_KEY", "")
