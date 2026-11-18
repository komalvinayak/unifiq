# ── brain_map.py ─────────────────────────────────────────────────────
# Visual knowledge map — shows all your notes as a connected graph.
#
# How it works:
# 1. Get all notes + their vectors from ChromaDB
# 2. For each note, find its 2 most similar neighbors
# 3. Draw a node (dot) for each note
# 4. Draw an edge (line) between similar notes
# 5. Color nodes by category (Work=blue, Learning=green, Personal=orange)
# 6. Render as interactive HTML using Pyvis
# ─────────────────────────────────────────────────────────────────────

import streamlit as st
import streamlit.components.v1 as components
import networkx as nx
from pyvis.network import Network
import numpy as np
from database.chroma_client import get_all_notes_with_embeddings


# Color for each category
CATEGORY_COLORS = {
    "Work": "#3B82F6",       # blue
    "Learning": "#10B981",   # green
    "Personal": "#F59E0B",   # orange
}


def cosine_similarity(vec1: list, vec2: list) -> float:
    """
    Calculates how similar two vectors are.

    Result is between -1 and 1:
    - 1.0 = identical meaning
    - 0.0 = unrelated
    - Negative = opposite meaning

    We show connections when similarity > 0.75
    """
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def build_graph(notes_data: dict) -> nx.Graph:
    """
    Builds a NetworkX graph from notes.
    Nodes = notes, Edges = similar notes.
    """
    G = nx.Graph()

    ids = notes_data["ids"]
    documents = notes_data["documents"]
    embeddings = notes_data["embeddings"]
    metadatas = notes_data["metadatas"]

    if not ids:
        return G

    # Add all notes as nodes
    for i, note_id in enumerate(ids):
        text = documents[i] if documents else ""
        category = metadatas[i].get("category", "Personal") if metadatas else "Personal"
        color = CATEGORY_COLORS.get(category, "#94A3B8")

        # Short label for display (first 30 chars)
        label = text[:30] + "..." if len(text) > 30 else text

        G.add_node(
            note_id,
            label=label,
            title=text,       # shown on hover
            color=color,
            category=category,
            size=20
        )

    # Add edges between similar notes
    if embeddings:
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                similarity = cosine_similarity(embeddings[i], embeddings[j])
                # Only connect notes that are meaningfully similar
                if similarity > 0.75:
                    G.add_edge(ids[i], ids[j], weight=similarity)

    return G


def render_map():
    """
    Creates and displays the interactive brain map.
    """
    st.subheader("Your Knowledge Map")
    st.caption("Each dot is a note. Lines connect related thoughts. Hover to read. Drag to explore.")

    # Get all notes with their vectors from ChromaDB
    notes_data = get_all_notes_with_embeddings()

    if not notes_data["ids"]:
        st.info("No notes yet. Add some notes in 'Dump Thought' first.")
        return

    note_count = len(notes_data["ids"])
    st.write(f"**{note_count} notes** in your brain")

    # Build the graph
    G = build_graph(notes_data)

    if G.number_of_nodes() == 0:
        st.warning("Could not build map. Try adding more notes.")
        return

    # ── CREATE PYVIS VISUALIZATION ───────────────────────────────────
    net = Network(
        height="500px",
        width="100%",
        bgcolor="#0A0F1E",      # dark background
        font_color="#E2E8F0",   # light text
        notebook=False
    )

    # Physics settings — makes the graph animate nicely
    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "stabilization": {"iterations": 100},
        "barnesHut": {
          "gravitationalConstant": -8000,
          "springLength": 150
        }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100
      }
    }
    """)

    # Add NetworkX graph to Pyvis
    net.from_nx(G)

    # Save to a temporary HTML file
    map_path = "/tmp/brain_map.html"
    net.save_graph(map_path)

    # Embed in Streamlit
    with open(map_path, "r", encoding="utf-8") as f:
        html = f.read()

    components.html(html, height=520, scrolling=False)

    # ── LEGEND ───────────────────────────────────────────────────────
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.markdown("🔵 **Work**")
    col2.markdown("🟢 **Learning**")
    col3.markdown("🟠 **Personal**")
