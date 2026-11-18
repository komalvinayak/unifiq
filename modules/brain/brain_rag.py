# ── brain_rag.py ─────────────────────────────────────────────────────
# The "Ask My Brain" feature — Manual RAG Pipeline
#
# RAG = Retrieve, Augment, Generate
#
# Step 1 — RETRIEVE:  Convert question to vector → find similar notes
# Step 2 — AUGMENT:   Add those notes as context to the prompt
# Step 3 — GENERATE:  Gemini answers using ONLY your notes as context
# ─────────────────────────────────────────────────────────────────────

import streamlit as st
from ai.embeddings_client import get_query_embedding
from database.chroma_client import search_similar_notes_with_scores
from ai.gemini_client import generate

_MAX_HISTORY = 10


def rag_answer(question: str) -> tuple:
    """
    Full RAG pipeline. Returns (answer, [(note_text, score), ...]).
    """
    question_vector = get_query_embedding(question)
    scored_notes = search_similar_notes_with_scores(question_vector, n_results=5)

    if not scored_notes:
        return "I haven't found any related notes in your brain yet. Add some notes first!", []

    context = "\n\n".join([f"Note {i+1}: {note}" for i, (note, _) in enumerate(scored_notes)])

    prompt = f"""You are UNIFIQ Brain — a personal assistant that helps the user
understand their own thoughts and knowledge.

The user has asked: "{question}"

Here are the most relevant notes from their personal knowledge base:

{context}

Based ONLY on these notes, answer the user's question.
If the notes don't have enough information, say so honestly.
Be concise and helpful. Write as if you are summarizing their own thinking back to them.
"""

    answer = generate(prompt)

    if "ai is temporarily unavailable" in answer.lower() and scored_notes:
        note_lines = "\n\n".join(
            f"**Note {i+1}:** {note}" for i, (note, _) in enumerate(scored_notes)
        )
        answer = (
            f"⚠️ AI is offline right now — here are your most relevant notes "
            f"for **\"{question}\"**:\n\n{note_lines}"
        )

    return answer, scored_notes


def _add_to_search_history(question: str):
    """Keeps a rolling list of the last N unique queries."""
    history = st.session_state.get("brain_search_history", [])
    if question in history:
        history.remove(question)
    history.insert(0, question)
    st.session_state.brain_search_history = history[:_MAX_HISTORY]


def _render_sources(sources: list):
    """Renders source notes as compact expanders below an assistant bubble."""
    if not sources:
        return
    st.caption("📌 **Sources from your notes:**")
    for i, (note, score) in enumerate(sources, 1):
        pct = int(score * 100)
        badge = "🟢" if pct >= 80 else "🟡" if pct >= 60 else "⚪"
        label = f"{badge} {pct}%  —  {note[:65]}…" if len(note) > 65 else f"{badge} {pct}%  —  {note}"
        with st.expander(label, expanded=False):
            st.write(note)


def _process_question(question: str):
    """Runs RAG for `question`, appends both sides to brain_chat, updates search history."""
    # Guard against duplicate processing (double-click or Streamlit re-render race)
    chat = st.session_state.brain_chat
    if chat and chat[-1]["role"] == "user" and chat[-1]["content"] == question:
        return

    chat.append({"role": "user", "content": question, "sources": []})
    _add_to_search_history(question)

    # Run RAG
    try:
        answer, sources = rag_answer(question)
    except Exception as e:
        answer = f"❌ Error searching your brain: {e}"
        sources = []

    st.session_state.brain_chat.append({
        "role": "assistant",
        "content": answer,
        "sources": sources,
    })


def ask_brain():
    """
    Chatbot UI for Ask My Brain.
    Called from brain_core.py tab 3.
    """
    # ── INIT STATE ───────────────────────────────────────────────────
    if "brain_chat" not in st.session_state:
        st.session_state.brain_chat = []

    # Header row with clear button
    hcol1, hcol2 = st.columns([6, 1])
    with hcol1:
        st.subheader("🧠 Ask Your Brain")
        st.caption("Type anything — keyword, topic, date, full question. Your brain finds the most relevant notes.")
    with hcol2:
        if st.session_state.brain_chat:
            if st.button("🗑 Clear", help="Clear chat", use_container_width=True):
                st.session_state.brain_chat = []
                st.rerun()

    # ── SEARCH HISTORY CHIPS ─────────────────────────────────────────
    history = st.session_state.get("brain_search_history", [])
    if history:
        with st.expander(f"🕐 Recent searches ({len(history)})", expanded=False):
            cols = st.columns(3)
            for i, past_q in enumerate(history):
                label = f"{past_q[:30]}…" if len(past_q) > 30 else past_q
                if cols[i % 3].button(label, key=f"hist_chip_{i}", use_container_width=True):
                    _process_question(past_q)
                    st.rerun()

    # ── STARTER CHIPS (only when chat is empty) ───────────────────────
    if not st.session_state.brain_chat:
        st.markdown("**Try asking:**")
        starter_chips = [
            "What do I know about RAG?",
            "Show my cybersecurity notes",
            "What have I written about productivity?",
            "Summarise my learning notes",
        ]
        c1, c2 = st.columns(2)
        pairs = [(starter_chips[i], starter_chips[i + 1]) for i in range(0, len(starter_chips), 2)]
        for left, right in pairs:
            if c1.button(left, key=f"starter_{left[:15]}", use_container_width=True):
                _process_question(left)
                st.rerun()
            if c2.button(right, key=f"starter_{right[:15]}", use_container_width=True):
                _process_question(right)
                st.rerun()

    # ── RENDER CHAT HISTORY ───────────────────────────────────────────
    for msg in st.session_state.brain_chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                _render_sources(msg.get("sources", []))

    # ── CHAT INPUT ────────────────────────────────────────────────────
    # st.chat_input can't be used inside st.tabs, so we use a form instead
    with st.form(key="brain_chat_form", clear_on_submit=True):
        col_in, col_btn = st.columns([8, 1])
        with col_in:
            question = st.text_input(
                "chat_input",
                placeholder="Ask anything — keyword, topic, date, question…",
                label_visibility="collapsed",
            )
        with col_btn:
            submitted = st.form_submit_button("➤", use_container_width=True)

    if submitted and question.strip():
        with st.spinner("Searching your brain…"):
            _process_question(question.strip())
        st.rerun()
