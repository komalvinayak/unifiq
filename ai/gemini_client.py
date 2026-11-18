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
from config.settings import GEMINI_KEYS, GROQ_API_KEY, GEMINI_MODEL, GROQ_MODEL, AVAILABLE_MODELS

# Try v1 first; newer models (gemini-2.0-*) may only exist in v1beta
_BASE_URL      = "https://generativelanguage.googleapis.com/v1/models"
_BASE_URL_BETA = "https://generativelanguage.googleapis.com/v1beta/models"

# Tracks which Gemini key to try first (rotates on rate limit)
_current_key_index = 0

# Which model the user has selected in the sidebar (index into AVAILABLE_MODELS)
_selected_model_idx = 0

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


def _get_selected_model_info() -> dict:
    """Returns the currently selected model's info dict from AVAILABLE_MODELS."""
    idx = max(0, min(_selected_model_idx, len(AVAILABLE_MODELS) - 1))
    return AVAILABLE_MODELS[idx]


def _get_gemini_response(prompt: str, key: str, model_id: str = None) -> str:
    """
    Tries the specified model (or primary) on v1, then v1beta.
    Raises so the caller can rotate keys or try the full fallback chain.
    """
    model = model_id or GEMINI_MODEL or "gemini-2.0-flash"
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


def _get_groq_response(prompt: str, model_id: str = None) -> str:
    """Calls Groq API with specified model, falling back through chain on failure."""
    client = Groq(api_key=GROQ_API_KEY)
    # If a specific model requested, try it first; then fallback chain
    fallback_chain = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "llama3-70b-8192",
        "llama3-8b-8192",
        "llama-3.1-8b-instant",
    ]
    if model_id:
        models_to_try = [model_id] + [m for m in fallback_chain if m != model_id]
    else:
        models_to_try = [GROQ_MODEL] + fallback_chain
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

    Routes to the user-selected model (from sidebar dropdown):
    - If Groq model selected → calls Groq directly with that model_id
    - If Gemini model selected → uses Gemini key rotation with that model_id
    - Fallback chain: if selected model fails, tries other providers
    """
    global _current_key_index, _last_generate_error

    selected = _get_selected_model_info()
    provider = selected["provider"]
    model_id = selected["model_id"]
    errors = []

    # ── Route: Groq selected ──────────────────────────────────────────
    if provider == "groq":
        if GROQ_API_KEY:
            try:
                result = _get_groq_response(prompt, model_id)
                _last_generate_error = ""
                return result
            except Exception as e:
                errors.append(f"Groq ({model_id}): {e}")
        else:
            errors.append("Groq: no API key configured")
        # Groq failed — fall through to Gemini as backup
        if GEMINI_KEYS:
            for attempt in range(len(GEMINI_KEYS)):
                key_index = (_current_key_index + attempt) % len(GEMINI_KEYS)
                key = GEMINI_KEYS[key_index]
                try:
                    result = _get_gemini_response(prompt, key)
                    _current_key_index = key_index
                    _last_generate_error = ""
                    return result
                except Exception as e:
                    errors.append(f"Gemini Key {key_index+1} (fallback): {e}")
        _last_generate_error = " | ".join(errors)
        return "AI is temporarily unavailable. Please try again in a minute."

    # ── Route: Gemini selected ────────────────────────────────────────
    for attempt in range(len(GEMINI_KEYS)):
        key_index = (_current_key_index + attempt) % len(GEMINI_KEYS)
        key = GEMINI_KEYS[key_index]

        try:
            result = _get_gemini_response(prompt, key, model_id)
            _current_key_index = key_index
            _last_generate_error = ""
            return result

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            errors.append(f"Key {key_index+1} HTTP {status}: {e}")
            if status == 429:
                continue  # rate limited — rotate to next key
            # Any other HTTP error — try full model fallback chain
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


def set_model(index: int):
    """Sets which model from AVAILABLE_MODELS the user has selected."""
    global _selected_model_idx
    if 0 <= index < len(AVAILABLE_MODELS):
        _selected_model_idx = index


def get_model_index() -> int:
    """Returns the current selected model index."""
    return _selected_model_idx


def get_selected_model_display() -> str:
    """Returns the display name of the currently selected model."""
    return _get_selected_model_info()["display"]