# ── app.py ────────────────────────────────────────────────────────────
# UNIFIQ — Unified Intelligence
# Main entry point for the Streamlit app.
#
# What this file does:
# 1. Sets up the page (title, icon, layout)
# 2. Builds the sidebar navigation
# 3. On first load — rebuilds ChromaDB from Google Sheets (hybrid persistence)
# 4. Renders whichever module the user has selected
#
# To run: streamlit run app.py
# ─────────────────────────────────────────────────────────────────────

import streamlit as st

# ── PAGE CONFIG (must be first Streamlit call) ────────────────────────
st.set_page_config(
    page_title="UNIFIQ",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── IMPORTS ──────────────────────────────────────────────────────────
from utils.date_utils import now_date_str, now_time_str, greeting
from ai.gemini_client import get_active_key_name
from ai.embeddings_client import get_active_key_name as get_embed_key_name
from database.sheets_client import get_all_rows
from database.chroma_client import rebuild_from_sheets, get_note_count
from modules.brain.brain_core import categorize_note, save_note


# ── STARTUP: REBUILD CHROMADB ─────────────────────────────────────────
# This runs once per session (when the app first loads).
# ChromaDB can be wiped on Streamlit Cloud restarts.
# We rebuild it from Google Sheets so brain search always works.

if "chroma_initialized" not in st.session_state:
    with st.spinner("Initializing UNIFIQ Brain..."):
        try:
            brain_notes = get_all_rows("brain_notes")
            if brain_notes:
                added = rebuild_from_sheets(brain_notes)
                st.session_state.chroma_note_count = get_note_count()
                st.session_state.chroma_error = None
            else:
                st.session_state.chroma_note_count = 0
                st.session_state.chroma_error = None
        except Exception as e:
            st.session_state.chroma_note_count = 0
            st.session_state.chroma_error = str(e)

    st.session_state.chroma_initialized = True


# ── CUSTOM STYLES ────────────────────────────────────────────────────
# Minimal CSS to make it look cleaner
st.markdown("""
<style>
    /* Sidebar title */
    .sidebar-title {
        font-size: 22px;
        font-weight: 700;
        color: #E2E8F0;
        margin-bottom: 4px;
    }
    .sidebar-sub {
        font-size: 11px;
        color: #94A3B8;
        margin-bottom: 20px;
    }
    /* Remove default top padding */
    .block-container {
        padding-top: 1.5rem;
    }
    /* Metric card styling */
    [data-testid="stMetric"] {
        background: rgba(255,255,255,0.03);
        border-radius: 8px;
        padding: 10px;
        border: 1px solid rgba(255,255,255,0.08);
    }
</style>
""", unsafe_allow_html=True)


# ── SIDEBAR ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-title">⚡ UNIFIQ</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-sub">Unified Intelligence</div>', unsafe_allow_html=True)

    st.divider()

    # Navigation
    page = st.radio(
        "Navigate",
        options=[
            "🏠 Command Centre",
            "📋 Project & Task Manager",
            "🧠 UNIFIQ Brain",
        ],
        label_visibility="collapsed"
    )

    st.divider()

    # System info
    st.caption("**System Status**")
    ai_key   = get_active_key_name()
    emb_key  = get_embed_key_name()
    # Show single line if both use same key, two lines if different
    if ai_key == emb_key:
        st.write(f"🤖 AI: `{ai_key}`")
    else:
        st.write(f"🤖 AI: `{ai_key}`  ·  Embed: `{emb_key}`")
    note_count = st.session_state.get("chroma_note_count", 0)
    st.write(f"🧠 Brain: `{note_count} notes indexed`")
    if st.session_state.get("chroma_error"):
        st.error(f"⚠️ Brain index error: {st.session_state.chroma_error}")
    if note_count == 0:
        if st.button("🔄 Rebuild Brain Index"):
            st.session_state.pop("chroma_initialized", None)
            st.rerun()
    st.write(f"📅 `{now_date_str()}`")
    st.write(f"🕐 `{now_time_str()} IST`")

    st.divider()

    # ── QUICK CAPTURE ────────────────────────────────────────────────
    # Always-visible capture box — zero friction to save a thought
    st.caption("**⚡ Quick Capture**")
    quick_note = st.text_area(
        "Quick thought",
        placeholder="Type a thought and press Save…",
        height=80,
        label_visibility="collapsed",
        key="sidebar_quick_note"
    )
    if st.button("Save 🧠", use_container_width=True, key="sidebar_save_btn"):
        if quick_note.strip():
            with st.spinner("Saving…"):
                try:
                    category = categorize_note(quick_note.strip())
                    save_note(quick_note.strip(), category)
                    st.session_state.chroma_note_count = get_note_count()
                    st.session_state.pop("brain_notes_cache", None)
                    st.success(f"✅ {category}")
                    # Clear the box by resetting the key
                    st.session_state.sidebar_quick_note = ""
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")
        else:
            st.warning("Write something first.")


# ── PAGE ROUTING ─────────────────────────────────────────────────────
# Based on what user clicked in sidebar, show the right module

if page == "🏠 Command Centre":
    from modules.command_centre import show
    show()

elif page == "📋 Project & Task Manager":
    from modules.project_task_manager import show
    show()

elif page == "🧠 UNIFIQ Brain":
    from modules.brain.brain_core import show

    # Add brain map as a separate section below
    show()

    st.divider()

    # Brain Map (visual knowledge graph)
    st.subheader("🗺️ Brain Map")
    st.caption("Visual map of all your notes. Similar thoughts are connected.")

    if st.button("Show Brain Map", use_container_width=True):
        from modules.brain.brain_map import render_map
        render_map()