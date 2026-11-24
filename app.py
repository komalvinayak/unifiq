# ── app.py ───────────────────────────────────────────────────────────
# Mufakkir — "Ctrl+F for your brain."
# ─────────────────────────────────────────────────────────────────────

import streamlit as st

st.set_page_config(
    page_title="Mufakkir",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── CUSTOM FAVICON ───────────────────────────────────────────────────
st.markdown("""
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ccircle cx='50' cy='50' r='48' fill='%234F46E5'/%3E%3Cg stroke='white' stroke-linecap='round' transform='translate(50,50)'%3E%3Cline x1='0' y1='-8' x2='0' y2='-42' stroke-width='3' stroke-opacity='0.95'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-28' stroke-width='2' stroke-opacity='0.6' transform='rotate(22.5)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-42' stroke-width='3' stroke-opacity='0.95' transform='rotate(45)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-28' stroke-width='2' stroke-opacity='0.6' transform='rotate(67.5)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-42' stroke-width='3' stroke-opacity='0.95' transform='rotate(90)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-28' stroke-width='2' stroke-opacity='0.6' transform='rotate(112.5)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-42' stroke-width='3' stroke-opacity='0.95' transform='rotate(135)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-28' stroke-width='2' stroke-opacity='0.6' transform='rotate(157.5)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-42' stroke-width='3' stroke-opacity='0.95' transform='rotate(180)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-28' stroke-width='2' stroke-opacity='0.6' transform='rotate(202.5)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-42' stroke-width='3' stroke-opacity='0.95' transform='rotate(225)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-28' stroke-width='2' stroke-opacity='0.6' transform='rotate(247.5)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-42' stroke-width='3' stroke-opacity='0.95' transform='rotate(270)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-28' stroke-width='2' stroke-opacity='0.6' transform='rotate(292.5)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-42' stroke-width='3' stroke-opacity='0.95' transform='rotate(315)'/%3E%3Cline x1='0' y1='-8' x2='0' y2='-28' stroke-width='2' stroke-opacity='0.6' transform='rotate(337.5)'/%3E%3C/g%3E%3Ccircle cx='50' cy='50' r='8' fill='white' opacity='0.95'/%3E%3Ccircle cx='50' cy='50' r='4' fill='white'/%3E%3C/svg%3E">
""", unsafe_allow_html=True)


from utils.date_utils import now_date_str, now_time_str
from ai.gemini_client import get_last_error, set_model, get_model_index, get_selected_model_display
from ai.embeddings_client import set_key_index as set_embed_key_index
from config.settings import GEMINI_KEYS, GROQ_API_KEY, AVAILABLE_MODELS, BRAIN_CATEGORIES
from database.sheets_client import get_all_rows
from database.chroma_client import rebuild_from_sheets, get_note_count
from modules.brain.brain_core import categorize_note, save_note, categorize_note_with_confidence, detect_mood
from modules.brain.brain_rag import rag_answer


def mufakkir_spinner(text="Ctrl+F in progress..."):
    return st.spinner(text)


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
                with mufakkir_spinner("Detecting category…"):
                    final_cat, conf = categorize_note_with_confidence(thought.strip())
            else:
                final_cat = cat_choice
                conf = 100

            with mufakkir_spinner("Saving…"):
                mood = detect_mood(thought.strip())
                save_note(thought.strip(), final_cat, conf, mood)
                st.session_state.pop("brain_notes_cache", None)
                st.session_state.chroma_note_count = get_note_count()
            st.success(f"✅ Saved as **{final_cat}**")
            st.rerun()


# ── ASK MY BRAIN DIALOG ──────────────────────────────────────────────
if _HAS_DIALOG:
    @st.dialog("🔍 Ask My Brain", width="large")
    def _ask_brain_dialog():
        if "brain_chat" not in st.session_state:
            st.session_state.brain_chat = []

        # Chat history
        for msg in st.session_state.brain_chat[-6:]:  # show last 6 messages
            if msg["role"] == "user":
                st.markdown(
                    f'<div style="text-align:right;margin:6px 0;">'
                    f'<span style="background:#4F46E5;color:#fff;border-radius:16px 16px 4px 16px;'
                    f'padding:8px 14px;font-size:0.9rem;display:inline-block;max-width:85%;">'
                    f'{msg["content"]}</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="margin:6px 0;">'
                    f'<span style="background:#F8F9FA;border:1px solid #E5E7EB;color:#1E1E2E;'
                    f'border-radius:16px 16px 16px 4px;padding:8px 14px;font-size:0.9rem;'
                    f'display:inline-block;max-width:85%;">{msg["content"]}</span></div>',
                    unsafe_allow_html=True,
                )
                sources = msg.get("sources", [])
                top_src = [(n, s) for n, s in sources if s >= 0.35]
                if top_src:
                    with st.expander(f"📌 {len(top_src)} source(s) from your notes"):
                        for nd, sc in top_src[:3]:
                            st.caption(f"**{nd.get('category','')}** · {nd.get('date','')} — {nd.get('content','')[:120]}…")

        if not st.session_state.brain_chat:
            st.markdown(
                '<div style="text-align:center;padding:20px 0 10px;">'
                '<div style="font-size:2rem;margin-bottom:8px;">🧠</div>'
                '<div style="color:#6B7280;font-size:0.95rem;">Ask anything about your notes — or just chat!</div>'
                '</div>',
                unsafe_allow_html=True,
            )

        st.divider()
        with st.form("ask_brain_form", clear_on_submit=True):
            q = st.text_input("Question", placeholder="What have I been thinking about lately?",
                              label_visibility="collapsed")
            c1, c2 = st.columns([4, 1])
            submitted = c1.form_submit_button("Ask 🧠", type="primary", use_container_width=True)
            cleared   = c2.form_submit_button("Clear", use_container_width=True)

        if cleared:
            st.session_state.brain_chat = []
            st.session_state["_ask_brain_open"] = True
            st.rerun()

        if submitted and q.strip():
            with mufakkir_spinner("Thinking…"):
                try:
                    answer, sources = rag_answer(q.strip())
                except Exception as e:
                    answer, sources = f"❌ Error: {e}", []
            st.session_state.brain_chat.append({"role": "user", "content": q.strip(), "sources": []})
            st.session_state.brain_chat.append({"role": "assistant", "content": answer, "sources": sources})
            st.session_state["_ask_brain_open"] = True
            st.rerun()


# ── STARTUP ──────────────────────────────────────────────────────────
if "chroma_initialized" not in st.session_state:
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


# ── ONE-TIME SPLASH SCREEN ───────────────────────────────────────────
if not st.session_state.get("splash_shown"):
    st.session_state["splash_shown"] = True
    st.markdown("""
<style>
#mufakkir-splash {
    position: fixed; inset: 0; z-index: 999999;
    background: #FFFFFF;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    animation: splash-out 0.5s ease-out 2.5s forwards;
    pointer-events: all;
}
@keyframes splash-out {
    0%   { opacity: 1; pointer-events: all; }
    100% { opacity: 0; pointer-events: none; }
}
body:has([data-testid="stHorizontalBlock"]) #mufakkir-splash {
    animation: splash-out 0.4s ease-out forwards;
}
.splash-starburst { animation: splash-spin 3s linear infinite; }
@keyframes splash-spin {
    from { transform: rotate(0deg); }
    to   { transform: rotate(360deg); }
}
</style>
<div id="mufakkir-splash">
  <div class="splash-starburst">
    <svg viewBox="0 0 200 200" width="110" height="110" xmlns="http://www.w3.org/2000/svg">
      <circle cx="100" cy="100" r="92" fill="none" stroke="#EEF2FF" stroke-width="2"/>
      <g stroke-linecap="round" transform="translate(100,100)">
        <line x1="0" y1="-18" x2="0" y2="-84" stroke="#4F46E5" stroke-width="4" opacity="0.95"/>
        <line x1="0" y1="-18" x2="0" y2="-84" stroke="#4F46E5" stroke-width="4" opacity="0.95" transform="rotate(45)"/>
        <line x1="0" y1="-18" x2="0" y2="-84" stroke="#4F46E5" stroke-width="4" opacity="0.95" transform="rotate(90)"/>
        <line x1="0" y1="-18" x2="0" y2="-84" stroke="#4F46E5" stroke-width="4" opacity="0.95" transform="rotate(135)"/>
        <line x1="0" y1="-18" x2="0" y2="-84" stroke="#4F46E5" stroke-width="4" opacity="0.95" transform="rotate(180)"/>
        <line x1="0" y1="-18" x2="0" y2="-84" stroke="#4F46E5" stroke-width="4" opacity="0.95" transform="rotate(225)"/>
        <line x1="0" y1="-18" x2="0" y2="-84" stroke="#4F46E5" stroke-width="4" opacity="0.95" transform="rotate(270)"/>
        <line x1="0" y1="-18" x2="0" y2="-84" stroke="#4F46E5" stroke-width="4" opacity="0.95" transform="rotate(315)"/>
        <line x1="0" y1="-18" x2="0" y2="-56" stroke="#818CF8" stroke-width="2" opacity="0.5" transform="rotate(22.5)"/>
        <line x1="0" y1="-18" x2="0" y2="-56" stroke="#818CF8" stroke-width="2" opacity="0.5" transform="rotate(67.5)"/>
        <line x1="0" y1="-18" x2="0" y2="-56" stroke="#818CF8" stroke-width="2" opacity="0.5" transform="rotate(112.5)"/>
        <line x1="0" y1="-18" x2="0" y2="-56" stroke="#818CF8" stroke-width="2" opacity="0.5" transform="rotate(157.5)"/>
        <line x1="0" y1="-18" x2="0" y2="-56" stroke="#818CF8" stroke-width="2" opacity="0.5" transform="rotate(202.5)"/>
        <line x1="0" y1="-18" x2="0" y2="-56" stroke="#818CF8" stroke-width="2" opacity="0.5" transform="rotate(247.5)"/>
        <line x1="0" y1="-18" x2="0" y2="-56" stroke="#818CF8" stroke-width="2" opacity="0.5" transform="rotate(292.5)"/>
        <line x1="0" y1="-18" x2="0" y2="-56" stroke="#818CF8" stroke-width="2" opacity="0.5" transform="rotate(337.5)"/>
      </g>
      <circle cx="100" cy="100" r="16" fill="#4F46E5" opacity="0.95"/>
      <circle cx="100" cy="100" r="8" fill="#6366F1"/>
    </svg>
  </div>
  <div style="margin-top:24px;font-size:28px;font-weight:800;color:#1E1E2E;letter-spacing:-0.5px;">🧠 Mufakkir</div>
  <div style="margin-top:8px;font-size:14px;color:#6B7280;font-style:italic;">Ctrl+F for your brain.</div>
</div>
""", unsafe_allow_html=True)


# ── LIGHT NOTION THEME ───────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stMain"], .main {
    background: #FFFFFF !important;
    color: #1E1E2E !important;
}
/* Hide sidebar, Streamlit's header, status widget */
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
header[data-testid="stHeader"],
[data-testid="stStatusWidget"],
#MainMenu,
footer { display: none !important; }

