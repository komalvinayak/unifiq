# ── brain_core.py ────────────────────────────────────────────────────
# Mufakkir — main brain page.
# Features: confidence-scored categorization, proactive surfacing,
#           contradiction detector, full IST timestamps.
# ─────────────────────────────────────────────────────────────────────

import json
import re
import streamlit as st
import uuid
from utils.date_utils import now_date_str, now_time_str, now_ist
from database.sheets_client import get_all_rows, add_row, update_row, delete_row, log_activity
from database.chroma_client import add_note_to_chroma, get_note_count, get_related_notes, search_similar_notes_with_scores
from ai.gemini_client import generate
from ai.embeddings_client import get_embedding
from config.settings import BRAIN_CATEGORIES


CAT_EMOJI = {
    "Work": "💼", "Learning": "📚", "Personal": "🌱",
    "Technical": "💻", "Career": "🎯",
}
_CAT_COLOR = {
    "Work": "#4F46E5", "Learning": "#16A34A", "Personal": "#D97706",
    "Technical": "#7C3AED", "Career": "#DC2626",
}


# ── CATEGORIZATION WITH CONFIDENCE ───────────────────────────────────

def categorize_note_with_confidence(text: str) -> tuple[str, int]:
    """
    Returns (category, confidence 0-100).
    Confidence > 70 → suggest to user; < 70 → ask user to pick manually.
    """
    prompt = f"""You are categorizing a personal note for an MBA student.

Categories:
- Work: MBA projects, case studies, assignments, group work, professional tasks, consulting, strategy
- Learning: studying, books, courses, business concepts, frameworks, finance, marketing, economics
- Technical: programming, AI, ML, data science, cybersecurity, networking, databases, APIs, Python, code, software tools
- Career: interview prep, job search, placements, networking, resume, LinkedIn, career goals
- Personal: personal thoughts, feelings, daily life, habits, health, family, hobbies

Note: "{text}"

Reply with ONLY this exact format (no other text):
CATEGORY: <one of Work/Learning/Personal/Technical/Career>
CONFIDENCE: <integer 0-100>"""

    result = generate(prompt).strip()
    category = "Personal"
    confidence = 50

    for line in result.splitlines():
        line = line.strip()
        if line.upper().startswith("CATEGORY:"):
            val = line.split(":", 1)[1].strip()
            for cat in BRAIN_CATEGORIES:
                if cat.lower() in val.lower():
                    category = cat
                    break
        elif line.upper().startswith("CONFIDENCE:"):
            try:
                confidence = max(0, min(100, int(re.sub(r"[^0-9]", "", line.split(":", 1)[1]))))
            except Exception:
                pass

    return category, confidence


def categorize_note(text: str) -> str:
    """Simple wrapper — returns category only (used by sidebar quick capture)."""
    cat, _ = categorize_note_with_confidence(text)
    return cat


# ── SAVE NOTE ─────────────────────────────────────────────────────────

def save_note(content: str, category: str, confidence: int = 100) -> str:
    """
    Saves a note to Google Sheets.
    Columns: note_id | content | category | date | time | embedding
             | confidence_score | connected_note_ids | day_of_week | created_time
    """
    note_id = str(uuid.uuid4())[:8]
    ist_now = now_ist()
    date_str = ist_now.strftime("%d %b %Y")
    time_str = ist_now.strftime("%I:%M %p")
    day_of_week = ist_now.strftime("%A")
    created_time = ist_now.strftime("%Y-%m-%d %H:%M:%S")

    embedding = None
    embedding_str = ""
    connected_ids = ""

    try:
        embedding = get_embedding(content)
        embedding_str = json.dumps(embedding)
    except Exception as e:
        st.warning(f"⚠️ Embedding failed (note saved without search index): {e}")

    # Find top 3 similar note IDs for connected_note_ids column
    if embedding:
        try:
            similar = search_similar_notes_with_scores(embedding, n_results=3)
            connected_ids = ",".join([
                _find_note_id_by_content(c, st.session_state.get("brain_notes_cache", []))
                for c, s in similar if s > 0.4
            ])
        except Exception:
            connected_ids = ""

    row = [
        note_id, content, category, date_str, time_str, embedding_str,
        confidence, connected_ids, day_of_week, created_time,
    ]
    add_row("brain_notes", row)

    if embedding:
        add_note_to_chroma(note_id, content, category, embedding)

    log_activity("Brain Note", f"Added: {content[:50]}")
    return note_id


