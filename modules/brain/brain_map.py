import json
import math
import datetime
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from collections import Counter
from database.sheets_client import get_all_rows


def _parse_note_date(row) -> datetime.date | None:
    """Parse the date field from a note row."""
    raw = row.get("date", "") or ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(str(raw).strip(), fmt).date()
        except Exception:
            continue
    return None

CATEGORY_COLORS = {
    "Work":      "#4F46E5",
    "Learning":  "#16A34A",
    "Personal":  "#D97706",
    "Technical": "#7C3AED",
    "Career":    "#DC2626",
}
_DEFAULT_COLOR = "#64748b"
_STOPWORDS = {
    "the","a","an","is","in","of","to","and","or","for","with","it","this",
    "that","are","was","be","as","at","by","from","on","not","we","you","have",
    "has","i","my","our","your","their","its","can","do","did","will","would",
    "should","could","may","might","which","who","when","where","what","how",
    "s","t","re","ve","ll","d","m",
}


# ── helpers ──────────────────────────────────────────────────────────

def _cosine(a, b) -> float:
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    n = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / n) if n > 0 else 0.0


def _parse_emb(row) -> list | None:
    raw = row.get("embedding", "")
    if not raw or str(raw).strip() in ("", "[]"):
        return None
    try:
        emb = json.loads(raw)
        return emb if isinstance(emb, list) and len(emb) > 0 else None
    except Exception:
        return None


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
        f'<span style="font-size:0.78rem;color:#94a3b8;margin-left:4px;">'
        f'<span style="letter-spacing:2px;">– – –</span> similar notes</span></div>',
        unsafe_allow_html=True,
    )


# ── VIEW 1 — FORCE GALAXY (Plotly) ───────────────────────────────────

def _spring_layout(nodes: list, edges: list, iterations: int = 80) -> dict:
    """Simple force-directed layout — no networkx needed."""
    import random
    pos = {n: [random.uniform(-1, 1), random.uniform(-1, 1)] for n in nodes}
    k = 1.5 / max(len(nodes) ** 0.5, 1)
    for _ in range(iterations):
        disp = {n: [0.0, 0.0] for n in nodes}
        # Repulsion
        for i, u in enumerate(nodes):
            for v in nodes[i+1:]:
                dx = pos[u][0] - pos[v][0]
                dy = pos[u][1] - pos[v][1]
                d  = max((dx**2 + dy**2) ** 0.5, 0.01)
                f  = k**2 / d
                disp[u][0] += dx / d * f
                disp[u][1] += dy / d * f
                disp[v][0] -= dx / d * f
                disp[v][1] -= dy / d * f
        # Attraction
        for u, v in edges:
            if u in pos and v in pos:
                dx = pos[u][0] - pos[v][0]
                dy = pos[u][1] - pos[v][1]
                d  = max((dx**2 + dy**2) ** 0.5, 0.01)
                f  = d**2 / k
                disp[u][0] -= dx / d * f * 0.1
                disp[u][1] -= dy / d * f * 0.1
                disp[v][0] += dx / d * f * 0.1
                disp[v][1] += dy / d * f * 0.1
        t = 0.1
        for n in nodes:
            mag = max((disp[n][0]**2 + disp[n][1]**2)**0.5, 0.01)
            pos[n][0] += disp[n][0] / mag * min(mag, t)
            pos[n][1] += disp[n][1] / mag * min(mag, t)
    return pos


