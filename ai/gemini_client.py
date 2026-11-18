# ── gemini_client.py ─────────────────────────────────────────────────
# Handles all calls to Gemini AI
# Key rotation: tries each Gemini key in order
# If all Gemini keys fail → automatically falls back to Groq
# ─────────────────────────────────────────────────────────────────────

import google.generativeai as genai
from groq import Groq
from config.settings import GEMINI_KEYS, GROQ_API_KEY, GEMINI_MODEL, GROQ_MODEL

# This variable tracks which Gemini key we are currently using
# It persists during the app session
_current_key_index = 0


def _get_gemini_response(prompt: str, key: str) -> str:
    """
    Calls Gemini API with a specific key.
    Returns the text response.
    Raises an exception if rate limited or any error.
    """
    genai.configure(api_key=key)
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(prompt)
    return response.text


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
            # Success — remember this key index for next call
            _current_key_index = key_index
            return result

        except Exception as e:
            error_msg = str(e).lower()
            # Rate limit hit — try next key
            if "quota" in error_msg or "rate" in error_msg or "429" in error_msg:
                continue
            # Different error — still try next key
            continue

    # All Gemini keys failed — try Groq as backup
    if GROQ_API_KEY:
        try:
            return _get_groq_response(prompt)
        except Exception:
            pass

    return "AI is temporarily unavailable. Please try again in a minute."


def get_active_key_name() -> str:
    """
    Returns which key is currently active — shown in sidebar.
    Example: 'Gemini Key 2'
    """
    if GEMINI_KEYS:
        return f"Gemini Key {_current_key_index + 1}"
    return "Groq (backup)"


def set_key_index(index: int):
    """
    Lets user manually switch to a different key from the sidebar.
    """
    global _current_key_index
    if 0 <= index < len(GEMINI_KEYS):
        _current_key_index = index
