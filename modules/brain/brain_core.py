# ── brain_core.py ────────────────────────────────────────────────────
# The main UNIFIQ Brain page.
# User can dump thoughts, see categorized notes, browse by category.
# ─────────────────────────────────────────────────────────────────────

import streamlit as st
import uuid
from utils.date_utils import now_date_str, now_time_str, now_datetime_str
from database.sheets_client import get_all_rows, add_row, log_activity
from database.chroma_client import add_note_to_chroma, get_note_count
from ai.gemini_client import generate
from ai.embeddings_client import get_embedding
from config.settings import BRAIN_CATEGORIES


def categorize_note(text: str) -> str:
    """
    Asks Gemini to categorize a note into Work, Learning, or Personal.
    Returns one word: Work, Learning, or Personal.
    """
    prompt = f"""
You are categorizing a personal note.
Choose exactly ONE category from: Work, Learning, Personal.

Work = projects, tasks, goals, professional things
Learning = study notes, books, courses, concepts, ideas
Personal = thoughts, feelings, daily life, habits, reflection

Note: "{text}"

Reply with ONLY the category word. Nothing else.
"""
    result = generate(prompt).strip()
    # Make sure the result is one of our valid categories
    for cat in BRAIN_CATEGORIES:
        if cat.lower() in result.lower():
            return cat
    return "Personal"  # default if AI returns something unexpected


def save_note(content: str, category: str):
    """
    Saves a note to both Google Sheets and ChromaDB.

    Step 1: Save to Google Sheets (permanent storage)
    Step 2: Generate embedding (convert text to vector)
    Step 3: Save to ChromaDB (search index)
    """
    note_id = str(uuid.uuid4())[:8]  # short unique ID like "a3f7b2c1"
    date = now_date_str()
    time = now_time_str()

    # Step 1: Save to Google Sheets
    row = [note_id, content, category, date, time]
    add_row("brain_notes", row)

    # Step 2 + 3: Save to ChromaDB for search
    try:
        embedding = get_embedding(content)
        add_note_to_chroma(note_id, content, category, embedding)
    except Exception as e:
        st.warning(f"Note saved, but search index not updated: {e}")

    # Log to activity feed
    log_activity("Brain Note", f"Added note: {content[:50]}...")

    return note_id


def show():
    """
    Main function — renders the UNIFIQ Brain page.
    Called from app.py.
    """
    st.title("🧠 UNIFIQ Brain")
    st.caption("Dump any thought. UNIFIQ remembers it, categorizes it, and connects it.")

    # ── TABS ─────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["💭 Dump Thought", "📋 Browse Notes", "🔍 Ask My Brain"])

    # ── TAB 1: DUMP THOUGHT ──────────────────────────────────────────
    with tab1:
        st.subheader("What's on your mind?")
        st.caption("Write anything — an idea, something you learned, a quick thought. No need to organize.")

        note_input = st.text_area(
            "Your thought",
            placeholder="e.g. Good managers ask questions before giving answers...",
            height=120,
            label_visibility="collapsed"
        )

        col1, col2 = st.columns([2, 1])
        with col1:
            auto_cat = st.toggle("Auto-categorize with AI", value=True)
        with col2:
            if not auto_cat:
                manual_cat = st.selectbox("Category", BRAIN_CATEGORIES)

        if st.button("Save to Brain 🧠", type="primary", use_container_width=True):
            if not note_input.strip():
                st.warning("Please write something first.")
            else:
                with st.spinner("Thinking..."):
                    if auto_cat:
                        category = categorize_note(note_input)
                        st.info(f"AI categorized this as: **{category}**")
                    else:
                        category = manual_cat

                    save_note(note_input.strip(), category)
                    st.success(f"✅ Saved to {category} at {now_time_str()}")
                    st.rerun()

        # ── QUICK STATS ──────────────────────────────────────────────
        st.divider()
        all_notes = get_all_rows("brain_notes")
        total = len(all_notes)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Notes", total)
        c2.metric("Work", sum(1 for n in all_notes if n.get("category") == "Work"))
        c3.metric("Learning", sum(1 for n in all_notes if n.get("category") == "Learning"))
        c4.metric("Personal", sum(1 for n in all_notes if n.get("category") == "Personal"))

    # ── TAB 2: BROWSE NOTES ──────────────────────────────────────────
    with tab2:
        st.subheader("All Your Notes")

        all_notes = get_all_rows("brain_notes")

        if not all_notes:
            st.info("No notes yet. Go to 'Dump Thought' to add your first note.")
            return

        # Filter by category
        filter_cat = st.selectbox(
            "Filter by category",
            ["All"] + BRAIN_CATEGORIES
        )

        # Filter notes
        if filter_cat == "All":
            filtered = all_notes
        else:
            filtered = [n for n in all_notes if n.get("category") == filter_cat]

        # Show notes as cards
        st.write(f"Showing **{len(filtered)}** notes")
        st.divider()

        for note in reversed(filtered):  # newest first
            cat = note.get("category", "Personal")
            # Color emoji per category
            cat_emoji = {"Work": "💼", "Learning": "📚", "Personal": "🌱"}.get(cat, "📝")

            with st.expander(
                f"{cat_emoji} {note.get('content', '')[:60]}... — {note.get('date', '')}",
                expanded=False
            ):
                st.write(note.get("content", ""))
                st.caption(f"Category: {cat} | Saved: {note.get('date')} at {note.get('time')}")

    # ── TAB 3: ASK MY BRAIN ──────────────────────────────────────────
    with tab3:
        # Import here to avoid circular imports
        from modules.brain.brain_rag import ask_brain
        ask_brain()
