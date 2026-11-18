# ── settings.py ──────────────────────────────────────────────────────
# Loads all API keys from .env file
# Every other file imports from here — keys are never hardcoded
# ─────────────────────────────────────────────────────────────────────

import os
from dotenv import load_dotenv

# Load .env file into environment variables
load_dotenv()

# ── GEMINI KEYS (multiple for rotation) ─────────────────────────────
# We collect all keys into a list — only add non-empty ones
GEMINI_KEYS = []
for i in range(1, 6):  # checks GEMINI_KEY_1 through GEMINI_KEY_5
    key = os.getenv(f"GEMINI_KEY_{i}")
    if key:
        GEMINI_KEYS.append(key)

# ── GROQ KEY (backup when all Gemini keys are rate limited) ──────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── GOOGLE SHEETS ────────────────────────────────────────────────────
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "sheets_creds.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "unifiq-db")

# ── APP CONSTANTS ────────────────────────────────────────────────────
# Categories for brain notes
BRAIN_CATEGORIES = ["Work", "Learning", "Personal"]

# Project statuses
PROJECT_STATUSES = ["Active", "On Hold", "Completed"]

# Task priorities
TASK_PRIORITIES = ["High", "Medium", "Low"]

# Task statuses
TASK_STATUSES = ["To Do", "In Progress", "Done"]

# Gemini model to use
GEMINI_MODEL = "gemini-1.5-flash"

# Groq model to use (free, fast)
GROQ_MODEL = "llama3-8b-8192"

# Embedding model (Google)
EMBEDDING_MODEL = "models/text-embedding-004"

# ChromaDB collection name
CHROMA_COLLECTION = "brain_notes"

# ChromaDB local path
CHROMA_PATH = "./knowledge_base/chroma_db"