def _find_note_id_by_content(content: str, notes: list) -> str:
    for n in notes:
        if n.get("content", "") == content:
            return str(n.get("note_id", ""))
    return ""


# ── PROACTIVE SURFACING ───────────────────────────────────────────────

def get_related_to_input(text: str, n: int = 3) -> list[tuple[str, str, float]]:
    """
    Returns top N related past notes for the given input text.
    Returns list of (content, category, score).
    """
    if len(text.strip()) < 10:
        return []
    try:
        emb = get_embedding(text)
        results = search_similar_notes_with_scores(emb, n_results=n)
        notes_cache = st.session_state.get("brain_notes_cache", [])
        out = []
        for content, score in results:
            if score > 0.35:
                cat = next(
                    (n.get("category", "") for n in notes_cache
                     if n.get("content", "") == content), ""
                )
                out.append((content, cat, score))
        return out
    except Exception:
        return []


# ── CONTRADICTION DETECTOR ────────────────────────────────────────────

def check_contradiction(new_note: str, category: str, all_notes: list) -> dict | None:
    """
    Checks if new_note contradicts any past note in the same category.
    Returns {date, content} of contradicting note, or None.
    """
    same_cat = [n for n in all_notes if n.get("category") == category]
    if not same_cat:
        return None

    past_texts = "\n".join(
        f"- [{n.get('date', '')}] {n.get('content', '')[:120]}"
        for n in same_cat[-20:]  # last 20 notes in category
    )

    prompt = f"""You are checking if a new thought contradicts past thoughts.

New thought: "{new_note}"

Past {category} notes:
{past_texts}

Does the new thought DIRECTLY contradict or conflict with any of the past notes?
If YES: Reply with exactly:
CONTRADICTION: <the past note text, up to 100 chars>
DATE: <its date>

If NO: Reply with exactly:
NO_CONTRADICTION"""

    result = generate(prompt).strip()
    if result.upper().startswith("NO_CONTRADICTION"):
        return None

    past_note = ""
    past_date = ""
    for line in result.splitlines():
        if line.upper().startswith("CONTRADICTION:"):
            past_note = line.split(":", 1)[1].strip()
        elif line.upper().startswith("DATE:"):
            past_date = line.split(":", 1)[1].strip()

    if past_note:
        return {"content": past_note, "date": past_date}
    return None


# ── HELPER ────────────────────────────────────────────────────────────

def _get_note_row_number(note_id: str, all_notes: list) -> int:
    for i, n in enumerate(all_notes, start=2):
        if str(n.get("note_id", "")) == str(note_id):
            return i
    return -1


# ── MAIN PAGE ─────────────────────────────────────────────────────────

