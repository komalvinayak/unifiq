# ── brain_rag.py ─────────────────────────────────────────────────────
# Ask My Brain — semantic search + category/date/keyword filters.
# ─────────────────────────────────────────────────────────────────────

import datetime
import streamlit as st
from ai.embeddings_client import get_query_embedding
from database.chroma_client import search_similar_notes_with_scores
from database.sheets_client import get_all_rows
from ai.gemini_client import generate
from utils.date_utils import now_ist
from config.settings import BRAIN_CATEGORIES

_MAX_HISTORY = 15

CAT_EMOJI = {
    "Work": "💼", "Learning": "📚", "Personal": "🌱",
    "Technical": "💻", "Career": "🎯",
}
_CAT_COLOR = {
    "Work": "#4F46E5", "Learning": "#16A34A", "Personal": "#D97706",
    "Technical": "#7C3AED", "Career": "#DC2626",
}


def _parse_note_date(raw: str):
    for fmt in ("%d %b %Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(str(raw).strip(), fmt).date()
        except Exception:
            continue
    return None


def rag_answer(question: str, cat_filter: str = "All",
               date_from=None, date_to=None,
               keyword: str = "") -> tuple:
    """
    Full RAG pipeline with optional filters.
    Returns (answer, [(note_dict, score), ...])
    where note_dict has content, category, date, time.
    """
    # Get all notes from cache for metadata lookup
    all_notes = st.session_state.get("brain_notes_cache") or get_all_rows("brain_notes")

    # Semantic search
    question_vector = get_query_embedding(question)
    scored_raw = search_similar_notes_with_scores(question_vector, n_results=20)

    # Match back to full note dicts for metadata
    scored_notes = []
    for content, score in scored_raw:
        note = next((n for n in all_notes if n.get("content", "") == content), None)
        if note:
            scored_notes.append((note, score))
        else:
            scored_notes.append(({"content": content, "category": "", "date": "", "time": ""}, score))

    # Apply category filter
    if cat_filter != "All":
        scored_notes = [(n, s) for n, s in scored_notes if n.get("category") == cat_filter]

    # Apply keyword filter
    if keyword.strip():
        kw = keyword.strip().lower()
        scored_notes = [(n, s) for n, s in scored_notes if kw in n.get("content", "").lower()]

    # Apply date range filter
    if date_from or date_to:
        filtered = []
        for n, s in scored_notes:
            nd = _parse_note_date(n.get("date", "") or n.get("created_time", ""))
            if nd:
                if date_from and nd < date_from:
                    continue
                if date_to and nd > date_to:
                    continue
            filtered.append((n, s))
        scored_notes = filtered

    # Keep top 5 by score
    scored_notes = sorted(scored_notes, key=lambda x: x[1], reverse=True)[:5]

    if not scored_notes:
        return "No matching notes found with the current filters. Try widening your search.", []

    context = "\n\n".join(
        f"Note {i+1} [{n.get('category','')} · {n.get('date','')}]: {n.get('content','')}"
        for i, (n, _) in enumerate(scored_notes)
    )

    prompt = f"""You are Mufakkir — a friendly personal brain assistant. You help the user recall their saved notes AND answer general questions naturally.

The user asked: "{question}"

Relevant notes from their knowledge base:
{context}

INSTRUCTIONS:
- For greetings, small talk, or general questions (like "how are you", "what can you do", "who are you"): respond warmly and naturally as a helpful assistant. Do NOT say "I don't have notes about that."
- For questions about the user's own thoughts/memories: answer using the notes above.
- For general knowledge questions: answer from your knowledge, mentioning relevant notes if any.
Be concise and conversational."""

    answer = generate(prompt)

    if "ai is temporarily unavailable" in answer.lower() and scored_notes:
        note_lines = "\n\n".join(
            f"**Note {i+1}:** {n.get('content','')}"
            for i, (n, _) in enumerate(scored_notes)
        )
        answer = (
            f"⚠️ AI is offline right now — here are your most relevant notes "
            f"for **\"{question}\"**:\n\n{note_lines}"
        )

    return answer, scored_notes


def _apply_browse_filters(notes: list, cat_filter: str, date_from, date_to, keyword: str) -> list:
    result = notes
    if cat_filter != "All":
        result = [n for n in result if n.get("category") == cat_filter]
    if keyword.strip():
        kw = keyword.strip().lower()
        result = [n for n in result if kw in n.get("content", "").lower()]
    if date_from or date_to:
        filtered = []
        for n in result:
            nd = _parse_note_date(n.get("date", "") or n.get("created_time", ""))
            if nd:
                if date_from and nd < date_from:
                    continue
                if date_to and nd > date_to:
                    continue
            filtered.append(n)
        result = filtered
    return result


def _render_note_card(n: dict):
    cat     = n.get("category", "Personal")
    color   = _CAT_COLOR.get(cat, "#6B7280")
    emoji   = CAT_EMOJI.get(cat, "📝")
    date    = n.get("date", "")
    time    = n.get("time", "")
    content = n.get("content", "")
    conf    = n.get("confidence_score", "")
    conf_txt = f" · {conf}% conf" if conf else ""
    st.markdown(
        f'<div style="margin:6px 0;padding:12px 14px;background:#F8F9FA;'
        f'border:1px solid #E5E7EB;border-radius:10px;'
        f'border-left:3px solid {color};">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
        f'<span style="background:{color}20;color:{color};border-radius:12px;'
        f'padding:2px 10px;font-size:0.74rem;font-weight:600;">{emoji} {cat}</span>'
        f'<span style="font-size:0.72rem;color:#9CA3AF;">📅 {date}{"  🕐 " + time if time else ""}{conf_txt}</span>'
        f'</div>'
        f'<div style="font-size:0.9rem;color:#1E1E2E;line-height:1.55;">{content}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def _add_to_history(question: str):
    history = st.session_state.get("brain_search_history", [])
    if question in history:
        history.remove(question)
    history.insert(0, question)
    st.session_state.brain_search_history = history[:_MAX_HISTORY]


def _process_question(question: str, cat_filter: str, date_from, date_to, keyword: str):
    chat = st.session_state.brain_chat
    if chat and chat[-1]["role"] == "user" and chat[-1]["content"] == question:
        return
    chat.append({"role": "user", "content": question, "sources": []})
    _add_to_history(question)
    try:
        answer, sources = rag_answer(question, cat_filter, date_from, date_to, keyword)
    except Exception as e:
        answer = f"❌ Error: {e}"
        sources = []
    chat.append({"role": "assistant", "content": answer, "sources": sources})


def ask_brain():
    if "brain_chat" not in st.session_state:
        st.session_state.brain_chat = []

    # ── STYLES ───────────────────────────────────────────────────────
    st.markdown("""
<style>
.user-bubble {
    background: #4F46E5;
    color: #FFFFFF;
    border-radius: 18px 18px 4px 18px;
    padding: 10px 16px;
    margin: 4px 0 4px 60px;
    font-size: 0.95rem;
    line-height: 1.5;
}
.bot-bubble {
    background: #F8F9FA;
    border: 1px solid #E5E7EB;
    color: #1E1E2E;
    border-radius: 18px 18px 18px 4px;
    padding: 12px 16px;
    margin: 4px 60px 4px 0;
    font-size: 0.95rem;
    line-height: 1.6;
}
.chat-label {
    font-size: 0.72rem;
    color: #9CA3AF;
    margin-bottom: 2px;
    padding-left: 4px;
}
.note-meta {
    font-size: 0.75rem;
    color: #9CA3AF;
    margin-top: 2px;
}
</style>
""", unsafe_allow_html=True)

    # ── HEADER ───────────────────────────────────────────────────────
    h1, h2 = st.columns([7, 1])
    with h1:
        st.markdown("### 🔍 Ask Your Brain")
    with h2:
        if st.session_state.brain_chat:
            if st.button("Clear", use_container_width=True, key="chat_clear_btn"):
                st.session_state.brain_chat = []
                st.rerun()

    # ── FILTERS ──────────────────────────────────────────────────────
    with st.expander("🔧 Search Filters", expanded=False):
        fc1, fc2, fc3, fc4 = st.columns([1, 1, 1, 1])
        with fc1:
            cat_filter = st.selectbox("Category", ["All"] + BRAIN_CATEGORIES,
                                      key="rag_cat_filter")
        with fc2:
            keyword_filter = st.text_input("Keyword", placeholder="e.g. RAG, Python…",
                                           key="rag_keyword_filter",
                                           label_visibility="visible")
        with fc3:
            date_from_input = st.date_input("From date", value=None, key="rag_date_from")
        with fc4:
            date_to_input = st.date_input("To date", value=None, key="rag_date_to")

    # ── EMPTY STATE ──────────────────────────────────────────────────
    if not st.session_state.brain_chat:
        st.markdown(
            '<div style="text-align:center;padding:40px 0 20px;">'
            '<div style="font-size:2rem;margin-bottom:12px;">🧠</div>'
            '<div style="font-size:1rem;color:#6B7280;font-weight:500;">Ask anything about your notes</div>'
            '<div style="font-size:0.85rem;color:#9CA3AF;margin-top:6px;">'
            'Try a topic, a keyword, a date range, or a full question</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── CHAT MESSAGES ────────────────────────────────────────────────
    for msg in st.session_state.brain_chat:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="chat-label" style="text-align:right">You</div>'
                f'<div class="user-bubble">{msg["content"]}</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown('<div class="chat-label">Mufakkir</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="bot-bubble">{msg["content"]}</div>',
                unsafe_allow_html=True
            )
            sources = msg.get("sources", [])
            if sources:
                top = [(n, s) for n, s in sources if s >= 0.35]
                if top:
                    with st.expander(f"📌 {len(top)} source{'s' if len(top)>1 else ''} from your notes", expanded=False):
                        for note_dict, score in top:
                            pct = int(score * 100)
                            cat  = note_dict.get("category", "")
                            date = note_dict.get("date", "")
                            time = note_dict.get("time", "")
                            emoji = CAT_EMOJI.get(cat, "📝")
                            color = _CAT_COLOR.get(cat, "#6B7280")
                            badge = "🟢" if pct >= 80 else "🟡" if pct >= 60 else "⚪"
                            content = note_dict.get("content", "")

                            st.markdown(
                                f'<div style="margin:6px 0;padding:10px 12px;background:#F8F9FA;'
                                f'border:1px solid #E5E7EB;border-radius:8px;">'
                                f'<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
                                f'<span style="background:{color}20;color:{color};'
                                f'border-radius:12px;padding:1px 8px;font-size:0.74rem;font-weight:600;">'
                                f'{emoji} {cat}</span>'
                                f'<span style="font-size:0.74rem;color:#9CA3AF;">{badge} {pct}% match</span>'
                                f'</div>'
                                f'<div style="font-size:0.88rem;color:#374151;">'
                                f'{content[:200]}{"…" if len(content)>200 else ""}</div>'
                                f'<div class="note-meta">📅 {date}{"  🕐 " + time if time else ""}</div>'
                                f'</div>',
                                unsafe_allow_html=True
                            )

    # ── INPUT BAR ────────────────────────────────────────────────────
    with st.form(key="brain_chat_form", clear_on_submit=True):
        col_in, col_btn = st.columns([9, 1])
        with col_in:
            question = st.text_input(
                "ask", placeholder="Ask anything about your notes…",
                label_visibility="collapsed",
            )
        with col_btn:
            sent = st.form_submit_button("➤", use_container_width=True)

    if sent and question.strip():
        with st.spinner("Ctrl+F in progress..."):
            _process_question(
                question.strip(),
                cat_filter,
                date_from_input,
                date_to_input,
                keyword_filter,
            )
        st.rerun()
