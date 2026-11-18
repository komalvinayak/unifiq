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

_MAX_HISTORY = 5


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

    return answer, scored_notes


def _add_to_history(question: str):
    """Keeps a rolling list of the last 5 unique questions asked."""
    history = st.session_state.get("brain_search_history", [])
    if question in history:
        history.remove(question)
    history.insert(0, question)
    st.session_state.brain_search_history = history[:_MAX_HISTORY]


def ask_brain():
    """
    Renders the Ask My Brain UI in Streamlit.
    Called from brain_core.py tab 3.
    """
    st.subheader("Ask Your Brain")
    st.caption("Ask anything you've written about. UNIFIQ finds your relevant notes and answers.")

    # ── SEARCH HISTORY ────────────────────────────────────────────────
    history = st.session_state.get("brain_search_history", [])
    if history:
        st.write("**Recent questions:**")
        history_cols = st.columns(min(len(history), 3))
        for i, past_q in enumerate(history[:3]):
            if history_cols[i].button(f"🕐 {past_q[:35]}…" if len(past_q) > 35 else f"🕐 {past_q}",
                                      key=f"hist_{i}", use_container_width=True):
                st.session_state.brain_question = past_q
                st.rerun()
        if len(history) > 3:
            more_cols = st.columns(len(history) - 3)
            for i, past_q in enumerate(history[3:]):
                if more_cols[i].button(f"🕐 {past_q[:35]}…" if len(past_q) > 35 else f"🕐 {past_q}",
                                       key=f"hist_extra_{i}", use_container_width=True):
                    st.session_state.brain_question = past_q
                    st.rerun()
        st.divider()

    # ── EXAMPLE PROMPTS ───────────────────────────────────────────────
    if not history:
        st.write("**Try asking:**")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("What do I know about leadership?"):
                st.session_state.brain_question = "What do I know about leadership?"
            if st.button("What are my thoughts on productivity?"):
                st.session_state.brain_question = "What are my thoughts on productivity?"
        with col2:
            if st.button("What have I learned about finance?"):
                st.session_state.brain_question = "What have I learned about finance?"
            if st.button("What are my recent work notes?"):
                st.session_state.brain_question = "What are my recent work notes?"
        st.divider()

    # ── QUESTION INPUT ────────────────────────────────────────────────
    question = st.text_input(
        "Your question",
        value=st.session_state.get("brain_question", ""),
        placeholder="e.g. What have I written about time management?"
    )

    if st.button("Ask 🔍", type="primary"):
        if not question.strip():
            st.warning("Please type a question.")
            return

        with st.spinner("Searching your brain..."):
            try:
                answer, sources = rag_answer(question)
                _add_to_history(question)
                # Store result in session_state so it survives the rerun below
                st.session_state.brain_last_answer = answer
                st.session_state.brain_last_sources = sources
                st.session_state.brain_last_question = question
                st.session_state.pop("brain_question", None)
                st.rerun()

            except Exception as e:
                st.error(f"Could not search brain: {e}")
                st.info("Make sure you have added some notes first.")

    # ── DISPLAY LAST ANSWER (persists across reruns) ──────────────────
    if "brain_last_answer" in st.session_state:
        st.divider()
        st.markdown(f"**Q: {st.session_state.brain_last_question}**")
        st.markdown("### Answer")
        st.write(st.session_state.brain_last_answer)

        sources = st.session_state.get("brain_last_sources", [])
        if sources:
            st.divider()
            st.markdown("**📌 Notes used to answer this:**")
            for i, (note, score) in enumerate(sources, 1):
                pct = int(score * 100)
                if pct >= 80:
                    badge = f"🟢 {pct}% match"
                elif pct >= 60:
                    badge = f"🟡 {pct}% match"
                else:
                    badge = f"⚪ {pct}% match"

                with st.expander(f"Source {i}  {badge}  — {note[:55]}…" if len(note) > 55 else f"Source {i}  {badge}  — {note}"):
                    st.write(note)
