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
from config.settings import GEMINI_KEYS, GROQ_API_KEY, AVAILABLE_MODELS, BRAIN_CATEGORIES
from database.sheets_client import get_all_rows
from database.chroma_client import rebuild_from_sheets, get_note_count
from modules.brain.brain_core import categorize_note, save_note, categorize_note_with_confidence, detect_mood

# ── QUICK CAPTURE DIALOG ─────────────────────────────────────────────
_HAS_DIALOG = hasattr(st, "dialog")

_QC_ADD_NEW = "➕ Add new category…"

if _HAS_DIALOG:
    @st.dialog("✍️ Quick Capture")
    def _quick_capture_dialog():
        thought = st.text_area(
            "Drop your thought…", height=120,
            placeholder="Idea, learning, vent — anything on your mind.",
            key="qc_thought",
        )

        # Build category list from base + any user-added ones
        _custom = st.session_state.get("qc_custom_categories", [])
        _all_cats = BRAIN_CATEGORIES + [c for c in _custom if c not in BRAIN_CATEGORIES]

        cat_choice = st.selectbox(
            "Category",
            options=["🤖 Auto-detect"] + _all_cats + [_QC_ADD_NEW],
            key="qc_cat_select",
        )

        new_cat_name = ""
        if cat_choice == _QC_ADD_NEW:
            new_cat_name = st.text_input(
                "New category name", placeholder="e.g. Health, Travel…",
                key="qc_new_cat_input",
            ).strip()

        if st.button("Save ⚡", type="primary", use_container_width=True, key="qc_save_btn"):
            if not thought.strip():
                st.warning("Write something first.")
                return

            # Resolve final category
            if cat_choice == _QC_ADD_NEW:
                if not new_cat_name:
                    st.warning("Enter a name for the new category.")
                    return
                final_cat = new_cat_name.title()
                # Persist the new category for this session
                _custom_updated = st.session_state.get("qc_custom_categories", [])
                if final_cat not in _custom_updated:
                    _custom_updated.append(final_cat)
                st.session_state["qc_custom_categories"] = _custom_updated
                conf = 100
            elif cat_choice == "🤖 Auto-detect":
                with st.spinner("Detecting category…"):
                    final_cat, conf = categorize_note_with_confidence(thought.strip())
            else:
                final_cat = cat_choice
                conf = 100

            with st.spinner("Saving…"):
                mood = detect_mood(thought.strip())
                save_note(thought.strip(), final_cat, conf, mood)
                st.session_state.pop("brain_notes_cache", None)
                st.session_state.chroma_note_count = get_note_count()
            st.success(f"✅ Saved as **{final_cat}**")
            st.rerun()


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

# ── FLOATING QUICK CAPTURE BUTTON ────────────────────────────────────
st.markdown("""
<style>
a.qc-fab {
    position: fixed;
    bottom: 30px; right: 30px;
    z-index: 9999;
    background: #4F46E5; color: #fff !important;
    border-radius: 50px;
    padding: 12px 22px;
    font-size: 15px; font-weight: 600;
    text-decoration: none !important;
    box-shadow: 0 4px 15px rgba(79,70,229,0.4);
    transition: background 0.15s;
    white-space: nowrap;
    letter-spacing: 0.01em;
}
a.qc-fab:hover { background: #4338CA !important; }
</style>
<a class="qc-fab" href="?qc_open=1">✍️ Quick Capture</a>
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


# ── MAIN ─────────────────────────────────────────────────────────────

# Quick Capture via floating button (query param trigger)
# Use new st.query_params (Streamlit ≥ 1.30) or fall back to experimental API
try:
    _qc_params = st.query_params
    _qc_open = _qc_params.get("qc_open") == "1"
    if _qc_open and "qc_open" in _qc_params:
        del _qc_params["qc_open"]
except AttributeError:
    _raw = st.experimental_get_query_params()
    _qc_open = _raw.get("qc_open", [""])[0] == "1"
    if _qc_open:
        st.experimental_set_query_params()

if _qc_open:
    if _HAS_DIALOG:
        _quick_capture_dialog()
    else:
        st.session_state["show_qc_fallback"] = True

# Fallback capture form (Streamlit < 1.37)
if not _HAS_DIALOG and st.session_state.get("show_qc_fallback"):
    with st.container():
        st.markdown("### ✍️ Quick Capture")
        _fb_custom = st.session_state.get("qc_custom_categories", [])
        _fb_cats = BRAIN_CATEGORIES + [c for c in _fb_custom if c not in BRAIN_CATEGORIES]
        with st.form("qc_fallback_form"):
            thought = st.text_area("Drop your thought…", height=100)
            cat_choice_fb = st.selectbox("Category", ["🤖 Auto-detect"] + _fb_cats + [_QC_ADD_NEW])
            new_cat_fb = ""
            if cat_choice_fb == _QC_ADD_NEW:
                new_cat_fb = st.text_input("New category name", placeholder="e.g. Health, Travel…").strip()
            c1, c2 = st.columns([3, 1])
            submitted = c1.form_submit_button("Save instantly ⚡", type="primary")
            cancelled = c2.form_submit_button("✕ Close")
        if cancelled:
            st.session_state.pop("show_qc_fallback", None)
            st.rerun()
        if submitted:
            if thought.strip():
                if cat_choice_fb == _QC_ADD_NEW:
                    if not new_cat_fb:
                        st.warning("Enter a name for the new category.")
                    else:
                        final_cat_fb = new_cat_fb.title()
                        _fb_upd = st.session_state.get("qc_custom_categories", [])
                        if final_cat_fb not in _fb_upd:
                            _fb_upd.append(final_cat_fb)
                        st.session_state["qc_custom_categories"] = _fb_upd
                        conf_fb = 100
                        with st.spinner("Saving…"):
                            mood = detect_mood(thought.strip())
                            save_note(thought.strip(), final_cat_fb, conf_fb, mood)
                            st.session_state.pop("brain_notes_cache", None)
                            st.session_state.chroma_note_count = get_note_count()
                        st.success(f"✅ Saved as **{final_cat_fb}**")
                        st.session_state.pop("show_qc_fallback", None)
                        st.rerun()
                elif cat_choice_fb == "🤖 Auto-detect":
                    with st.spinner("Saving…"):
                        cat_fb, conf_fb = categorize_note_with_confidence(thought.strip())
                        mood = detect_mood(thought.strip())
                        save_note(thought.strip(), cat_fb, conf_fb, mood)
                        st.session_state.pop("brain_notes_cache", None)
                        st.session_state.chroma_note_count = get_note_count()
                    st.success(f"✅ Saved as **{cat_fb}**")
                    st.session_state.pop("show_qc_fallback", None)
                    st.rerun()
                else:
                    with st.spinner("Saving…"):
                        mood = detect_mood(thought.strip())
                        save_note(thought.strip(), cat_choice_fb, 100, mood)
                        st.session_state.pop("brain_notes_cache", None)
                        st.session_state.chroma_note_count = get_note_count()
                    st.success(f"✅ Saved as **{cat_choice_fb}**")
                    st.session_state.pop("show_qc_fallback", None)
                    st.rerun()
            else:
                st.warning("Write something first.")
        st.divider()

from modules.brain.brain_core import show
show()
