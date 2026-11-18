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
from database.chroma_client import search_similar_notes
from ai.gemini_client import generate


def rag_answer(question: str) -> tuple:
    """
    The full RAG pipeline in one function.

    Returns:
        answer (str): Gemini's answer based on your notes
        sources (list): The notes that were used to answer

    How it works (3 steps):
    """

    # ── STEP 1: RETRIEVE ─────────────────────────────────────────────
    # Convert the question into a vector (768 numbers)
    # Then find the 5 most similar note vectors in ChromaDB
    question_vector = get_query_embedding(question)
    similar_notes = search_similar_notes(question_vector, n_results=5)

    if not similar_notes:
        return "I haven't found any related notes in your brain yet. Add some notes first!", []

    # ── STEP 2: AUGMENT ──────────────────────────────────────────────
    # Build a prompt that includes the retrieved notes as context
    # This is what "augmented" means — we augment the question with context
    context = "\n\n".join([f"Note {i+1}: {note}" for i, note in enumerate(similar_notes)])

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
    # Send the augmented prompt to Gemini
    # Gemini answers using the retrieved notes as context
    answer = generate(prompt)

    return answer, similar_notes


def ask_brain():
    """
    Renders the Ask My Brain UI in Streamlit.
    Called from brain_core.py tab 3.
    """
    st.subheader("Ask Your Brain")
    st.caption("Ask anything you've written about. UNIFIQ finds your relevant notes and answers.")

    # Show question examples
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

    # Question input
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

                # Show the answer
                st.markdown("### Answer")
                st.write(answer)

                # Show which notes were used
                if sources:
                    st.divider()
                    st.markdown("**📌 Notes used to answer this:**")
                    for i, note in enumerate(sources, 1):
                        with st.expander(f"Source {i}: {note[:60]}..."):
                            st.write(note)

            except Exception as e:
                st.error(f"Could not search brain: {e}")
                st.info("Make sure you have added some notes first.")
