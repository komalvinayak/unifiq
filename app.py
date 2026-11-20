# ── app.py ───────────────────────────────────────────────────────────
# Mufakkir — "Ctrl+F for your brain."
# ─────────────────────────────────────────────────────────────────────

import streamlit as st

st.set_page_config(
    page_title="Mufakkir",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

from utils.date_utils import now_date_str, now_time_str
from ai.gemini_client import get_last_error, set_model, get_model_index, get_selected_model_display
from ai.embeddings_client import set_key_index as set_embed_key_index
from config.settings import GEMINI_KEYS, GROQ_API_KEY, AVAILABLE_MODELS
from database.sheets_client import get_all_rows
from database.chroma_client import rebuild_from_sheets, get_note_count
from modules.brain.brain_core import categorize_note, save_note


# ── STARTUP ──────────────────────────────────────────────────────────
if "chroma_initialized" not in st.session_state:
    with st.spinner("Loading Mufakkir…"):
        try:
            brain_notes = get_all_rows("brain_notes")
            if brain_notes:
                rebuild_from_sheets(brain_notes)
                st.session_state.chroma_note_count = get_note_count()
                st.session_state.chroma_error = None
            else:
                st.session_state.chroma_note_count = 0
                st.session_state.chroma_error = None
        except Exception as e:
            st.session_state.chroma_note_count = 0
            st.session_state.chroma_error = str(e)
    st.session_state.chroma_initialized = True


# ── LIGHT NOTION THEME ───────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stMain"], .main {
    background: #FFFFFF !important;
    color: #1E1E2E !important;
}
[data-testid="stSidebar"] {
    background: #F8F9FA !important;
    border-right: 1px solid #E5E7EB;
}
/* Remove default top padding */
.block-container { padding-top: 1.5rem; }

/* ── Typography ── */
h1,h2,h3,h4,h5,h6 { color: #1E1E2E !important; }
p, label, .stMarkdown { color: #374151 !important; }

/* ── Buttons ── */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    border: 1px solid #E5E7EB !important;
    background: #FFFFFF !important;
    color: #1E1E2E !important;
    transition: all 0.15s ease;
}
.stButton > button[kind="primary"] {
    background: #4F46E5 !important;
    color: #FFFFFF !important;
    border-color: #4F46E5 !important;
}
.stButton > button:hover {
    border-color: #4F46E5 !important;
    color: #4F46E5 !important;
}
.stButton > button[kind="primary"]:hover {
    background: #4338CA !important;
    color: #FFFFFF !important;
}

/* ── Inputs ── */
.stTextInput input, .stTextArea textarea,
.stSelectbox > div > div {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 8px !important;
    color: #1E1E2E !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #4F46E5 !important;
    box-shadow: 0 0 0 3px rgba(79,70,229,0.1) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab"] {
    color: #6B7280 !important;
    font-weight: 500;
}
.stTabs [aria-selected="true"] {
    color: #4F46E5 !important;
    border-bottom-color: #4F46E5 !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: #F8F9FA !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 10px !important;
    padding: 12px !important;
}
[data-testid="stMetricValue"] { color: #1E1E2E !important; }
[data-testid="stMetricLabel"] { color: #6B7280 !important; }

/* ── Expanders ── */
details summary {
    color: #1E1E2E !important;
    background: #F8F9FA !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
}

/* ── Divider ── */
hr { border-color: #E5E7EB !important; }

/* ── Sidebar caption ── */
.stSidebar .stCaption { color: #6B7280 !important; }
</style>
""", unsafe_allow_html=True)


# ── SIDEBAR ──────────────────────────────────────────────────────────
with st.sidebar:
    # Logo + title
    st.markdown("""
<div style="margin-bottom:4px;">
  <span style="font-size:26px;font-weight:800;color:#1E1E2E;letter-spacing:-0.5px;">🧠 Mufakkir</span>
</div>
<div style="font-size:12px;color:#6B7280;margin-bottom:16px;font-style:italic;">
  Ctrl+F for your brain.
</div>
""", unsafe_allow_html=True)

    st.divider()

    # System Status
    st.caption("**System Status**")

    _avail = [
        (i, m) for i, m in enumerate(AVAILABLE_MODELS)
        if (m["provider"] == "gemini" and GEMINI_KEYS)
        or (m["provider"] == "groq" and GROQ_API_KEY)
    ]
    if _avail:
        _avail_indices = [i for i, _ in _avail]
        _avail_labels  = {i: m["display"] for i, m in _avail}
        _cur_model_idx = get_model_index()
        if _cur_model_idx not in _avail_indices:
            _cur_model_idx = _avail_indices[0]
        selected_model_idx = st.selectbox(
            "🤖 AI Model",
            options=_avail_indices,
            format_func=lambda i: _avail_labels[i],
            index=_avail_indices.index(_cur_model_idx),
            key="sidebar_ai_model_select",
        )
        set_model(selected_model_idx)
        selected_model = AVAILABLE_MODELS[selected_model_idx]
        set_embed_key_index(0 if selected_model["provider"] == "groq" else 0)
    else:
        st.write("🤖 AI: No keys configured")

    note_count = st.session_state.get("chroma_note_count", 0)
    st.write(f"🧠 `{note_count} notes indexed`")

    if st.session_state.get("chroma_error"):
        st.error(f"⚠️ {st.session_state.chroma_error}")

    ai_err = get_last_error()
    if ai_err:
        with st.expander("⚠️ AI error details"):
            st.code(ai_err, language=None)

    if note_count == 0:
        if st.button("🔄 Rebuild Index"):
            st.session_state.pop("chroma_initialized", None)
            st.rerun()

    st.write(f"📅 `{now_date_str()}`  🕐 `{now_time_str()} IST`")
    st.divider()

    # Quick Capture
    st.caption("**⚡ Quick Capture**")
    quick_note = st.text_area(
        "Quick thought",
        placeholder="Type a thought and press Save…",
        height=80,
        label_visibility="collapsed",
        key="sidebar_quick_note"
    )
    if st.button("Save 🧠", use_container_width=True, key="sidebar_save_btn", type="primary"):
        if quick_note.strip():
            with st.spinner("Saving…"):
                try:
                    category = categorize_note(quick_note.strip())
                    save_note(quick_note.strip(), category)
                    st.session_state.chroma_note_count = get_note_count()
                    st.session_state.pop("brain_notes_cache", None)
                    st.success(f"✅ {category}")
                    st.session_state.sidebar_quick_note = ""
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")
        else:
            st.warning("Write something first.")


# ── MAIN ─────────────────────────────────────────────────────────────
from modules.brain.brain_core import show
show()
