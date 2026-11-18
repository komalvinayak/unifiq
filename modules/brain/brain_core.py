# ── brain_core.py ────────────────────────────────────────────────────
# The main UNIFIQ Brain page.
# User can dump thoughts, see categorized notes, browse by category.
#
# KEY IMPROVEMENT: Embeddings are now saved to Google Sheets column 6.
# On startup, rebuild reads embeddings from Sheets — zero API calls.
# No more "Rebuild Brain Index" needed after every restart.
# ─────────────────────────────────────────────────────────────────────

import json
import streamlit as st
import uuid
from utils.date_utils import now_date_str, now_time_str
from database.sheets_client import get_all_rows, add_row, update_row, delete_row, log_activity
from database.chroma_client import add_note_to_chroma, get_note_count, get_related_notes
from ai.gemini_client import generate
from ai.embeddings_client import get_embedding
from config.settings import BRAIN_CATEGORIES


def categorize_note(text: str) -> str:
    """
    Asks Gemini to categorize a note.
    Returns one word from BRAIN_CATEGORIES.
    """
    prompt = f"""
You are categorizing a personal note for an MBA student.
Choose exactly ONE category from: Work, Learning, Personal, Technical, Career.

Work = MBA projects, case studies, assignments, group work, professional tasks, consulting, strategy
Learning = studying, books, courses, business concepts, frameworks (Porter's, BCG, SWOT), finance, marketing, economics, any subject being learned
Technical = programming, AI, ML, data science, cybersecurity, networking, databases, APIs, Python, code, software tools, RAG, cloud, hacking, security
Career = interview prep, job search, placements, networking, resume, LinkedIn, self-improvement, career goals, salary
Personal = personal thoughts, feelings, daily life, habits, health, family, hobbies, non-academic reflections

IMPORTANT RULES:
- "learn X" or "study X" where X is a technical subject → Technical
- "learn X" where X is a business concept → Learning
- Anything about cybersecurity, hacking, networks, security → Technical
- When in doubt between Learning and Technical, pick Technical for tech topics

Note: "{text}"

Reply with ONLY one word: Work, Learning, Personal, Technical, or Career.
"""
    result = generate(prompt).strip()
    for cat in BRAIN_CATEGORIES:
        if cat.lower() in result.lower():
            return cat
    return "Personal"


def save_note(content: str, category: str):
    """
    Saves a note to Google Sheets with its embedding in column 6.

    Columns: note_id | content | category | date | time | embedding

    Why store embedding in Sheets?
    - App restarts wipe memory (session_state)
    - Re-generating embeddings on every restart = slow + uses API quota
    - Storing in Sheets = instant rebuild, zero API calls on startup
    """
    note_id = str(uuid.uuid4())[:8]
    date = now_date_str()
    time = now_time_str()

    # Generate embedding first
    embedding = None
    embedding_str = ""
    try:
        embedding = get_embedding(content)
        embedding_str = json.dumps(embedding)  # store as JSON string in Sheets
    except Exception as e:
        st.warning(f"⚠️ Embedding failed (note saved without search index): {e}")

    # Save to Google Sheets — 6 columns now
    row = [note_id, content, category, date, time, embedding_str]
    add_row("brain_notes", row)

    # Add to in-memory vector store for immediate use
    if embedding:
        add_note_to_chroma(note_id, content, category, embedding)

    log_activity("Brain Note", f"Added note: {content[:50]}...")
    return note_id


def _get_note_row_number(note_id: str, all_notes: list) -> int:
    """Returns the 1-based Sheets row number for a note (header = row 1, data starts at row 2)."""
    for i, n in enumerate(all_notes, start=2):
        if str(n.get("note_id", "")) == str(note_id):
            return i
    return -1


def _get_vector_store_entry(note_id: str) -> dict | None:
    """Returns the vector store entry for a note, or None."""
    store = st.session_state.get("vector_store", [])
    for entry in store:
        if entry["id"] == note_id:
            return entry
    return None


