# ── brain_rag.py ─────────────────────────────────────────────────────
# The "Ask My Brain" feature — Manual RAG Pipeline
#
# RAG = Retrieve, Augment, Generate
#
# Step 1 — RETRIEVE:  Convert question to vector → find similar notes
# Step 2 — AUGMENT:   Add those notes as context to the prompt
# Step 3 — GENERATE:  Gemini answers using ONLY your notes as context
#
# No LangChain. Every step is written by us. Every step is visible.
# ─────────────────────────────────────────────────────────────────────

import streamlit as st
from ai.embeddings_client import get_query_embedding
from database.chroma_client import search_similar_notes_with_scores
from ai.gemini_client import generate


def rag_answer(question: str) -> tuple:
    """
    The full RAG pipeline in one function.

    Returns:
        answer (str): Gemini's answer based on your notes
        sources (list): (text, score) tuples — notes used, with similarity %
    """

    # ── STEP 1: RETRIEVE ─────────────────────────────────────────────
    question_vector = get_query_embedding(question)
    scored_notes = search_similar_notes_with_scores(question_vector, n_results=5)

    if not scored_notes:
        return "I haven't found any related notes in your brain yet. Add some notes first!", []

    # ── STEP 2: AUGMENT ──────────────────────────────────────────────
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

    # ── STEP 3: GENERATE ─────────────────────────────────────────────
    answer = generate(prompt)

    # Graceful degradation: if all AI providers are down, still show retrieved notes
    if "ai is temporarily unavailable" in answer.lower() and scored_notes:
        note_lines = "\n\n".join(
            f"**Note {i+1}:** {note}" for i, (note, _) in enumerate(scored_notes)
        )
        answer = (
            f"⚠️ AI is offline right now — here are your most relevant notes "
            f"for **\"{question}\"**:\n\n{note_lines}"
        )

    return answer, scored_notes


def _render_sources(sources: list):
    """Renders source notes as compact expanders inside a chat bubble."""
    if not sources:
        return
    st.caption("📌 **Sources from your notes:**")
    for i, (note, score) in enumerate(sources, 1):
        pct = int(score * 100)
        badge = "🟢" if pct >= 80 else "🟡" if pct >= 60 else "⚪"
        label = f"{badge} {pct}%  —  {note[:60]}…" if len(note) > 60 else f"{badge} {pct}%  —  {note}"
        with st.expander(label, expanded=False):
            st.write(note)


def ask_brain():
    """
    Renders the Ask My Brain chatbot UI.
    Called from brain_core.py tab 3.
    """
    st.subheader("🧠 Ask Your Brain")
    st.caption("Type anything — a keyword, topic, date, or question. Your brain will find the most relevant notes.")

    # ── INIT CHAT HISTORY ────────────────────────────────────────────
    if "brain_chat" not in st.session_state:
        st.session_state.brain_chat = []  # list of {role, content, sources}

    # ── STARTER CHIPS (shown only when chat is empty) ─────────────────
    if not st.session_state.brain_chat:
        st.markdown("**Try asking:**")
        chips = [
            "What do I know about RAG?",
            "Show my cybersecurity notes",
            "What have I written about productivity?",
            "Summarise my learning notes",
        ]
        cols = st.columns(2)
        for i, chip in enumerate(chips):
            if cols[i % 2].button(chip, key=f"chip_{i}", use_container_width=True):
                st.session_state.brain_chat_input = chip
                st.rerun()

    # ── RENDER CHAT HISTORY ───────────────────────────────────────────
    for msg in st.session_state.brain_chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("sources"):
                _render_sources(msg["sources"])

    # ── CHAT INPUT ────────────────────────────────────────────────────
    # Pre-fill from chip click or sidebar quick-ask
    prefill = st.session_state.pop("brain_chat_input", None)

    prompt = st.chat_input(
        "Ask anything — keyword, topic, date, question…",
        key="brain_chat_input_box",
    )

    # Accept from either the chat_input widget or a chip button
    question = prompt or prefill
    if not question:
        return

    # Show user bubble immediately
    st.session_state.brain_chat.append({"role": "user", "content": question, "sources": []})
    with st.chat_message("user"):
        st.markdown(question)

    # Run RAG and stream assistant bubble
    with st.chat_message("assistant"):
        with st.spinner("Searching your brain…"):
            try:
                answer, sources = rag_answer(question)
            except Exception as e:
                answer = f"❌ Could not search brain: {e}"
                sources = []

        st.markdown(answer)
        _render_sources(sources)

    st.session_state.brain_chat.append({
        "role": "assistant",
        "content": answer,
        "sources": sources,
    })

    # ── CLEAR BUTTON ─────────────────────────────────────────────────
    if st.session_state.brain_chat:
        if st.button("🗑 Clear chat", key="clear_brain_chat"):
            st.session_state.brain_chat = []
            st.rerun()
