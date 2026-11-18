# ── brain_map.py ─────────────────────────────────────────────────────
# Visual knowledge map with category-first navigation.
#
# Default view: hub-spoke layout — category nodes in center,
#               notes radiating outward, similarity lines between them.
# Click a category button → zooms into just that category's notes.
# ─────────────────────────────────────────────────────────────────────

import os
import tempfile
import numpy as np
import networkx as nx
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network
from database.chroma_client import get_all_notes_with_embeddings


CATEGORY_COLORS = {
    "Work":      "#3B82F6",
    "Learning":  "#10B981",
    "Personal":  "#F59E0B",
    "Technical": "#8B5CF6",
    "Career":    "#EF4444",
}

CATEGORY_EMOJI = {
    "Work": "💼", "Learning": "📚",
    "Personal": "🌱", "Technical": "💻", "Career": "🎯",
}


# ── helpers ──────────────────────────────────────────────────────────

def _cosine(a, b) -> float:
    a, b = np.array(a), np.array(b)
    n = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / n) if n else 0.0


def _render_pyvis(G: nx.Graph, height: int = 560):
    """Build a Pyvis network from G and embed it in Streamlit."""
    if G.number_of_nodes() == 0:
        st.info("No notes in this category yet. Add a note first.")
        return

    net = Network(
        height=f"{height}px",
        width="100%",
        bgcolor="#FFFFFF",
        font_color="#1E293B",
        notebook=False,
    )
    net.set_options("""
    {
      "nodes": {
        "borderWidth": 2,
        "borderWidthSelected": 4,
        "shadow": {
          "enabled": true,
          "size": 10,
          "x": 2,
          "y": 2
        },
        "font": {
          "size": 13,
          "face": "Inter, Arial, sans-serif",
          "bold": {"mod": "bold"}
        }
      },
      "edges": {
        "smooth": {"type": "dynamic"},
        "shadow": false
      },
      "physics": {
        "enabled": true,
        "stabilization": {"iterations": 200, "fit": true},
        "barnesHut": {
          "gravitationalConstant": -12000,
          "springLength": 180,
          "springConstant": 0.03,
          "damping": 0.09
        }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 50,
        "navigationButtons": true,
        "keyboard": true,
        "zoomView": true
      }
    }
    """)
    net.from_nx(G)

    # Write to current directory — works on Windows and Linux
    map_path = "brain_map_temp.html"
    net.write_html(map_path)

    with open(map_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Inject custom CSS for white background + tooltip styling + legend overlay
    style_inject = """
    <style>
      body, html { background: #FFFFFF !important; margin: 0; padding: 0; }
      #mynetwork {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%) !important;
        border: 1.5px solid #e2e8f0;
        border-radius: 12px;
      }
      div.vis-tooltip {
        background: #1E293B !important;
        color: #F1F5F9 !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 10px 14px !important;
        font-size: 13px !important;
        max-width: 320px !important;
        white-space: pre-wrap !important;
        word-break: break-word !important;
        line-height: 1.6 !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.25) !important;
      }
      #map-legend {
        position: absolute;
        top: 12px;
        right: 12px;
        background: rgba(255,255,255,0.92);
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 10px 14px;
        font-family: Inter, Arial, sans-serif;
        font-size: 12px;
        line-height: 2;
        z-index: 999;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        pointer-events: none;
      }
    </style>
    """

    legend_html = """
    <div id="map-legend">
      <div style="font-weight:700; color:#1E293B; margin-bottom:4px; font-size:11px; letter-spacing:0.05em; text-transform:uppercase;">Categories</div>
      <div style="color:#3B82F6"><span style="font-size:16px">●</span> Work</div>
      <div style="color:#10B981"><span style="font-size:16px">●</span> Learning</div>
      <div style="color:#F59E0B"><span style="font-size:16px">●</span> Personal</div>
      <div style="color:#8B5CF6"><span style="font-size:16px">●</span> Technical</div>
      <div style="color:#EF4444"><span style="font-size:16px">●</span> Career</div>
      <div style="margin-top:6px; padding-top:6px; border-top:1px solid #e2e8f0; color:#94A3B8; font-size:11px;">- - - similar notes</div>
    </div>
    """

    html = html.replace("</head>", style_inject + "</head>")
    html = html.replace("</body>", legend_html + "</body>")

    components.html(html, height=height + 20, scrolling=False)


# ── graph builders ───────────────────────────────────────────────────

def _build_overview(notes_data: dict) -> nx.Graph:
    """
    Hub-spoke layout:
    • Large category nodes in the middle
    • Smaller note nodes connected to their category
    • Thin lines between notes that are semantically similar
    """
    G = nx.Graph()

    ids        = notes_data["ids"]
    documents  = notes_data["documents"]
    embeddings = notes_data["embeddings"]
    metadatas  = notes_data["metadatas"]

    # Count per category
    cat_counts: dict[str, int] = {}
    for m in metadatas:
        c = m.get("category", "Personal")
        cat_counts[c] = cat_counts.get(c, 0) + 1

    # Category hub nodes
    for cat, count in cat_counts.items():
        color = CATEGORY_COLORS.get(cat, "#94A3B8")
        emoji = CATEGORY_EMOJI.get(cat, "📝")
        G.add_node(
            f"CAT_{cat}",
            label=f"{emoji} {cat}\n({count} notes)",
            title=f"📂 {cat}\n{count} note{'s' if count != 1 else ''} in this category",
            color={"background": color, "border": color,
                   "highlight": {"background": color, "border": "#1E293B"}},
            size=58,
            shape="dot",
            font={"size": 15, "color": "#FFFFFF", "bold": True},
        )

    # Note nodes + category edges
    for i, note_id in enumerate(ids):
        cat   = metadatas[i].get("category", "Personal")
        text  = documents[i]
        color = CATEGORY_COLORS.get(cat, "#94A3B8")
        # Short label for display, FULL text in tooltip
        label = text[:20] + "…" if len(text) > 20 else text
        tooltip = f"📝 {cat}\n\n{text}"

        G.add_node(
            note_id,
            label=label,
            title=tooltip,
            color={"background": color + "CC",   # slightly transparent
                   "border": color,
                   "highlight": {"background": color, "border": "#1E293B"}},
            size=20,
            shape="dot",
            font={"size": 11, "color": "#1E293B"},
        )
        G.add_edge(f"CAT_{cat}", note_id,
                   color={"color": color + "55", "highlight": color},
                   width=1.5, dashes=False)

    # Similarity edges between notes
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if embeddings[i] and embeddings[j]:
                sim = _cosine(embeddings[i], embeddings[j])
                if sim > 0.70:
                    G.add_edge(
                        ids[i], ids[j],
                        color={"color": "#94A3B8", "highlight": "#475569"},
                        width=max(1, int(sim * 3)),
                        dashes=True,
                        title=f"🔗 Related — {sim:.0%} similar",
                    )
    return G


def _build_category_graph(notes_data: dict, category: str) -> nx.Graph:
    """
    Zoomed-in view of one category:
    • All notes from that category as nodes
    • Lines between semantically similar notes
    """
    G = nx.Graph()

    ids        = notes_data["ids"]
    documents  = notes_data["documents"]
    embeddings = notes_data["embeddings"]
    metadatas  = notes_data["metadatas"]

    color      = CATEGORY_COLORS.get(category, "#94A3B8")
    cat_idx    = [i for i, m in enumerate(metadatas)
                  if m.get("category") == category]

    if not cat_idx:
        return G

    for i in cat_idx:
        text  = documents[i]
        label = text[:30] + "…" if len(text) > 30 else text
        G.add_node(
            ids[i],
            label=label,
            title=text,
            color=color,
            size=25,
            shape="dot",
        )

    # Similarity edges (lower threshold so notes connect more)
    for a in range(len(cat_idx)):
        for b in range(a + 1, len(cat_idx)):
            i, j = cat_idx[a], cat_idx[b]
            if embeddings[i] and embeddings[j]:
                sim = _cosine(embeddings[i], embeddings[j])
                if sim > 0.50:
                    G.add_edge(
                        ids[i], ids[j],
                        color=color,
                        width=max(1, int(sim * 4)),
                        title=f"Similarity: {sim:.0%}",
                    )
    return G


# ── main renderer ────────────────────────────────────────────────────

def render_map():
    st.subheader("🗺️ Your Knowledge Map")
    st.caption("Click a category to explore its notes. Hover over any dot to read it.")

    notes_data = get_all_notes_with_embeddings()

    if not notes_data["ids"]:
        st.info("No notes yet. Add some notes in 'Dump Thought' first.")
        return

    total = len(notes_data["ids"])

    # Notes per category
    cat_counts: dict[str, int] = {}
    for m in notes_data["metadatas"]:
        c = m.get("category", "Personal")
        cat_counts[c] = cat_counts.get(c, 0) + 1

    # ── CATEGORY BUTTONS ─────────────────────────────────────────────
    if "map_category" not in st.session_state:
        st.session_state.map_category = "All"

    active_cats = ["All"] + [c for c in CATEGORY_COLORS if c in cat_counts]
    cols = st.columns(len(active_cats))

    for i, cat in enumerate(active_cats):
        if cat == "All":
            lbl = f"🌐 All  ({total})"
        else:
            lbl = f"{CATEGORY_EMOJI.get(cat,'📝')} {cat}  ({cat_counts[cat]})"

        is_active = (st.session_state.map_category == cat)
        if cols[i].button(lbl, key=f"mapcat_{cat}",
                          type="primary" if is_active else "secondary",
                          use_container_width=True):
            st.session_state.map_category = cat
            st.rerun()

    st.divider()

    # ── GRAPH / CARDS ────────────────────────────────────────────────
    selected = st.session_state.map_category

    if selected == "All":
        st.write(f"**{total} notes** — large circles = categories, small circles = notes")
        G = _build_overview(notes_data)
        _render_pyvis(G, height=540)
    else:
        # Show notes as readable cards — more useful than a sub-graph
        color = CATEGORY_COLORS.get(selected, "#94A3B8")
        emoji = CATEGORY_EMOJI.get(selected, "📝")
        count = cat_counts.get(selected, 0)

        st.markdown(
            f"<span style='color:{color}; font-size:1.1rem'>●</span> "
            f"**{selected}** — {count} note{'s' if count != 1 else ''}",
            unsafe_allow_html=True,
        )
        st.divider()

        # Pull matching notes from vector store
        ids       = notes_data["ids"]
        documents = notes_data["documents"]
        metadatas = notes_data["metadatas"]

        cat_notes = [
            {"id": ids[i], "text": documents[i]}
            for i, m in enumerate(metadatas)
            if m.get("category") == selected
        ]

        if not cat_notes:
            st.info(f"No notes in {selected} yet.")
        else:
            for note in cat_notes:
                st.markdown(
                    f"""<div style="
                        background: rgba(255,255,255,0.04);
                        border-left: 4px solid {color};
                        border-radius: 8px;
                        padding: 14px 18px;
                        margin-bottom: 12px;
                        color: #E2E8F0;
                        font-size: 0.95rem;
                        line-height: 1.6;
                    ">{note['text']}</div>""",
                    unsafe_allow_html=True,
                )