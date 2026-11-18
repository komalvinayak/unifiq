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
GROQ_MODEL = "llama3-70b-8192"
EMBEDDING_MODEL = "models/text-embedding-004"
CHROMA_COLLECTION = "brain_notes"
CHROMA_PATH = "./knowledge_base/chroma_db"