# ── chroma_client.py ─────────────────────────────────────────────────
# Manages ChromaDB — the vector database for UNIFIQ Brain.
#
# Hybrid Persistence Strategy:
# - Google Sheets = permanent storage (source of truth)
# - ChromaDB = search index (rebuilt from Sheets on startup)
#
# This solves the Streamlit Cloud problem:
# Even if the server restarts and ChromaDB is wiped,
# we just rebuild it from Google Sheets in a few seconds.
# ─────────────────────────────────────────────────────────────────────

import chromadb
from config.settings import CHROMA_PATH, CHROMA_COLLECTION


# In-memory ChromaDB — data is rebuilt from Google Sheets on every startup
# This avoids disk corruption issues on Streamlit Cloud restarts
_chroma_client = None

def get_collection():
    """
    Returns the ChromaDB collection.
    Uses EphemeralClient (in-memory) since we rebuild from Sheets on every startup.
    """
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.EphemeralClient()
    
    collection = _chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )
    return collection


def add_note_to_chroma(note_id: str, text: str, category: str, embedding: list):
    """
    Adds one note to ChromaDB with its vector.

    What gets stored:
    - note_id: unique ID (matches Google Sheets)
    - text: the actual note content
    - category: Work / Learning / Personal
    - embedding: the vector (list of 768 numbers)
    """
    collection = get_collection()

    # Check if this note already exists (avoid duplicates on rebuild)
    existing = collection.get(ids=[note_id])
    if existing["ids"]:
        return  # already in ChromaDB, skip

    collection.add(
        ids=[note_id],
        documents=[text],
        embeddings=[embedding],
        metadatas=[{"category": category}]
    )


def search_similar_notes(query_embedding: list, n_results: int = 5) -> list:
    """
    Finds the most similar notes to a question.

    How it works:
    1. We convert the question to a vector (done before calling this)
    2. ChromaDB compares that vector to all stored note vectors
    3. Returns the top n_results most similar notes

    Returns a list of note texts.
    """
    collection = get_collection()

    # Check how many notes are stored
    count = collection.count()
    if count == 0:
        return []

    # Don't ask for more results than we have
    actual_results = min(n_results, count)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=actual_results,
        include=["documents", "metadatas", "distances"]
    )

    # Return just the text documents
    if results["documents"]:
        return results["documents"][0]
    return []


def get_all_notes_with_embeddings() -> dict:
    """
    Returns all notes stored in ChromaDB.
    Used for building the brain map visualization.

    Returns dict with ids, documents, embeddings, metadatas.
    """
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return {"ids": [], "documents": [], "embeddings": [], "metadatas": []}

    return collection.get(include=["documents", "embeddings", "metadatas"])


def rebuild_from_sheets(brain_notes: list):
    """
    Rebuilds the ChromaDB index from Google Sheets data.
    Called once on app startup.

    brain_notes: list of dicts from the brain_notes sheet
    Each dict has: note_id, content, category, embedding (stored as string in Sheets)

    Why we do this:
    Streamlit Cloud can restart anytime, wiping ChromaDB.
    But Google Sheets never loses data.
    So on every startup we rebuild ChromaDB from Sheets.
    """
    from ai.embeddings_client import get_embedding

    added = 0
    for note in brain_notes:
        note_id = str(note.get("note_id", ""))
        content = str(note.get("content", ""))
        category = str(note.get("category", "Personal"))

        if not note_id or not content:
            continue

        try:
            # Generate embedding for this note
            embedding = get_embedding(content)
            # Add to ChromaDB (skips if already exists)
            add_note_to_chroma(note_id, content, category, embedding)
            added += 1
        except Exception as e:
            raise Exception(f"Embedding failed: {e}")

    return added


def get_note_count() -> int:
    """Returns how many notes are in ChromaDB"""
    return get_collection().count()