def show():
    # Page header
    st.markdown("""
<div style="margin-bottom:8px;">
  <h1 style="margin:0;font-size:2rem;font-weight:800;color:#1E1E2E;">🧠 Mufakkir</h1>
  <p style="margin:0;color:#6B7280;font-size:0.95rem;font-style:italic;">Ctrl+F for your brain.</p>
</div>
""", unsafe_allow_html=True)

    # Load notes once per session
    if "brain_notes_cache" not in st.session_state:
        st.session_state.brain_notes_cache = get_all_rows("brain_notes")
    all_notes = st.session_state.brain_notes_cache

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💭 Dump Thought", "📋 Browse Notes", "🔍 Ask My Brain",
        "📊 Insights", "📥 Bulk Import",
    ])

    # ── TAB 1: DUMP THOUGHT ──────────────────────────────────────────
    with tab1:
        col_main, col_side = st.columns([2, 1])

        with col_main:
            st.subheader("What's on your mind?")
            st.caption("Write anything — an idea, something you learned, a quick thought.")

            note_input = st.text_area(
                "Your thought",
                placeholder="e.g. Good managers ask questions before giving answers…",
                height=130,
                label_visibility="collapsed",
                key="dump_thought_input",
            )

            # Proactive surfacing while typing
            if note_input.strip() and len(note_input.strip()) >= 15:
                related = get_related_to_input(note_input.strip(), n=3)
                if related:
                    with col_side:
                        st.markdown("""
<div style="background:#F8F9FA;border:1px solid #E5E7EB;border-radius:10px;padding:12px 14px;margin-top:36px;">
  <div style="font-size:0.8rem;font-weight:600;color:#4F46E5;margin-bottom:8px;">
    💡 You thought about this before:
  </div>
""", unsafe_allow_html=True)
                        for rc, rcat, rscore in related:
                            pct = int(rscore * 100)
                            emoji = CAT_EMOJI.get(rcat, "📝")
                            st.markdown(
                                f'<div style="margin:6px 0;padding:8px 10px;background:#fff;'
                                f'border:1px solid #E5E7EB;border-radius:8px;font-size:0.82rem;color:#374151;">'
                                f'<span style="font-size:0.72rem;color:#6B7280;">{emoji} {rcat} · {pct}% match</span><br>'
                                f'{rc[:100]}{"…" if len(rc)>100 else ""}</div>',
                                unsafe_allow_html=True
                            )
                        st.markdown("</div>", unsafe_allow_html=True)

            # Categorization flow
            auto_cat = st.toggle("Auto-categorize with AI", value=True, key="auto_cat_toggle")

            if not auto_cat:
                manual_cat = st.selectbox("Category", BRAIN_CATEGORIES, key="manual_cat_select")

            if st.button("Analyse & Save 🧠", type="primary", use_container_width=True, key="save_btn"):
                if not note_input.strip():
                    st.warning("Please write something first.")
                else:
                    if auto_cat:
                        with st.spinner("Thinking…"):
                            cat, conf = categorize_note_with_confidence(note_input.strip())

                        if conf >= 70:
                            # Show suggestion and let user confirm or change
                            st.session_state["pending_note"] = note_input.strip()
                            st.session_state["pending_cat"] = cat
                            st.session_state["pending_conf"] = conf
                            st.session_state["show_cat_confirm"] = True
                        else:
                            # Low confidence — ask user to pick manually
                            st.session_state["pending_note"] = note_input.strip()
                            st.session_state["pending_conf"] = conf
                            st.session_state["show_low_conf"] = True
                    else:
                        # Manual — go straight to save
                        st.session_state["pending_note"] = note_input.strip()
                        st.session_state["pending_cat"] = manual_cat
                        st.session_state["show_final_confirm"] = True

            # ── Confirm category (high confidence) ───────────────────
            if st.session_state.get("show_cat_confirm"):
                cat  = st.session_state["pending_cat"]
                conf = st.session_state["pending_conf"]
                color = _CAT_COLOR.get(cat, "#4F46E5")
                st.markdown(
                    f'<div style="background:#F0F0FF;border:1px solid #C7D2FE;border-radius:10px;'
                    f'padding:14px 16px;margin:10px 0;">'
                    f'<span style="font-size:0.85rem;color:#4F46E5;font-weight:600;">AI Suggestion ({conf}% confident)</span><br>'
                    f'<span style="font-size:1rem;color:#1E1E2E;font-weight:700;">{CAT_EMOJI.get(cat,"")} {cat}</span></div>',
                    unsafe_allow_html=True
                )
                col_ok, col_change = st.columns(2)
                if col_ok.button(f"✅ Yes, save as {cat}", key="confirm_cat_yes", type="primary"):
                    _do_save(st.session_state["pending_note"], cat, conf, all_notes)
                    st.session_state.pop("show_cat_confirm", None)
                    st.session_state.pop("dump_thought_input", None)
                    st.rerun()

                change_cat = col_change.selectbox(
                    "Change to:", BRAIN_CATEGORIES,
                    index=BRAIN_CATEGORIES.index(cat),
                    key="override_cat_select"
                )
                if col_change.button("Save with this category", key="confirm_cat_override"):
                    _do_save(st.session_state["pending_note"], change_cat, conf, all_notes)
                    st.session_state.pop("show_cat_confirm", None)
                    st.rerun()

            # ── Low confidence — ask user to pick ────────────────────
            if st.session_state.get("show_low_conf"):
                conf = st.session_state["pending_conf"]
                st.warning(f"⚠️ AI is only {conf}% confident. Please pick the category:")
                chosen_cat = st.selectbox("Category", BRAIN_CATEGORIES, key="low_conf_cat")
                if st.button("Save with selected category", key="low_conf_save", type="primary"):
                    _do_save(st.session_state["pending_note"], chosen_cat, conf, all_notes)
                    st.session_state.pop("show_low_conf", None)
                    st.rerun()

            # ── Final confirm for manual mode ─────────────────────────
            if st.session_state.get("show_final_confirm"):
                cat = st.session_state["pending_cat"]
                st.info(f"Save this note as **{cat}**?")
                col_y, col_n = st.columns(2)
                if col_y.button("✅ Save", key="final_save_yes", type="primary"):
                    _do_save(st.session_state["pending_note"], cat, 100, all_notes)
                    st.session_state.pop("show_final_confirm", None)
                    st.rerun()
                if col_n.button("Cancel", key="final_save_no"):
                    st.session_state.pop("show_final_confirm", None)
                    st.rerun()

            # ── Contradiction warning ─────────────────────────────────
            if st.session_state.get("contradiction_warn"):
                warn = st.session_state["contradiction_warn"]
                st.markdown(
                    f'<div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:10px;'
                    f'padding:14px 16px;margin:10px 0;">'
                    f'<span style="font-size:0.9rem;color:#C2410C;font-weight:600;">'
                    f'⚠️ On {warn["date"]} you thought:</span><br>'
                    f'<em style="color:#374151;">"{warn["content"]}"</em><br>'
                    f'<span style="font-size:0.85rem;color:#6B7280;">Has your view changed?</span></div>',
                    unsafe_allow_html=True
                )
                col_upd, col_dis = st.columns(2)
                if col_upd.button("✍️ Updated View", key="contra_update"):
                    st.session_state.pop("contradiction_warn", None)
                    st.info("Great — your new note is already saved with your updated thinking.")
                if col_dis.button("Dismiss", key="contra_dismiss"):
                    st.session_state.pop("contradiction_warn", None)
                    st.rerun()

        # Quick stats (below the input area)
        st.divider()
        total = len(all_notes)
        cols = st.columns(6)
        cols[0].metric("Total", total)
        for i, cat in enumerate(BRAIN_CATEGORIES):
            cols[i+1].metric(f"{CAT_EMOJI.get(cat,'')} {cat}",
                             sum(1 for n in all_notes if n.get("category") == cat))

    # ── TAB 2: BROWSE NOTES ──────────────────────────────────────────
    with tab2:
        st.subheader("All Your Notes")

        if not all_notes:
            st.info("No notes yet. Go to 'Dump Thought' to add your first note.")
            return

        col_search, col_filter, col_date = st.columns([2, 1, 1])
        with col_search:
            search_query = st.text_input(
                "Search", placeholder="🔍 Filter by keyword…",
                label_visibility="collapsed"
            )
        with col_filter:
            filter_cat = st.selectbox("Category", ["All"] + BRAIN_CATEGORIES,
                                      label_visibility="collapsed")
        with col_date:
            date_filter = st.selectbox("Period",
                ["All Time", "Today", "This Week", "This Month"],
                label_visibility="collapsed"
            )

        filtered = _apply_filters(all_notes, search_query, filter_cat, date_filter)
        st.caption(f"Showing **{len(filtered)}** of {len(all_notes)} notes")
        st.divider()

        for note in reversed(filtered):
            cat      = note.get("category", "Personal")
            note_id  = str(note.get("note_id", ""))
            content  = note.get("content", "")
            emoji    = CAT_EMOJI.get(cat, "📝")
            color    = _CAT_COLOR.get(cat, "#6B7280")

            with st.expander(
                f"{emoji} {content[:65]}{'…' if len(content)>65 else ''} — {note.get('date','')}",
                expanded=False
            ):
                edit_key = f"editing_{note_id}"
                if st.session_state.get(edit_key):
                    edited_content = st.text_area("Edit note", value=content, height=100, key=f"edit_text_{note_id}")
                    edited_cat = st.selectbox("Category", BRAIN_CATEGORIES,
                                              index=BRAIN_CATEGORIES.index(cat) if cat in BRAIN_CATEGORIES else 0,
                                              key=f"edit_cat_{note_id}")
                    s_col, c_col = st.columns(2)
                    if s_col.button("💾 Save", key=f"save_{note_id}", type="primary"):
                        row_num = _get_note_row_number(note_id, all_notes)
                        if row_num > 0:
                            emb_str = note.get("embedding", "")
                            if edited_content.strip() != content:
                                try:
                                    emb_str = json.dumps(get_embedding(edited_content.strip()))
                                except Exception:
                                    pass
                            update_row("brain_notes", row_num, [
                                note_id, edited_content.strip(), edited_cat,
                                note.get("date"), note.get("time"), emb_str,
                                note.get("confidence_score", ""), note.get("connected_note_ids", ""),
                                note.get("day_of_week", ""), note.get("created_time", ""),
                            ])
                            st.session_state.pop(edit_key, None)
                            st.session_state.pop("brain_notes_cache", None)
                            st.session_state.pop("chroma_initialized", None)
                            log_activity("Brain Note", f"Edited: {edited_content[:50]}")
                            st.success("Updated.")
                            st.rerun()
                    if c_col.button("✕ Cancel", key=f"cancel_{note_id}"):
                        st.session_state.pop(edit_key, None)
                        st.rerun()
                else:
                    st.write(content)
                    # Meta row
                    meta = []
                    if note.get("date"): meta.append(f"📅 {note['date']}")
                    if note.get("time"): meta.append(f"🕐 {note['time']}")
                    if note.get("day_of_week"): meta.append(f"📆 {note['day_of_week']}")
                    conf = note.get("confidence_score", "")
                    if conf: meta.append(f"🎯 {conf}% AI confidence")
                    st.caption("  ·  ".join(meta) if meta else "")

                    # Category badge
                    st.markdown(
                        f'<span style="background:{color}20;color:{color};'
                        f'border-radius:20px;padding:2px 10px;font-size:0.78rem;font-weight:600;">'
                        f'{emoji} {cat}</span>',
                        unsafe_allow_html=True
                    )
                    st.markdown("")

                    act_col, del_col = st.columns(2)
                    if act_col.button("✏️ Edit", key=f"open_edit_{note_id}"):
                        st.session_state[edit_key] = True
                        st.rerun()
                    if del_col.button("🗑️ Delete", key=f"del_{note_id}"):
                        st.session_state[f"confirm_del_{note_id}"] = True
                        st.rerun()

                    if st.session_state.get(f"confirm_del_{note_id}"):
                        st.warning("Delete this note? This cannot be undone.")
                        y_col, n_col = st.columns(2)
                        if y_col.button("Yes, delete", key=f"yes_del_{note_id}", type="primary"):
                            row_num = _get_note_row_number(note_id, all_notes)
                            if row_num > 0:
                                delete_row("brain_notes", row_num)
                                log_activity("Brain Note", f"Deleted: {content[:50]}")
                                st.session_state.pop(f"confirm_del_{note_id}", None)
                                st.session_state.pop("brain_notes_cache", None)
                                st.session_state.pop("chroma_initialized", None)
                                st.success("Deleted.")
                                st.rerun()
                        if n_col.button("Cancel", key=f"no_del_{note_id}"):
                            st.session_state.pop(f"confirm_del_{note_id}", None)
                            st.rerun()

    # ── TAB 3: ASK MY BRAIN ──────────────────────────────────────────
    with tab3:
        from modules.brain.brain_rag import ask_brain
        ask_brain()

    # ── TAB 4: INSIGHTS ──────────────────────────────────────────────
    with tab4:
        from modules.brain.brain_insights import show_insights
        show_insights(all_notes)

    # ── TAB 5: BULK IMPORT ───────────────────────────────────────────
    with tab5:
        st.subheader("Bulk Import Notes")
        st.caption("Paste multiple thoughts — one per line (or paste a WhatsApp export).")

        bulk_input = st.text_area(
            "Paste notes", height=180, label_visibility="collapsed",
            placeholder="Good managers ask questions before giving answers\nLearn Porter's Five Forces…"
        )
        bulk_auto = st.toggle("Auto-categorize each note", value=True, key="bulk_auto_cat")
        if not bulk_auto:
            bulk_manual_cat = st.selectbox("Category for all", BRAIN_CATEGORIES, key="bulk_cat")

        if bulk_input.strip():
            lines = [l.strip() for l in bulk_input.splitlines() if l.strip()]
            cleaned = []
            for line in lines:
                m = re.match(r"^\[[\d/,: ]+\]\s*[^:]+:\s*(.+)$", line)
                cleaned.append(m.group(1).strip() if m else line)

            st.write(f"**{len(cleaned)} notes** ready to import")
            for i, line in enumerate(cleaned[:5], 1):
                st.write(f"{i}. {line[:80]}{'…' if len(line)>80 else ''}")
            if len(cleaned) > 5:
                st.caption(f"…and {len(cleaned)-5} more")

            if st.button(f"Import {len(cleaned)} notes 🧠", type="primary", use_container_width=True):
                bar = st.progress(0, text="Starting import…")
                saved = failed = 0
                for i, line in enumerate(cleaned):
                    bar.progress((i+1)/len(cleaned), text=f"Saving {i+1}/{len(cleaned)}…")
                    try:
                        cat = categorize_note(line) if bulk_auto else bulk_manual_cat
                        save_note(line, cat)
                        saved += 1
                    except Exception as e:
                        failed += 1
                        st.warning(f"Skipped: {line[:60]} — {e}")
                st.session_state.chroma_note_count = get_note_count()
                st.session_state.pop("brain_notes_cache", None)
                bar.empty()
                if failed == 0:
                    st.success(f"✅ Imported all {saved} notes!")
                else:
                    st.warning(f"Imported {saved}. {failed} failed.")
                st.rerun()

    # ── BRAIN MAP ────────────────────────────────────────────────────
    st.divider()
    st.subheader("🗺️ Brain Map")
    st.caption("Visual map of all your notes.")

    if "show_brain_map" not in st.session_state:
        st.session_state.show_brain_map = False

    col_show, col_hide = st.columns([1, 1])
    if col_show.button("🗺️ Show Map", use_container_width=True,
                       type="primary" if not st.session_state.show_brain_map else "secondary"):
        st.session_state.show_brain_map = True
    if col_hide.button("✕ Hide", use_container_width=True):
        st.session_state.show_brain_map = False

    if st.session_state.show_brain_map:
        from modules.brain.brain_map import render_map
        render_map()