/* ── Remove top whitespace only, keep side padding ── */
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section.main { padding-top: 0 !important; margin-top: 0 !important; }

/* Force full-width — remove sidebar DOM space */
[data-testid="stSidebar"] { width: 0 !important; min-width: 0 !important; }
[data-testid="stMain"], section.main {
    margin-left: 0 !important;
    max-width: 100% !important;
    width: 100% !important;
}

/* Proper content padding — like a real website */
.block-container {
    padding-top: 0 !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 1400px !important;
}

/* ── Navbar: bleed full-width out of the padded container ── */
[data-testid="stMain"] [data-testid="stHorizontalBlock"]:first-of-type {
    background: #FFFFFF;
    border-bottom: 2px solid #E5E7EB;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    padding: 10px 2rem !important;
    margin-left: -2rem !important;
    margin-right: -2rem !important;
    margin-bottom: 16px !important;
    width: calc(100% + 4rem) !important;
}
/* Align navbar columns vertically */
[data-testid="stMain"] [data-testid="stHorizontalBlock"]:first-of-type > div {
    display: flex;
    align-items: center;
}
.nav-brand {
    font-size: 19px;
    font-weight: 700;
    color: #1E1E2E;
    display: flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
}
.nav-tagline {
    font-size: 12px;
    color: #9CA3AF;
    margin-left: 8px;
    font-weight: 400;
}
.nav-right {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #4F46E5;
    font-family: monospace;
    white-space: nowrap;
    justify-content: flex-end;
}
/* Compact selectbox — ONLY inside the navbar (first horizontal block) */
[data-testid="stHorizontalBlock"]:first-of-type [data-testid="stSelectbox"] > div > div {
    min-height: 34px !important;
    font-size: 13px !important;
    font-family: monospace !important;
    color: #4F46E5 !important;
    border-color: #C7D2FE !important;
    background: #EEF2FF !important;
}

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
    white-space: nowrap !important;
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

