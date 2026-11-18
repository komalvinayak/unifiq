import os
from dotenv import load_dotenv

load_dotenv()

# ── GEMINI KEYS ──────────────────────────────────────────────────────
GEMINI_KEYS = []
for i in range(1, 6):
    key = os.getenv(f"GEMINI_KEY_{i}")
    if key:
        GEMINI_KEYS.append(key)

# ── GROQ KEY ─────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── GOOGLE SHEETS ────────────────────────────────────────────────────
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "sheets_creds.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "unifiq-db")

# ── APP CONSTANTS ────────────────────────────────────────────────────
BRAIN_CATEGORIES = ["Work", "Learning", "Personal", "Technical", "Career"]
PROJECT_STATUSES = ["Active", "On Hold", "Completed"]
TASK_PRIORITIES = ["High", "Medium", "Low"]
TASK_STATUSES = ["To Do", "In Progress", "Done"]
GEMINI_MODEL = "gemini-2.0-flash"
GROQ_MODEL = "openai/gpt-oss-120b"
EMBEDDING_MODEL = "models/text-embedding-004"
CHROMA_COLLECTION = "brain_notes"
CHROMA_PATH = "./knowledge_base/chroma_db"

# All models available in the sidebar dropdown
# provider: "gemini" uses GEMINI_KEYS rotation; "groq" uses GROQ_API_KEY directly
AVAILABLE_MODELS = [
    # ── Gemini ────────────────────────────────────────────────────────
    {"display": "Gemini 2.0 Flash",     "provider": "gemini", "model_id": "gemini-2.0-flash"},
    {"display": "Gemini 1.5 Flash",     "provider": "gemini", "model_id": "gemini-1.5-flash"},
    {"display": "Gemini 1.5 Pro",       "provider": "gemini", "model_id": "gemini-1.5-pro"},
    # ── Groq — OpenAI ─────────────────────────────────────────────────
    {"display": "GPT-OSS 120B (Groq)",  "provider": "groq",   "model_id": "openai/gpt-oss-120b"},
    {"display": "GPT-OSS 20B (Groq)",   "provider": "groq",   "model_id": "openai/gpt-oss-20b"},
    # ── Groq — Meta Llama ─────────────────────────────────────────────
    {"display": "Llama 3 70B (Groq)",   "provider": "groq",   "model_id": "llama3-70b-8192"},
    {"display": "Llama 3 8B (Groq)",    "provider": "groq",   "model_id": "llama3-8b-8192"},
    {"display": "Llama 3.1 8B (Groq)",  "provider": "groq",   "model_id": "llama-3.1-8b-instant"},
]