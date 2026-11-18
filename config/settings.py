# ── settings.py ──────────────────────────────────────────────────────
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

def _get(key, default=""):
    """Read from st.secrets first, then .env"""
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

# ── GEMINI KEYS ──────────────────────────────────────────────────────
GEMINI_KEYS = []
for i in range(1, 6):
    key = _get(f"GEMINI_KEY_{i}")
    if key:
        GEMINI_KEYS.append(key)

# ── GROQ KEY ─────────────────────────────────────────────────────────
GROQ_API_KEY = _get("GROQ_API_KEY", "")

# ── GOOGLE SHEETS ────────────────────────────────────────────────────
GOOGLE_SHEETS_CREDENTIALS = _get("GOOGLE_SHEETS_CREDENTIALS", "sheets_creds.json")
SPREADSHEET_NAME = _get("SPREADSHEET_NAME", "unifiq-db")

# ── APP CONSTANTS ────────────────────────────────────────────────────
BRAIN_CATEGORIES = ["Work", "Learning", "Personal", "Technical", "Career"]
PROJECT_STATUSES = ["Active", "On Hold", "Completed"]
TASK_PRIORITIES = ["High", "Medium", "Low"]
TASK_STATUSES = ["To Do", "In Progress", "Done"]
GEMINI_MODEL = "gemini-1.5-flash"
GROQ_MODEL = "llama3-8b-8192"
EMBEDDING_MODEL = "models/text-embedding-004"
CHROMA_COLLECTION = "brain_notes"
CHROMA_PATH = "./knowledge_base/chroma_db"