/* ── Custom Mufakkir Spinner ── */
div[data-testid="stSpinner"] {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
}
div[data-testid="stSpinner"] > div {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 16px;
    font-weight: 600;
    color: #4F46E5;
}
div[data-testid="stSpinner"]::before {
    content: "⚡🔥";
    font-size: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100px;
    height: 100px;
    border-radius: 50%;
    background: rgba(79, 70, 229, 0.08);
    border: 3px solid rgba(79, 70, 229, 0.2);
    animation: mufakkir-pulse 1.5s ease-in-out infinite;
    margin-bottom: 12px;
}
@keyframes mufakkir-pulse {
    0%   { transform: scale(1);    box-shadow: 0 0 0 0 rgba(79,70,229,0.3); }
    50%  { transform: scale(1.08); box-shadow: 0 0 0 15px rgba(79,70,229,0); }
    100% { transform: scale(1);    box-shadow: 0 0 0 0 rgba(79,70,229,0); }
}
</style>
""", unsafe_allow_html=True)

# ── FLOATING ACTION BUTTONS ───────────────────────────────────────────
st.markdown("""
<style>
.fab-stack {
    position: fixed;
    bottom: 30px; right: 30px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 10px;
}
a.qc-fab, a.ask-fab {
    border-radius: 50px;
    padding: 11px 20px;
    font-size: 14px; font-weight: 600;
    text-decoration: none !important;
    box-shadow: 0 4px 15px rgba(79,70,229,0.35);
    transition: background 0.15s;
    white-space: nowrap;
    letter-spacing: 0.01em;
    display: inline-block;
}
a.qc-fab { background: #4F46E5; color: #fff !important; }
a.qc-fab:hover { background: #4338CA !important; }
a.ask-fab { background: #FFFFFF; color: #4F46E5 !important; border: 2px solid #4F46E5; }
a.ask-fab:hover { background: #EEF2FF !important; }
</style>
<div class="fab-stack">
  <a class="ask-fab" href="?ask_open=1" target="_top">🔍 Ask My Brain</a>
  <a class="qc-fab" href="?qc_open=1" target="_top">✍️ Quick Capture</a>
</div>
""", unsafe_allow_html=True)


# ── TOP NAVBAR ───────────────────────────────────────────────────────
_note_count = st.session_state.get("chroma_note_count", 0)

_avail = [
    (i, m) for i, m in enumerate(AVAILABLE_MODELS)
    if (m["provider"] == "gemini" and GEMINI_KEYS)
    or (m["provider"] == "groq" and GROQ_API_KEY)
]

nav_col1, nav_col2, nav_col3 = st.columns([4, 2, 4], gap="small")

with nav_col1:
    st.markdown(
        '<div class="nav-brand">🧠 Mufakkir'
        '<span class="nav-tagline">Ctrl+F for your brain.</span></div>',
        unsafe_allow_html=True,
    )

with nav_col2:
    if _avail:
        _avail_indices = [i for i, _ in _avail]
        _avail_labels  = {i: m["display"] for i, m in _avail}
        _cur_model_idx = get_model_index()
        if _cur_model_idx not in _avail_indices:
            _cur_model_idx = _avail_indices[0]
        selected_model_idx = st.selectbox(
            "AI Model",
            options=_avail_indices,
            format_func=lambda i: f"🤖 {_avail_labels[i]}",
            index=_avail_indices.index(_cur_model_idx),
            key="navbar_ai_model_select",
            label_visibility="collapsed",
        )
        set_model(selected_model_idx)
        set_embed_key_index(0)
    else:
        st.markdown('<span style="color:#9CA3AF;font-size:12px;font-family:monospace;">🤖 No AI configured</span>', unsafe_allow_html=True)

with nav_col3:
    _ai_err = get_last_error()
    _err_badge = ' <span style="color:#DC2626;">⚠️</span>' if _ai_err else ""
    _chroma_err = st.session_state.get("chroma_error", "")
    st.markdown(
        f'<div class="nav-right">'
        f'🧠&nbsp;{_note_count}&nbsp;notes&nbsp;&nbsp;|&nbsp;&nbsp;'
        f'📅&nbsp;{now_date_str()}&nbsp;&nbsp;🕐&nbsp;{now_time_str()}&nbsp;IST'
        f'{_err_badge}</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div style="border-bottom:1px solid #E5E7EB;margin-bottom:16px;"></div>', unsafe_allow_html=True)

# Show errors / rebuild button inline (below navbar)
if _ai_err or _chroma_err or _note_count == 0:
    with st.expander("⚙️ System status", expanded=False):
        if _chroma_err:
            st.error(f"⚠️ {_chroma_err}")
        if _ai_err:
            st.code(_ai_err, language=None)
        if _note_count == 0:
            if st.button("🔄 Rebuild Index"):
                st.session_state.pop("chroma_initialized", None)
                st.rerun()

# ── MAIN ─────────────────────────────────────────────────────────────

# Quick Capture via floating button (query param trigger)
# Use new st.query_params (Streamlit ≥ 1.30) or fall back to experimental API
try:
    _qc_params = st.query_params
    _qc_open = _qc_params.get("qc_open") == "1"
    if _qc_open and "qc_open" in _qc_params:
        del _qc_params["qc_open"]
    _ask_open = _qc_params.get("ask_open") == "1"
    if _ask_open and "ask_open" in _qc_params:
        del _qc_params["ask_open"]
except AttributeError:
    _raw = st.experimental_get_query_params()
    _qc_open = _raw.get("qc_open", [""])[0] == "1"
    _ask_open = _raw.get("ask_open", [""])[0] == "1"
    if _qc_open or _ask_open:
        st.experimental_set_query_params()

# Latch into session state so the dialog survives st.rerun() after answering
if _ask_open:
    st.session_state["_ask_brain_open"] = True

if _qc_open:
    if _HAS_DIALOG:
        _quick_capture_dialog()
    else:
        st.session_state["show_qc_fallback"] = True

if st.session_state.get("_ask_brain_open"):
    if _HAS_DIALOG:
        st.session_state["_ask_brain_open"] = False   # clear before dialog opens; rerun inside dialog re-sets it
        _ask_brain_dialog()

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
                        with mufakkir_spinner("Saving…"):
                            mood = detect_mood(thought.strip())
                            save_note(thought.strip(), final_cat_fb, conf_fb, mood)
                            st.session_state.pop("brain_notes_cache", None)
                            st.session_state.chroma_note_count = get_note_count()
                        st.success(f"✅ Saved as **{final_cat_fb}**")
                        st.session_state.pop("show_qc_fallback", None)
                        st.rerun()
                elif cat_choice_fb == "🤖 Auto-detect":
                    with mufakkir_spinner("Saving…"):
                        cat_fb, conf_fb = categorize_note_with_confidence(thought.strip())
                        mood = detect_mood(thought.strip())
                        save_note(thought.strip(), cat_fb, conf_fb, mood)
                        st.session_state.pop("brain_notes_cache", None)
                        st.session_state.chroma_note_count = get_note_count()
                    st.success(f"✅ Saved as **{cat_fb}**")
                    st.session_state.pop("show_qc_fallback", None)
                    st.rerun()
                else:
                    with mufakkir_spinner("Saving…"):
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