def _render_force_galaxy(rows):
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.error("Run: `pip install plotly` then restart.")
        return

    # Category filter dropdown
    cats_present = sorted({r.get("category", "Personal") for r in rows})
    selected_cat = st.selectbox(
        "Filter by category",
        ["All"] + cats_present,
        key="galaxy_cat_filter_sel",
        label_visibility="visible",
    )
    filtered = rows if selected_cat == "All" else [
        r for r in rows if r.get("category") == selected_cat
    ]

    if not filtered:
        st.info("No notes in this category.")
        return

    # Build graph structure
    node_ids, node_labels, node_colors, node_sizes, node_texts = [], [], [], [], []
    edge_pairs = []
    embeddings = {}

    # Category hub nodes
    cat_counts = Counter(r.get("category", "Personal") for r in filtered)
    for cat, cnt in cat_counts.items():
        nid = f"CAT_{cat}"
        node_ids.append(nid)
        node_labels.append(cat)
        node_colors.append(CATEGORY_COLORS.get(cat, _DEFAULT_COLOR))
        node_sizes.append(40)
        node_texts.append(f"<b>{cat}</b><br>{cnt} notes")

    # Note nodes
    for r in filtered:
        nid  = str(r.get("note_id", ""))
        text = r.get("content", "")
        cat  = r.get("category", "Personal")
        if not nid or not text:
            continue
        node_ids.append(nid)
        node_labels.append(text[:22] + "…" if len(text) > 22 else text)
        node_colors.append(CATEGORY_COLORS.get(cat, _DEFAULT_COLOR))
        node_sizes.append(14)
        node_texts.append(f"<b>{cat}</b><br>{text[:180]}")
        edge_pairs.append((f"CAT_{cat}", nid, 0.3))  # (u, v, weight)
        emb = _parse_emb(r)
        if emb:
            embeddings[nid] = emb

    # Similarity edges between notes
    nids = list(embeddings.keys())
    for i in range(len(nids)):
        for j in range(i + 1, len(nids)):
            sim = _cosine(embeddings[nids[i]], embeddings[nids[j]])
            if sim > 0.45:
                edge_pairs.append((nids[i], nids[j], sim))

    # Layout
    all_nodes = node_ids
    pos = _spring_layout(all_nodes, [(u, v) for u, v, _ in edge_pairs])

    # Node size = number of connections
    conn_count = Counter()
    for u, v, _ in edge_pairs:
        conn_count[u] += 1
        conn_count[v] += 1
    node_sizes = [
        40 if nid.startswith("CAT_") else max(12, min(30, 10 + conn_count.get(nid, 0) * 4))
        for nid in node_ids
    ]

    # Build Plotly traces
    # Edge traces (grouped by similarity strength → line width)
    edge_traces = []
    for u, v, w in edge_pairs:
        if u not in pos or v not in pos:
            continue
        is_sim = not (u.startswith("CAT_") or v.startswith("CAT_"))
        edge_traces.append(go.Scatter(
            x=[pos[u][0], pos[v][0], None],
            y=[pos[u][1], pos[v][1], None],
            mode="lines",
            line=dict(
                width=max(0.5, w * 3) if is_sim else 1,
                color="#6366f1" if is_sim else "#CBD5E1",
            ),
            hoverinfo="none",
            showlegend=False,
        ))

    # Node trace
    xs = [pos[nid][0] for nid in node_ids if nid in pos]
    ys = [pos[nid][1] for nid in node_ids if nid in pos]
    valid = [i for i, nid in enumerate(node_ids) if nid in pos]

    node_trace = go.Scatter(
        x=xs, y=ys,
        mode="markers+text",
        text=[node_labels[i] for i in valid],
        textposition="top center",
        hovertext=[node_texts[i] for i in valid],
        hoverinfo="text",
        marker=dict(
            color=[node_colors[i] for i in valid],
            size=[node_sizes[i] for i in valid],
            line=dict(color="#FFFFFF", width=2),
            opacity=0.9,
        ),
        textfont=dict(size=9, color="#374151"),
        showlegend=False,
    )

    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=10, r=10, t=10, b=10),
        height=580,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        hovermode="closest",
    )

    # Click node → show full note in a panel below the chart
    selected = st.plotly_chart(fig, use_container_width=True,
                               key="force_galaxy_chart")

    _render_legend()


# ── VIEW 2 — MEMORY RIVER ────────────────────────────────────────────

