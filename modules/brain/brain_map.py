import math
import streamlit as st
import plotly.graph_objects as go

CATEGORY_COLORS = {
    "Work":      "#4F46E5",
    "Learning":  "#16A34A",
    "Personal":  "#D97706",
    "Technical": "#7C3AED",
    "Career":    "#DC2626",
}
_DEFAULT_COLOR = "#64748b"


def _render_legend():
    items = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:18px;">'
        f'<span style="width:11px;height:11px;border-radius:50%;background:{color};'
        f'display:inline-block;flex-shrink:0;"></span>'
        f'<span style="font-size:0.82rem;color:#334155;">{cat}</span></span>'
        for cat, color in CATEGORY_COLORS.items()
    )
    st.markdown(
        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;'
        f'border-radius:8px;padding:10px 14px;display:flex;flex-wrap:wrap;align-items:center;'
        f'gap:4px;margin-bottom:12px;">'
        f'{items}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _cluster_by_category(rows):
    groups: dict[str, list] = {}
    for r in rows:
        cat = r.get("category", "Personal") or "Personal"
        groups.setdefault(cat, []).append(r.get("content", ""))

    result = []
    for cat, notes in groups.items():
        color = CATEGORY_COLORS.get(cat, _DEFAULT_COLOR)
        result.append({"notes": notes, "color": color, "label": cat})

    result.sort(key=lambda x: len(x["notes"]), reverse=True)
    return result


def _cluster_positions(n):
    if n == 1:  return [(450, 290)]
    if n == 2:  return [(270, 290), (630, 290)]
    if n == 3:  return [(200, 290), (450, 180), (700, 290)]
    if n == 4:  return [(220, 185), (630, 185), (220, 400), (630, 400)]
    if n == 5:  return [(160, 200), (450, 130), (740, 200), (280, 410), (620, 410)]
    cols = 3
    rows_n = math.ceil(n / cols)
    pts = []
    for r in range(rows_n):
        for c in range(cols):
            if len(pts) < n:
                pts.append((170 + c * 270, 160 + r * 230))
    return pts


def render_topic_clouds(rows):
    _render_legend()
    if not rows:
        st.info("No notes yet.")
        return

    clusters = _cluster_by_category(rows)
    if not clusters:
        st.info("No notes yet.")
        return

    positions = _cluster_positions(len(clusters))
    fig = go.Figure()

    for i, cl in enumerate(clusters):
        cx, cy = positions[i]
        notes = cl["notes"]
        color = cl["color"]
        label = cl["label"]
        n = len(notes)
        if n == 0:
            continue

        radius = min(130, max(68, 60 + n * 12))

        # Halo circle
        theta = [j * 2 * math.pi / 60 for j in range(61)]
        fig.add_trace(go.Scatter(
            x=[cx + radius * math.cos(t) for t in theta],
            y=[cy + radius * math.sin(t) for t in theta],
            mode="lines",
            line=dict(color=color, width=1.5),
            opacity=0.35,
            showlegend=False,
            hoverinfo="skip",
        ))

        # Category label
        fig.add_annotation(x=cx, y=cy + 8, text=f"<b>{label}</b>",
                           showarrow=False, font=dict(size=13, color=color), yanchor="bottom")
        fig.add_annotation(x=cx, y=cy - 8,
                           text=f"{n} note{'s' if n != 1 else ''}",
                           showarrow=False, font=dict(size=10, color="#64748b"), yanchor="top")

        # Note dots
        dot_x, dot_y, texts = [], [], []
        for j, note in enumerate(notes):
            angle = 2 * math.pi * j / n
            orbit = radius * 0.75 + (j % 3) * 11
            dot_x.append(cx + orbit * math.cos(angle))
            dot_y.append(cy + orbit * math.sin(angle))
            texts.append(note[:120] + ("…" if len(note) > 120 else ""))

        fig.add_trace(go.Scatter(
            x=dot_x, y=dot_y,
            mode="markers",
            marker=dict(size=10, color=color, opacity=0.85,
                        line=dict(width=1.5, color="white")),
            text=texts,
            hoverinfo="text",
            name=label,
            showlegend=False,
        ))

    fig.update_layout(
        height=480,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        xaxis=dict(visible=False, showgrid=False, zeroline=False),
        yaxis=dict(visible=False, showgrid=False, zeroline=False, scaleanchor="x"),
        showlegend=False,
        hoverlabel=dict(bgcolor="#1e293b", font_size=12,
                        font_color="white", bordercolor="#334155"),
    )
    st.plotly_chart(fig, use_container_width=True)