def show():
    """
    Main function — renders the UNIFIQ Brain page.
    Called from app.py.
    """
    st.title("🧠 UNIFIQ Brain")
    st.caption("Dump any thought. UNIFIQ remembers it, categorizes it, and connects it.")

    # ── Load notes ONCE per session (avoid Sheets rate limit) ────────
    if "brain_notes_cache" not in st.session_state:
        st.session_state.brain_notes_cache = get_all_rows("brain_notes")
    all_notes = st.session_state.brain_notes_cache

    # ── TABS ─────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "💭 Dump Thought", "📋 Browse Notes", "🔍 Ask My Brain", "📥 Bulk Import"
    ])

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
                    st.session_state.chroma_note_count = get_note_count()
                    st.session_state.pop("brain_notes_cache", None)
                    st.success(f"✅ Saved to {category} at {now_time_str()}")
                    st.rerun()

        # ── QUICK STATS ──────────────────────────────────────────────
        st.divider()
        total = len(all_notes)
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total", total)
        c2.metric("💼 Work",     sum(1 for n in all_notes if n.get("category") == "Work"))
        c3.metric("📚 Learning", sum(1 for n in all_notes if n.get("category") == "Learning"))
        c4.metric("💻 Technical",sum(1 for n in all_notes if n.get("category") == "Technical"))
        c5.metric("🎯 Career",   sum(1 for n in all_notes if n.get("category") == "Career"))
        c6.metric("🌱 Personal", sum(1 for n in all_notes if n.get("category") == "Personal"))

    # ── TAB 2: BROWSE NOTES ──────────────────────────────────────────
    with tab2:
        st.subheader("All Your Notes")

        if not all_notes:
            st.info("No notes yet. Go to 'Dump Thought' to add your first note.")
            return

        # ── FILTERS ──────────────────────────────────────────────────
        col_search, col_filter = st.columns([2, 1])
        with col_search:
            search_query = st.text_input(
                "Search notes",
                placeholder="🔍 Type to filter by keyword...",
                label_visibility="collapsed"
            )
        with col_filter:
            filter_cat = st.selectbox("Category", ["All"] + BRAIN_CATEGORIES,
                                      label_visibility="collapsed")

        # Apply filters
        filtered = all_notes
        if filter_cat != "All":
            filtered = [n for n in filtered if n.get("category") == filter_cat]
        if search_query.strip():
            q = search_query.strip().lower()
            filtered = [n for n in filtered if q in n.get("content", "").lower()]

        st.write(f"Showing **{len(filtered)}** of {len(all_notes)} notes")
        st.divider()

        cat_emoji_map = {
            "Work": "💼", "Learning": "📚", "Personal": "🌱",
            "Technical": "💻", "Career": "🎯"
        }

        for note in reversed(filtered):
            cat      = note.get("category", "Personal")
            note_id  = str(note.get("note_id", ""))
            content  = note.get("content", "")
            cat_emoji = cat_emoji_map.get(cat, "📝")

            with st.expander(
                f"{cat_emoji} {content[:60]}{'…' if len(content) > 60 else ''} — {note.get('date', '')}",
                expanded=False
            ):
                # ── EDIT / VIEW toggle ───────────────────────────────
                edit_key = f"editing_{note_id}"
                if st.session_state.get(edit_key):
                    # Edit mode
                    edited_content = st.text_area(
                        "Edit note", value=content, height=100, key=f"edit_text_{note_id}"
                    )
                    edited_cat = st.selectbox(
                        "Category", BRAIN_CATEGORIES,
                        index=BRAIN_CATEGORIES.index(cat) if cat in BRAIN_CATEGORIES else 0,
                        key=f"edit_cat_{note_id}"
                    )
                    save_col, cancel_col = st.columns(2)
                    if save_col.button("💾 Save", key=f"save_{note_id}", type="primary"):
                        row_num = _get_note_row_number(note_id, all_notes)
                        if row_num > 0:
                            # Re-embed if content changed
                            embedding_str = note.get("embedding", "")
                            if edited_content.strip() != content:
                                try:
                                    new_emb = get_embedding(edited_content.strip())
                                    embedding_str = json.dumps(new_emb)
                                except Exception:
                                    pass
                            update_row("brain_notes", row_num, [
                                note_id, edited_content.strip(), edited_cat,
                                note.get("date"), note.get("time"), embedding_str
                            ])
                            log_activity("Brain Note", f"Edited note: {edited_content[:50]}")
                            st.session_state.pop(edit_key, None)
                            st.session_state.pop("brain_notes_cache", None)
                            st.session_state.pop("chroma_initialized", None)
                            st.success("Note updated.")
                            st.rerun()
                    if cancel_col.button("✕ Cancel", key=f"cancel_{note_id}"):
                        st.session_state.pop(edit_key, None)
                        st.rerun()
                else:
                    # Read mode
                    st.write(content)
                    st.caption(f"Category: {cat} | Saved: {note.get('date')} at {note.get('time')}")

                    action_col, del_col = st.columns([1, 1])
                    if action_col.button("✏️ Edit", key=f"open_edit_{note_id}"):
                        st.session_state[edit_key] = True
                        st.rerun()

                    if del_col.button("🗑️ Delete", key=f"del_{note_id}"):
                        st.session_state[f"confirm_del_{note_id}"] = True
                        st.rerun()

                    if st.session_state.get(f"confirm_del_{note_id}"):
                        st.warning("Delete this note? This cannot be undone.")
                        yes_col, no_col = st.columns(2)
                        if yes_col.button("Yes, delete", key=f"yes_del_{note_id}", type="primary"):
                            row_num = _get_note_row_number(note_id, all_notes)
                            if row_num > 0:
                                delete_row("brain_notes", row_num)
                                log_activity("Brain Note", f"Deleted note: {content[:50]}")
                                st.session_state.pop(f"confirm_del_{note_id}", None)
                                st.session_state.pop("brain_notes_cache", None)
                                st.session_state.pop("chroma_initialized", None)
                                st.success("Note deleted.")
                                st.rerun()
                        if no_col.button("Cancel", key=f"no_del_{note_id}"):
                            st.session_state.pop(f"confirm_del_{note_id}", None)
                            st.rerun()

                    # ── RELATED NOTES ────────────────────────────────
                    entry = _get_vector_store_entry(note_id)
                    if entry and entry.get("embedding"):
                        related = get_related_notes(entry["embedding"], note_id, n_results=3)
                        related = [(t, s) for t, s in related if s >= 0.55]
                        if related:
                            st.divider()
                            st.caption("**🔗 Related notes:**")
                            for rel_text, rel_score in related:
                                pct = int(rel_score * 100)
                                st.markdown(
                                    f"<div style='padding:6px 10px; margin:4px 0; "
                                    f"background:rgba(255,255,255,0.04); border-radius:6px; "
                                    f"border-left:3px solid #475569; font-size:0.88rem; color:#CBD5E1;'>"
                                    f"<span style='color:#64748B; font-size:0.78rem;'>{pct}% similar</span><br>"
                                    f"{rel_text[:120]}{'…' if len(rel_text) > 120 else ''}</div>",
                                    unsafe_allow_html=True
                                )

    # ── TAB 3: ASK MY BRAIN ──────────────────────────────────────────
    with tab3:
        from modules.brain.brain_rag import ask_brain
        ask_brain()

    # ── TAB 4: BULK IMPORT ───────────────────────────────────────────
    with tab4:
        st.subheader("Bulk Import Notes")
        st.caption(
            "Paste multiple thoughts — one per line (or paste a WhatsApp export). "
            "Each non-empty line becomes a separate note."
        )

        bulk_input = st.text_area(
            "Paste notes here",
            placeholder=(
                "Good managers ask questions before giving answers\n"
                "Porter's Five Forces: supplier power, buyer power, substitutes, new entrants, rivalry\n"
                "Finish MBA case study by Friday\n"
                "Learn numpy broadcasting for data science"
            ),
            height=200,
            label_visibility="collapsed"
        )

        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            bulk_auto_cat = st.toggle("Auto-categorize each note", value=True, key="bulk_auto_cat")
        with col_opt2:
            if not bulk_auto_cat:
                bulk_manual_cat = st.selectbox("Category for all", BRAIN_CATEGORIES, key="bulk_cat")

        if bulk_input.strip():
            # Preview the lines
            lines = [l.strip() for l in bulk_input.splitlines() if l.strip()]
            # Strip WhatsApp timestamp prefixes like "[18/11/2026, 19:04:00] Name: "
            import re
            cleaned = []
            for line in lines:
                # WhatsApp format: [DD/MM/YYYY, HH:MM:SS] Name: message
                m = re.match(r"^\[[\d/,: ]+\]\s*[^:]+:\s*(.+)$", line)
                cleaned.append(m.group(1).strip() if m else line)

            st.write(f"**{len(cleaned)} notes** ready to import:")
            for i, line in enumerate(cleaned[:5], 1):
                st.write(f"{i}. {line[:80]}{'…' if len(line) > 80 else ''}")
            if len(cleaned) > 5:
                st.caption(f"…and {len(cleaned) - 5} more")

            if st.button(f"Import {len(cleaned)} notes 🧠", type="primary", use_container_width=True):
                progress_bar = st.progress(0, text="Starting import…")
                saved = 0
                failed = 0

                for i, line in enumerate(cleaned):
                    progress_bar.progress((i + 1) / len(cleaned), text=f"Saving note {i+1}/{len(cleaned)}…")
                    try:
                        if bulk_auto_cat:
                            category = categorize_note(line)
                        else:
                            category = bulk_manual_cat
                        save_note(line, category)
                        saved += 1
                    except Exception as e:
                        failed += 1
                        st.warning(f"Skipped: {line[:60]} — {e}")

                st.session_state.chroma_note_count = get_note_count()
                st.session_state.pop("brain_notes_cache", None)
                progress_bar.empty()

                if failed == 0:
                    st.success(f"✅ Imported all {saved} notes!")
                else:
                    st.warning(f"Imported {saved} notes. {failed} failed — see warnings above.")
                st.rerun()
        else:
            st.info("Paste some text above to get started.")