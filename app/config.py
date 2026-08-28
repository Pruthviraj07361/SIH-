"""
Central config. Loads secrets from environment variables (via a local .env file).

>>> THIS IS WHERE YOUR API KEY GOES <<<
Do NOT paste your key into this file. Instead:
  1. Copy .env.example -> .env  (in the project root, next to this app/ folder)
  2. Open .env and set:
        GROQ_API_KEY=gsk_your_actual_key_here
        SUPABASE_URL=https://your-project-ref.supabase.co
        SUPABASE_KEY=your_actual_supabase_key_here
  3. That's it — this file reads it automatically at startup.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # reads the .env file in the project root into os.environ

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Current recommended Groq model per the project spec (check
# https://console.groq.com/docs/models periodically — these get deprecated).
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

# Fail loudly and immediately if the key is missing, instead of failing deep
# inside a request later with a confusing error.
if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
    )
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL / SUPABASE_KEY not set. Copy .env.example to .env and add them."
    )