def _render_memory_river(rows):
    _render_legend()
    if not rows:
        st.info("No notes yet.")
        return

    # Parse and sort by real date
    dated = []
    for r in rows:
        d = _parse_note_date(r)
        dated.append({
            "content":  r.get("content", ""),
            "category": r.get("category", "Personal"),
            "date":     d.isoformat() if d else "",
            "dateMs":   int(datetime.datetime(d.year, d.month, d.day).timestamp() * 1000) if d else 0,
        })
    dated.sort(key=lambda x: x["dateMs"])

    # Build unique sorted date labels for x-axis
    unique_dates = sorted({n["date"] for n in dated if n["date"]})
    # Format: "Nov 15" style
    def _fmt(iso):
        try:
            dt = datetime.date.fromisoformat(iso)
            return dt.strftime("%b %-d") if hasattr(dt, "strftime") else dt.strftime("%b %d").replace(" 0", " ")
        except Exception:
            return iso

    # On Windows strftime doesn't support %-d, use lstrip("0")
    def _fmt_date(iso):
        try:
            dt = datetime.date.fromisoformat(iso)
            return dt.strftime("%b %d").replace(" 0", " ")
        except Exception:
            return iso

    axis_labels = [{"iso": d, "label": _fmt_date(d)} for d in unique_dates]

    notes_js   = json.dumps(dated, ensure_ascii=True)
    colors_js  = json.dumps(CATEGORY_COLORS, ensure_ascii=True)
    axis_js    = json.dumps(axis_labels, ensure_ascii=True)

    html = f"""<!DOCTYPE html><html><head>
<style>
  body{{margin:0;background:#ffffff;overflow:hidden;font-family:Inter,Arial,sans-serif;}}
  canvas{{display:block;}}
  #tip{{position:absolute;display:none;background:#1e293b;color:#f8fafc;
        border:1px solid #334155;border-radius:8px;padding:8px 12px;
        font:12px/1.5 Inter,sans-serif;max-width:280px;pointer-events:none;
        z-index:10;word-break:break-word;box-shadow:0 4px 12px rgba(0,0,0,0.18);}}
</style></head><body>
<canvas id="c"></canvas>
<div id="tip"></div>
<script>
const NOTES  = {notes_js};
const COLORS = {colors_js};
const AXIS   = {axis_js};
const DEFAULT= "#64748b";
const W = Math.min(window.innerWidth, 940), H = 520;
const canvas = document.getElementById("c");
canvas.width = W; canvas.height = H;
const ctx = canvas.getContext("2d");
const tip = document.getElementById("tip");
const PAD = 72, RY = Math.round(H * 0.56);
let time = 0;

// Map each note's date to an x position
const msArr = NOTES.map(n => n.dateMs);
const minMs = Math.min(...msArr.filter(x=>x>0)) || Date.now();
const maxMs = Math.max(...msArr.filter(x=>x>0)) || (minMs + 86400000);
const span  = Math.max(maxMs - minMs, 86400000);

function dateToX(ms) {{
  if (!ms) return PAD;
  return PAD + ((ms - minMs) / span) * (W - PAD * 2);
}}

// Jitter same-date notes so they don't stack
const xCounts = {{}};
const bubbles = NOTES.map((n, i) => {{
  const x0 = dateToX(n.dateMs);
  xCounts[x0] = (xCounts[x0] || 0) + 1;
  const slot = xCounts[x0] - 1;
  const jitter = (slot % 2 === 0 ? 1 : -1) * Math.floor(slot / 2) * 22;
  const r = Math.min(26, Math.max(10, n.content.length / 20));
  const above = i % 2 === 0;
  return {{
    x: x0 + jitter,
    baseY: above ? RY - 85 - (i % 3) * 20 : RY + 85 + (i % 3) * 20,
    r, color: COLORS[n.category] || DEFAULT,
    content: n.content, category: n.category, i,
    above, curY: 0,
  }};
}});

function draw() {{
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, W, H);

  // Axis tick lines
  AXIS.forEach(a => {{
    const x = dateToX(new Date(a.iso).getTime());
    ctx.save();
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, 40); ctx.lineTo(x, H - 36);
    ctx.stroke();
    ctx.restore();
  }});

  // River line
  const rg = ctx.createLinearGradient(0, 0, W, 0);
  rg.addColorStop(0, "#93c5fd"); rg.addColorStop(1, "#3b82f6");
  ctx.save();
  ctx.fillStyle = rg;
  ctx.fillRect(PAD - 10, RY - 3, W - PAD * 2 + 20, 6);
  ctx.restore();

  // Date labels on axis
  ctx.fillStyle = "#94a3b8";
  ctx.font = "11px Inter,Arial,sans-serif";
  ctx.textAlign = "center";
  AXIS.forEach(a => {{
    const x = dateToX(new Date(a.iso).getTime());
    ctx.fillText(a.label, x, RY + 20);
  }});

  // "Earlier" / "Recent" axis ends
  ctx.textAlign = "left";
  ctx.fillStyle = "#cbd5e1";
  ctx.font = "10px Inter,Arial,sans-serif";
  ctx.fillText("← Earlier", 4, RY + 20);
  ctx.textAlign = "right";
  ctx.fillText("Recent →", W - 4, RY + 20);

  bubbles.forEach(b => {{
    const y = b.baseY + Math.sin(time / 1.4 + b.i * 1.1) * 1.5;
    b.curY = y;

    // Connector
    ctx.save();
    ctx.strokeStyle = b.color;
    ctx.globalAlpha = 0.35;
    ctx.setLineDash([3, 4]);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(b.x, y > RY ? y - b.r : y + b.r);
    ctx.lineTo(b.x, RY);
    ctx.stroke();
    ctx.restore();

    // Bubble
    ctx.save();
    ctx.shadowColor = b.color + "55"; ctx.shadowBlur = 6;
    ctx.beginPath();
    ctx.arc(b.x, y, b.r, 0, Math.PI * 2);
    ctx.fillStyle = b.color;
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.85)";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.restore();

    // Short keyword label above/below bubble
    if (b.r > 13) {{
      const word = b.content.trim().split(/\s+/)[0].slice(0, 9);
      ctx.save();
      ctx.fillStyle = b.above ? b.color : b.color;
      ctx.font = "bold 9px Inter,Arial,sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = b.above ? "bottom" : "top";
      ctx.fillText(word, b.x, b.above ? y - b.r - 3 : y + b.r + 3);
      ctx.restore();
    }}
  }});

  time += 0.016;
  requestAnimationFrame(draw);
}}
draw();

canvas.addEventListener("mousemove", e => {{
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  let found = null;
  bubbles.forEach(b => {{
    const dy = (b.curY || b.baseY) - my;
    if (Math.sqrt((b.x - mx) ** 2 + dy ** 2) < b.r + 5) found = b;
  }});
  if (found) {{
    tip.style.display = "block";
    tip.style.left = (e.clientX + 12) + "px";
    tip.style.top  = (e.clientY - 50) + "px";
    tip.innerHTML  = `<strong style="color:#93c5fd">${{found.category}}</strong><br>${{found.content.slice(0,140)}}${{found.content.length>140?"…":""}}`;
  }} else {{
    tip.style.display = "none";
  }}
}});
canvas.addEventListener("mouseleave", () => tip.style.display = "none");
</script></body></html>"""

    components.html(html, height=540, scrolling=False)