# ── HELPERS ───────────────────────────────────────────────────────────

def _do_save(content: str, category: str, confidence: int, all_notes: list):
    """Save note, then asynchronously check for contradictions."""
    with st.spinner("Saving…"):
        save_note(content, category, confidence)
        st.session_state.chroma_note_count = get_note_count()
        st.session_state.pop("brain_notes_cache", None)
        st.success(f"✅ Saved to **{category}** at {now_time_str()}")

    # Contradiction check (runs after save)
    with st.spinner("Checking for contradictions…"):
        try:
            contradiction = check_contradiction(content, category, all_notes)
            if contradiction:
                st.session_state["contradiction_warn"] = contradiction
        except Exception:
            pass


def _apply_filters(notes: list, query: str, cat_filter: str, date_filter: str) -> list:
    from utils.date_utils import now_ist
    import datetime

    result = notes
    if cat_filter != "All":
        result = [n for n in result if n.get("category") == cat_filter]
    if query.strip():
        q = query.strip().lower()
        result = [n for n in result if q in n.get("content", "").lower()]

    if date_filter == "Today":
        today = now_ist().strftime("%d %b %Y")
        result = [n for n in result if n.get("date", "") == today]
    elif date_filter == "This Week":
        now = now_ist()
        week_ago = (now - datetime.timedelta(days=7)).date()
        result = [n for n in result if _note_date_gte(n, week_ago)]
    elif date_filter == "This Month":
        now = now_ist()
        month_ago = (now - datetime.timedelta(days=30)).date()
        result = [n for n in result if _note_date_gte(n, month_ago)]

    return result


def _note_date_gte(note: dict, threshold) -> bool:
    import datetime
    raw = note.get("date", "") or note.get("created_time", "")
    for fmt in ("%d %b %Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            d = datetime.datetime.strptime(str(raw).strip(), fmt).date()
            return d >= threshold
        except Exception:
            continue
    return True  # if unparseable, include it
