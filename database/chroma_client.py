# ── chroma_client.py ─────────────────────────────────────────────────
# In-memory vector store using numpy — no ChromaDB needed.
#
# KEY IMPROVEMENT: rebuild_from_sheets now reads embeddings stored
# in Google Sheets column 6 instead of re-calling Gemini API.
# Startup is instant and uses zero API quota.
#
# If a note has no stored embedding (old notes), it generates one
# and that's the only time the API is called.
# ─────────────────────────────────────────────────────────────────────

import json
import numpy as np
import streamlit as st


def _get_store() -> list:
    """Returns the in-memory vector store (persists across reruns via session_state)."""
    if "vector_store" not in st.session_state:
        st.session_state.vector_store = []
    return st.session_state.vector_store


def add_note_to_chroma(note_id: str, text: str, category: str, embedding: list):
    """Adds one note to the vector store. Skips duplicates."""
    store = _get_store()
    for entry in store:
        if entry["id"] == note_id:
            return
    store.append({
        "id": note_id,
        "text": text,
        "category": category,
        "embedding": embedding
    })


def search_similar_notes(query_embedding: list, n_results: int = 5) -> list:
    """
    Finds the most semantically similar notes to a query.
    Returns list of note text strings, most similar first.
    """
    results = search_similar_notes_with_scores(query_embedding, n_results)
    return [text for text, _ in results]


def search_similar_notes_with_scores(query_embedding: list, n_results: int = 5) -> list:
    """
    Like search_similar_notes but returns (text, score) tuples.
    Score is cosine similarity as a float 0–1.
    """
    store = _get_store()
    if not store:
        return []

    query_vec = np.array(query_embedding)
    scores = []
    for entry in store:
        vec = np.array(entry["embedding"])
        norm = np.linalg.norm(query_vec) * np.linalg.norm(vec)
        if norm == 0:
            continue
        sim = float(np.dot(query_vec, vec) / norm)
        scores.append((sim, entry["text"], entry["id"]))

    scores.sort(reverse=True)
    return [(text, sim) for sim, text, _ in scores[:n_results]]


def get_related_notes(note_embedding: list, exclude_id: str, n_results: int = 3) -> list:
    """
    Returns the top-N most similar notes to a given embedding,
    excluding the note itself. Returns (text, score) tuples.
    """
    store = _get_store()
    if not store:
        return []

    note_vec = np.array(note_embedding)
    scores = []
    for entry in store:
        if entry["id"] == exclude_id:
            continue
        vec = np.array(entry["embedding"])
        norm = np.linalg.norm(note_vec) * np.linalg.norm(vec)
        if norm == 0:
            continue
        sim = float(np.dot(note_vec, vec) / norm)
        scores.append((sim, entry["text"]))

    scores.sort(reverse=True)
    return [(text, sim) for sim, text in scores[:n_results]]


def get_all_notes_with_embeddings() -> dict:
    """
    Returns all notes with their embeddings.
    Used by brain_map.py to build the knowledge graph.
    """
    store = _get_store()
    if not store:
        return {"ids": [], "documents": [], "embeddings": [], "metadatas": []}

    return {
        "ids":        [e["id"]        for e in store],
        "documents":  [e["text"]      for e in store],
        "embeddings": [e["embedding"] for e in store],
        "metadatas":  [{"category": e["category"]} for e in store]
    }


def rebuild_from_sheets(brain_notes: list) -> int:
    """
    Rebuilds the vector store from Google Sheets data.

    NEW BEHAVIOUR:
    - If a note has an embedding stored in column 6 → use it directly (no API call)
    - If a note has no embedding (old notes) → generate it via Gemini API

    This means after the first rebuild, restarts are instant and free.
    """
    from ai.embeddings_client import get_embedding

    st.session_state.vector_store = []
    added = 0
    needs_generation = []

    for note in brain_notes:
        note_id  = str(note.get("note_id",  ""))
        content  = str(note.get("content",  ""))
        category = str(note.get("category", "Personal"))
        emb_str  = str(note.get("embedding", ""))

        if not note_id or not content:
            continue

        # Try to load stored embedding first
        if emb_str and emb_str.strip() not in ("", "[]"):
            try:
                embedding = json.loads(emb_str)
                if isinstance(embedding, list) and len(embedding) > 0:
                    add_note_to_chroma(note_id, content, category, embedding)
                    added += 1
                    continue
            except (json.JSONDecodeError, ValueError):
                pass  # fall through to generate

        # No stored embedding — queue for generation
        needs_generation.append((note_id, content, category))

    # Generate embeddings for notes that don't have them yet
    if needs_generation:
        for note_id, content, category in needs_generation:
            try:
                embedding = get_embedding(content)
                add_note_to_chroma(note_id, content, category, embedding)
                added += 1
            except Exception as e:
                raise Exception(f"Embedding failed for '{content[:40]}': {e}")

    return added


def get_note_count() -> int:
    """Returns how many notes are currently in the vector store."""
    return len(_get_store())