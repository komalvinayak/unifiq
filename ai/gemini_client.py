# ── gemini_client.py ─────────────────────────────────────────────────
# Handles all calls to Gemini AI via direct REST API.
#
# WHY REST INSTEAD OF google-generativeai LIBRARY:
# The library doesn't support newer API key formats (AQ.xxx).
# Calling the v1 REST endpoint directly works with all key formats.
#
# Key rotation: tries each Gemini key in order
# If all Gemini keys fail → automatically falls back to Groq
# ─────────────────────────────────────────────────────────────────────

import requests
from groq import Groq
from config.settings import GEMINI_KEYS, GROQ_API_KEY, GEMINI_MODEL, GROQ_MODEL

# Try v1 first; newer models (gemini-2.0-*) may only exist in v1beta
_BASE_URL      = "https://generativelanguage.googleapis.com/v1/models"
_BASE_URL_BETA = "https://generativelanguage.googleapis.com/v1beta/models"

# Tracks which Gemini key to try first (rotates on rate limit)
_current_key_index = 0

# Last error from generate() — shown in sidebar for diagnostics
_last_generate_error = ""


def _post_gemini(url: str, prompt: str, key: str) -> str:
    """Single REST call to a Gemini endpoint. Raises on any failure."""
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1500},
    }
    r = requests.post(
        url, json=body,
        params={"key": key},
        headers={"Content-Type": "application/json"},
        timeout=8,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _get_gemini_response(prompt: str, key: str) -> str:
    """
    Tries the primary model on v1, then v1beta.
    Raises so the caller can rotate keys or try the full fallback chain.
    """
    model = GEMINI_MODEL or "gemini-2.0-flash"
    last_exc = None
    for base in [_BASE_URL, _BASE_URL_BETA]:
        try:
            return _post_gemini(f"{base}/{model}:generateContent", prompt, key)
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            if status == 404:
                last_exc = e
                continue   # model not in this API version — try the other
            raise          # 429, 403, 400, etc. → let caller handle
        except Exception as e:
            last_exc = e
    raise last_exc or Exception(f"Model {model} unreachable on v1 and v1beta")


def _get_groq_response(prompt: str) -> str:
    """Calls Groq API as a backup, trying several models in order."""
    client = Groq(api_key=GROQ_API_KEY)
    # Ordered by reliability — if primary is deprecated, next one is tried
    models_to_try = [
        GROQ_MODEL,
        "llama3-70b-8192",
        "llama3-8b-8192",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
    ]
    last_exc = None
    for model in dict.fromkeys(models_to_try):  # deduplicate, preserve order
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
            )
            return completion.choices[0].message.content
        except Exception as e:
            last_exc = e
            continue
    raise last_exc or Exception("All Groq models failed")


def generate(prompt: str) -> str:
    """
    Main function — call this from anywhere in the app.

    How it works:
    1. Try primary model on v1 + v1beta for each key (rotating on 429)
    2. On any non-429 HTTP error → try full model fallback chain for that key
    3. If all Gemini keys exhaust → fall back to Groq
    4. If Groq also fails → return error message (graceful degradation in brain_rag)
    """
    global _current_key_index, _last_generate_error

    errors = []

    # Try each Gemini key
    for attempt in range(len(GEMINI_KEYS)):
        key_index = (_current_key_index + attempt) % len(GEMINI_KEYS)
        key = GEMINI_KEYS[key_index]

        try:
            result = _get_gemini_response(prompt, key)
            _current_key_index = key_index
            _last_generate_error = ""
            return result

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            errors.append(f"Key {key_index+1} HTTP {status}: {e}")
            if status == 429:
                continue  # rate limited — rotate to next key
            # Any other HTTP error (404, 403, 400) — try full model fallback
            try:
                result = _get_gemini_response_fallback(prompt, key)
                _current_key_index = key_index
                _last_generate_error = ""
                return result
            except Exception as fe:
                errors.append(f"Key {key_index+1} fallback: {fe}")
                continue

        except Exception as e:
            errors.append(f"Key {key_index+1}: {e}")
            continue

    # All Gemini keys failed — try Groq as backup
    if GROQ_API_KEY:
        try:
            result = _get_groq_response(prompt)
            _last_generate_error = ""
            return result
        except Exception as e:
            errors.append(f"Groq: {e}")

    _last_generate_error = " | ".join(errors)
    return "AI is temporarily unavailable. Please try again in a minute."


def _get_gemini_response_fallback(prompt: str, key: str) -> str:
    """Fallback through all known working models on both v1 and v1beta."""
    for model in [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-1.5-flash-002",
        "gemini-1.5-flash-8b",
        "gemini-1.5-pro",
        "gemini-pro",
    ]:
        for base in [_BASE_URL, _BASE_URL_BETA]:
            try:
                return _post_gemini(f"{base}/{model}:generateContent", prompt, key)
            except Exception:
                continue
    raise Exception("All fallback models failed on v1 and v1beta")


def get_last_error() -> str:
    """Returns the last error from generate() — used in sidebar diagnostics."""
    return _last_generate_error


def get_active_key_name() -> str:
    """Returns which key is currently active — shown in sidebar."""
    if GEMINI_KEYS:
        return f"Gemini Key {_current_key_index + 1}"
    return "Groq (backup)"


def get_key_index() -> int:
    """Returns the current key index."""
    return _current_key_index


def set_key_index(index: int):
    """Lets user manually switch to a different key from the sidebar."""
    global _current_key_index
    if 0 <= index < len(GEMINI_KEYS):
        _current_key_index = index