# ── VIEW 3 — TOPIC CLOUDS ────────────────────────────────────────────

def _cluster_by_category(rows):
    """Group notes by their category field — gives one cloud per category."""
    groups: dict[str, list] = {}
    for r in rows:
        cat = r.get("category", "Personal") or "Personal"
        groups.setdefault(cat, []).append(r.get("content", ""))

    result = []
    for cat, notes in groups.items():
        color = CATEGORY_COLORS.get(cat, _DEFAULT_COLOR)
        result.append({"notes": notes, "color": color, "label": cat})

    # Sort by note count descending so largest clouds get central positions
    result.sort(key=lambda x: len(x["notes"]), reverse=True)
    return result


def _cluster_positions(n):
    # Spread positions evenly across the canvas
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


def _render_topic_clouds(rows):
    _render_legend()
    if not rows:
        st.info("No notes yet.")
        return

    clusters = _cluster_by_category(rows)
    positions = _cluster_positions(len(clusters))

    cluster_data = [
        {"notes": c["notes"], "color": c["color"], "label": c["label"],
         "cx": positions[i][0], "cy": positions[i][1]}
        for i, c in enumerate(clusters)
    ]
    clusters_js = json.dumps(cluster_data, ensure_ascii=True)

    html = f"""<!DOCTYPE html><html><head>
<style>
  body{{margin:0;background:#ffffff;overflow:hidden;font-family:Inter,Arial,sans-serif;}}
  canvas{{display:block;}}
  #tip2{{position:absolute;display:none;background:#1e293b;color:#f8fafc;
         border:1px solid #334155;border-radius:8px;padding:8px 12px;
         font:12px/1.5 Inter,sans-serif;max-width:280px;pointer-events:none;
         z-index:10;word-break:break-word;box-shadow:0 4px 14px rgba(0,0,0,0.2);}}
</style></head><body>
<canvas id="c2"></canvas>
<div id="tip2"></div>
<script>
const CLUSTERS = {clusters_js};
const W = Math.min(window.innerWidth, 940), H = 580;
const canvas = document.getElementById("c2");
canvas.width = W; canvas.height = H;
const ctx = canvas.getContext("2d");
const tip = document.getElementById("tip2");
let time = 0;

function hexToRgba(hex, a) {{
  const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  return `rgba(${{r}},${{g}},${{b}},${{a}})`;
}}

// Scale cluster positions to actual canvas width
const BASE_W = 900;
CLUSTERS.forEach(cl => {{
  cl.cx = Math.round(cl.cx * W / BASE_W);
  cl.cy = Math.round(cl.cy);
  cl._dots = [];
}});

function drawCloud(cl) {{
  const count  = cl.notes.length;
  const radius = Math.min(130, Math.max(68, 60 + count * 12));

  // Gradient blob fill
  const grad = ctx.createRadialGradient(cl.cx, cl.cy, 0, cl.cx, cl.cy, radius);
  grad.addColorStop(0,   hexToRgba(cl.color, 0.14));
  grad.addColorStop(0.7, hexToRgba(cl.color, 0.08));
  grad.addColorStop(1,   hexToRgba(cl.color, 0.02));

  ctx.save();
  ctx.beginPath();
  ctx.arc(cl.cx, cl.cy, radius, 0, Math.PI * 2);
  ctx.fillStyle = grad;
  ctx.fill();
  ctx.strokeStyle = hexToRgba(cl.color, 0.45);
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.restore();

  // Category label
  ctx.save();
  ctx.fillStyle = cl.color;
  ctx.font = "bold 14px Inter,Arial,sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(cl.label, cl.cx, cl.cy - 7);
  ctx.restore();

  // Note count
  ctx.save();
  ctx.fillStyle = "#64748b";
  ctx.font = "11px Inter,Arial,sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.fillText(count + " note" + (count !== 1 ? "s" : ""), cl.cx, cl.cy + 7);
  ctx.restore();

  // Orbiting note dots
  cl._dots = [];
  cl.notes.forEach((note, ni) => {{
    const total  = cl.notes.length;
    const speed  = 0.25 + (ni % 3) * 0.08;
    const angle  = (2 * Math.PI * ni / total) + time * speed;
    const orbit  = radius * 0.75 + (ni % 3) * 11;
    const dx = cl.cx + orbit * Math.cos(angle);
    const dy = cl.cy + orbit * Math.sin(angle);
    const dr = 7;

    ctx.save();
    ctx.beginPath();
    ctx.arc(dx, dy, dr, 0, Math.PI * 2);
    ctx.fillStyle = cl.color;
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.9)";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.restore();

    cl._dots.push({{x: dx, y: dy, r: dr, content: note}});
  }});
}}

function draw() {{
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, W, H);

  CLUSTERS.forEach(drawCloud);

  time += 0.003;
  requestAnimationFrame(draw);
}}
draw();

canvas.addEventListener("mousemove", e => {{
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  let found = null;
  CLUSTERS.forEach(cl => {{
    cl._dots.forEach(d => {{
      if (Math.sqrt((d.x - mx) ** 2 + (d.y - my) ** 2) < d.r + 4) found = d;
    }});
  }});
  if (found) {{
    tip.style.display = "block";
    tip.style.left = (e.clientX + 14) + "px";
    tip.style.top  = (e.clientY - 50) + "px";
    tip.textContent = found.content.slice(0, 120) + (found.content.length > 120 ? "…" : "");
  }} else {{
    tip.style.display = "none";
  }}
}});
canvas.addEventListener("mouseleave", () => tip.style.display = "none");
</script></body></html>"""

    components.html(html, height=600, scrolling=False)


# ── MAIN ─────────────────────────────────────────────────────────────

def render_map():
    rows = get_all_rows("brain_notes")
    if not rows:
        st.info("Add some notes first to see your Brain Map.")
        return

    view = st.radio(
        "", ["🪐 Force Galaxy", "🌊 Memory River", "☁️ Topic Clouds"],
        horizontal=True, label_visibility="collapsed",
        key="brain_map_view",
    )
    st.caption("Force Galaxy = connections (interactive Plotly) · Memory River = timeline · Topic Clouds = categories")

    if view == "🪐 Force Galaxy":
        _render_force_galaxy(rows)
    elif view == "🌊 Memory River":
        _render_memory_river(rows)
    elif view == "☁️ Topic Clouds":
        _render_topic_clouds(rows)
