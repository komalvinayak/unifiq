# ── embeddings_client.py ─────────────────────────────────────────────
# Converts text into embedding vectors using Google's v1 REST API.
#
# KEY ROTATION:
#   Tries GEMINI_KEY_1, then GEMINI_KEY_2, then GEMINI_KEY_3 etc.
#   On 429 (rate limit) → automatically moves to the next key.
#   On network error    → retries same call up to 3 times with backoff.
#   The _current_key_index persists within the session so the last
#   working key is tried first on the next call.
#
# WHY REST NOT google-generativeai:
#   The library uses v1beta internally. Embedding models live in v1 only.
#   Calling REST directly fixes this.
# ─────────────────────────────────────────────────────────────────────

import time
import requests
from config.settings import GEMINI_KEYS

_BASE_URL = "https://generativelanguage.googleapis.com/v1/models"
_MODEL    = "gemini-embedding-001"

# Tracks which key is currently active — rotates on 429
_current_key_index = 0


def _embed(text: str, task_type: str) -> list:
    """
    Core embedding call with full key rotation + network retry.

    Flow:
      1. Try current key
      2. If 429 (rate limit) → rotate to next key, try again
      3. If network error   → wait 1 s and retry (same key, up to 3 times)
      4. If all keys exhausted → raise with a clear message
    """
    global _current_key_index

    if not GEMINI_KEYS:
        raise ValueError("No Gemini API keys found. Add GEMINI_KEY_1 to your .env file.")

    url  = f"{_BASE_URL}/{_MODEL}:embedContent"
    body = {
        "model":   f"models/{_MODEL}",
        "content": {"parts": [{"text": text}]},
        "taskType": task_type,
    }

    last_error   = None
    keys_tried   = 0
    total_keys   = len(GEMINI_KEYS)

    while keys_tried < total_keys:
        key = GEMINI_KEYS[_current_key_index]

        # Network retry loop for the current key
        for net_attempt in range(3):
            try:
                resp = requests.post(
                    url,
                    json=body,
                    params={"key": key},
                    headers={"Content-Type": "application/json"},
                    timeout=20,
                )

                if resp.status_code == 429:
                    # Rate limited — stop retrying THIS key, rotate to next
                    last_error = Exception(
                        f"Key {_current_key_index + 1} rate limited (429)"
                    )
                    break  # exits network retry loop → triggers key rotation

                resp.raise_for_status()   # raises for 4xx / 5xx
                _current_key_index = (_current_key_index) % total_keys  # keep
                return resp.json()["embedding"]["values"]

            except requests.exceptions.ConnectionError as e:
                # DNS failure, refused connection, timeout — network issue
                last_error = e
                if net_attempt < 2:
                    time.sleep(1.0 * (net_attempt + 1))  # 1s, then 2s
                    continue
                break  # 3 network failures on this key → rotate

            except requests.exceptions.Timeout as e:
                last_error = e
                if net_attempt < 2:
                    time.sleep(1.5)
                    continue
                break

            except requests.exceptions.HTTPError as e:
                # 4xx / 5xx that isn't 429 — not retryable, raise immediately
                raise

        # Rotate to the next key
        _current_key_index = (_current_key_index + 1) % total_keys
        keys_tried += 1

    # All keys and retries exhausted
    raise Exception(
        f"Embedding failed after trying all {total_keys} key(s). "
        f"Last error: {last_error}"
    )


def get_embedding(text: str) -> list:
    """
    Converts a note/document text into a vector for storage.
    Uses RETRIEVAL_DOCUMENT task type (optimised for indexing).

    Example:
        "study financial ratios" → [0.023, -0.145, ... 3072 numbers]
    """
    return _embed(text, "RETRIEVAL_DOCUMENT")


def get_query_embedding(question: str) -> list:
    """
    Converts a search question into a vector for querying.
    Uses RETRIEVAL_QUERY task type for better search accuracy.

    Example:
        "what did I write about finance?" → [0.018, -0.132, ... 3072 numbers]
    """
    return _embed(question, "RETRIEVAL_QUERY")


def get_active_key_name() -> str:
    """Returns which embedding key is active — for the sidebar status widget."""
    if GEMINI_KEYS:
        return f"Gemini Key {_current_key_index + 1}"
    return "No key"


def set_key_index(index: int):
    """Sync the embed key to match the user's AI key selection."""
    global _current_key_index
    if 0 <= index < len(GEMINI_KEYS):
        _current_key_index = index