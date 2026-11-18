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

_BASE_URL = "https://generativelanguage.googleapis.com/v1/models"

# Tracks which Gemini key to try first (rotates on rate limit)
_current_key_index = 0


def _get_gemini_response(prompt: str, key: str) -> str:
    """
    Calls Gemini text generation via REST v1 API.
    Raises an exception if the call fails so the caller can rotate keys.
    """
    # Try the configured model, fall back to gemini-2.0-flash
    model = GEMINI_MODEL or "gemini-2.0-flash"

    url = f"{_BASE_URL}/{model}:generateContent"
    body = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1500,
        }
    }

    response = requests.post(
        url,
        json=body,
        params={"key": key},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    # Extract text from response
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _get_groq_response(prompt: str) -> str:
    """
    Calls Groq API as a backup.
    Groq is free and very fast — uses Llama 3 model.
    """
    client = Groq(api_key=GROQ_API_KEY)
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000
    )
    return completion.choices[0].message.content


def generate(prompt: str) -> str:
    """
    Main function — call this from anywhere in the app.

    How it works:
    1. Try Gemini Key 1 → if rate limited, try Key 2 → try Key 3
    2. If ALL Gemini keys fail → fall back to Groq
    3. If Groq also fails → return an error message

    This means your app NEVER stops working due to rate limits.
    """
    global _current_key_index

    # Try each Gemini key
    for attempt in range(len(GEMINI_KEYS)):
        key_index = (_current_key_index + attempt) % len(GEMINI_KEYS)
        key = GEMINI_KEYS[key_index]

        try:
            result = _get_gemini_response(prompt, key)
            _current_key_index = key_index  # remember working key
            return result

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            if status == 429:
                continue  # rate limited — try next key
            if status == 404:
                # Model name might be wrong — try gemini-1.5-flash directly
                try:
                    result = _get_gemini_response_fallback(prompt, key)
                    _current_key_index = key_index
                    return result
                except Exception:
                    continue
            continue  # other HTTP error — try next key

        except Exception:
            continue  # network or parse error — try next key

    # All Gemini keys failed — try Groq as backup
    if GROQ_API_KEY:
        try:
            return _get_groq_response(prompt)
        except Exception:
            pass

    return "AI is temporarily unavailable. Please try again in a minute."


def _get_gemini_response_fallback(prompt: str, key: str) -> str:
    """Fallback through all known working models."""
    for model in [
        "gemini-2.0-flash",        # newest — try first
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-1.5-flash-002",
        "gemini-1.5-flash-8b",
        "gemini-1.5-pro",
        "gemini-pro",
    ]:
        try:
            url = f"{_BASE_URL}/{model}:generateContent"
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1500}
            }
            r = requests.post(url, json=body, params={"key": key},
                              headers={"Content-Type": "application/json"}, timeout=30)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            continue
    raise Exception("All fallback models failed")


def get_active_key_name() -> str:
    """Returns which key is currently active — shown in sidebar."""
    if GEMINI_KEYS:
        return f"Gemini Key {_current_key_index + 1}"
    return "Groq (backup)"


def set_key_index(index: int):
    """Lets user manually switch to a different key from the sidebar."""
    global _current_key_index
    if 0 <= index < len(GEMINI_KEYS):
        _current_key_index = index