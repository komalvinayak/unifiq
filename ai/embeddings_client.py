# ── embeddings_client.py ─────────────────────────────────────────────
# Converts text into vectors (lists of numbers) using Google's API
#
# Why do we need this?
# Regular databases search by exact words.
# Vectors let us search by MEANING.
# "Good managers listen" and "leadership requires empathy"
# are similar in meaning — vectors capture that, words don't.
# ─────────────────────────────────────────────────────────────────────

import google.generativeai as genai
from config.settings import GEMINI_KEYS, EMBEDDING_MODEL


def get_embedding(text: str) -> list:
    """
    Converts a piece of text into a vector (list of 768 numbers).

    Example:
        "I need to study financial ratios"
        → [0.023, -0.145, 0.087, ... 768 numbers total]

    Two similar texts will have similar number lists.
    That's how semantic search works.
    """
    if not GEMINI_KEYS:
        raise ValueError("No Gemini API key found. Check your .env file.")

    # Use the first available key for embeddings
    genai.configure(api_key=GEMINI_KEYS[0])

    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
        task_type="retrieval_document"  # tells Google this is for search
    )

    return result["embedding"]


def get_query_embedding(question: str) -> list:
    """
    Converts a QUESTION into a vector.

    We use a different task_type for questions vs documents.
    This improves search accuracy.
    """
    if not GEMINI_KEYS:
        raise ValueError("No Gemini API key found. Check your .env file.")

    genai.configure(api_key=GEMINI_KEYS[0])

    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=question,
        task_type="retrieval_query"  # tells Google this is a search query
    )

    return result["embedding"]
