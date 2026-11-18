import json
import math
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from collections import Counter
from database.sheets_client import get_all_rows

CATEGORY_COLORS = {
    "Work":      "#4A90D9",
    "Learning":  "#27AE60",
    "Personal":  "#F39C12",
    "Technical": "#8E44AD",
    "Career":    "#E74C3C",
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
        f'<span style="font-size:0.82rem;color:#cbd5e1;">{cat}</span></span>'
        for cat, color in CATEGORY_COLORS.items()
    )
    st.markdown(
        f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);'
        f'border-radius:8px;padding:10px 14px;display:flex;flex-wrap:wrap;align-items:center;'
        f'gap:4px;margin-bottom:12px;">'
        f'{items}'
        f'<span style="font-size:0.78rem;color:#475569;margin-left:4px;">'
        f'<span style="letter-spacing:2px;">– – –</span> similar notes</span></div>',
        unsafe_allow_html=True,
    )


# ── VIEW 1 — FORCE GALAXY ────────────────────────────────────────────

def _render_force_galaxy(rows):
    _render_legend()

    try:
        from pyvis.network import Network
        import networkx as nx
    except ImportError:
        st.error("Run: `pip install pyvis networkx` then restart.")
        return

    # Category filter buttons
    cats_present = sorted({r.get("category", "Personal") for r in rows})
    filter_key = "galaxy_cat_filter"
    if filter_key not in st.session_state:
        st.session_state[filter_key] = "All"

    btn_cols = st.columns(len(cats_present) + 1)
    for i, cat in enumerate(["All"] + cats_present):
        active = st.session_state[filter_key] == cat
        if btn_cols[i].button(cat, key=f"gf_{cat}",
                              type="primary" if active else "secondary",
                              use_container_width=True):
            st.session_state[filter_key] = cat
            st.rerun()

    selected_cat = st.session_state[filter_key]
    filtered = rows if selected_cat == "All" else [r for r in rows if r.get("category") == selected_cat]

    G = nx.Graph()

    # Category hub nodes
    cat_counts = Counter(r.get("category", "Personal") for r in filtered)
    for cat, cnt in cat_counts.items():
        color = CATEGORY_COLORS.get(cat, _DEFAULT_COLOR)
        G.add_node(f"CAT_{cat}", label=cat, title=f"{cnt} notes",
                   color={"background": color, "border": color},
                   size=35, shape="dot",
                   font={"size": 15, "color": "#ffffff", "bold": True})

    # Note nodes + category edges
    embeddings = {}
    for r in filtered:
        nid  = str(r.get("note_id", ""))
        text = r.get("content", "")
        cat  = r.get("category", "Personal")
        if not nid or not text:
            continue
        color = CATEGORY_COLORS.get(cat, _DEFAULT_COLOR)
        label = text[:25] + "…" if len(text) > 25 else text
        G.add_node(nid, label=label, title=text,
                   color={"background": color + "b3", "border": color},
                   size=12, shape="dot",
                   font={"size": 10, "color": "#e2e8f0"})
        G.add_edge(f"CAT_{cat}", nid,
                   color={"color": "#334155"}, width=1, dashes=False)
        emb = _parse_emb(r)
        if emb:
            embeddings[nid] = emb

    # Similarity edges
    nids = list(embeddings.keys())
    for i in range(len(nids)):
        for j in range(i + 1, len(nids)):
            sim = _cosine(embeddings[nids[i]], embeddings[nids[j]])
            if sim > 0.45:
                G.add_edge(nids[i], nids[j],
                           color={"color": "#7c6af7"}, width=0.5,
                           dashes=True, title=f"{sim:.0%} similar")

    net = Network(height="600px", width="100%",
                  bgcolor="#0f1117", font_color="#e2e8f0", notebook=False)
    net.set_options(json.dumps({
        "physics": {
            "enabled": True,
            "forceAtlas2Based": {
                "gravitationalConstant": -50,
                "springLength": 100,
                "springConstant": 0.04,
                "damping": 0.09,
            },
            "solver": "forceAtlas2Based",
            "stabilization": {"iterations": 150},
        },
        "interaction": {"hover": True, "tooltipDelay": 50,
                        "navigationButtons": True, "keyboard": True},
        "edges": {"smooth": {"type": "dynamic"}},
    }))
    net.from_nx(G)
    net.save_graph("brain_map_temp.html")
    html = open("brain_map_temp.html", "r", encoding="utf-8").read()
    html = html.replace("</head>",
        "<style>body,html{background:#0f1117!important;margin:0;padding:0;}"
        "#mynetwork{border-radius:12px;border:1px solid #1e293b;}"
        "div.vis-tooltip{background:#1e293b!important;color:#f1f5f9!important;"
        "border-radius:8px!important;padding:10px!important;max-width:300px!important;"
        "white-space:pre-wrap!important;font-size:12px!important;}</style></head>")
    components.html(html, height=620, scrolling=False)


# ── VIEW 2 — MEMORY RIVER ────────────────────────────────────────────

def _render_memory_river(rows):
    _render_legend()
    if not rows:
        st.info("No notes yet.")
        return

    notes_js = json.dumps(
        [{"content": r.get("content", ""), "category": r.get("category", "Personal")}
         for r in rows],
        ensure_ascii=True
    )
    colors_js = json.dumps(CATEGORY_COLORS, ensure_ascii=True)

    html = f"""<!DOCTYPE html><html><head>
<style>
  body{{margin:0;background:#0a0f1e;overflow:hidden;}}
  canvas{{display:block;}}
  #tip{{position:absolute;display:none;background:#1e293b;color:#e2e8f0;
        border:1px solid #334155;border-radius:8px;padding:8px 12px;
        font:12px/1.5 Inter,sans-serif;max-width:260px;pointer-events:none;
        z-index:10;word-break:break-word;}}
</style></head><body>
<canvas id="c"></canvas>
<div id="tip"></div>
<script>
const NOTES={notes_js};
const COLORS={colors_js};
const DEFAULT="#64748b";
const W=Math.min(window.innerWidth,900), H=500;
const canvas=document.getElementById("c");
canvas.width=W; canvas.height=H;
const ctx=canvas.getContext("2d");
const tip=document.getElementById("tip");
const RY=H/2, PAD=60;
let time=0;

const bubbles=NOTES.map((n,i)=>{{
  const r=Math.min(28,Math.max(10,n.content.length/18));
  return {{
    x: PAD+(i/(Math.max(NOTES.length-1,1)))*(W-PAD*2),
    baseY: i%2===0? RY-80-(i%4)*18 : RY+80+(i%4)*18,
    r, color:COLORS[n.category]||DEFAULT,
    content:n.content, category:n.category, i
  }};
}});

function draw(){{
  ctx.clearRect(0,0,W,H);

  // River
  const rg=ctx.createLinearGradient(0,0,W,0);
  rg.addColorStop(0,"#1e3a5f"); rg.addColorStop(1,"#0f2847");
  ctx.save();
  ctx.shadowColor="#3b82f6"; ctx.shadowBlur=12;
  ctx.fillStyle=rg;
  ctx.fillRect(0,RY-3,W,6);
  ctx.restore();

  bubbles.forEach(b=>{{
    const y=b.baseY+Math.sin(time/1.2+b.i*0.9)*0.4;
    b.curY=y;

    // Connector
    ctx.save();
    ctx.strokeStyle=b.color;
    ctx.globalAlpha=0.35;
    ctx.setLineDash([4,4]);
    ctx.lineWidth=1;
    ctx.beginPath();
    ctx.moveTo(b.x, y>RY? y-b.r : y+b.r);
    ctx.lineTo(b.x, RY);
    ctx.stroke();
    ctx.restore();

    // Bubble
    ctx.save();
    ctx.shadowColor=b.color; ctx.shadowBlur=10;
    ctx.globalAlpha=0.88;
    ctx.beginPath();
    ctx.arc(b.x, y, b.r, 0, Math.PI*2);
    ctx.fillStyle=b.color;
    ctx.fill();
    ctx.strokeStyle="rgba(255,255,255,0.7)";
    ctx.lineWidth=1.5;
    ctx.stroke();
    ctx.restore();
  }});

  time+=0.016;
  requestAnimationFrame(draw);
}}
draw();

canvas.addEventListener("mousemove",e=>{{
  const rect=canvas.getBoundingClientRect();
  const mx=e.clientX-rect.left, my=e.clientY-rect.top;
  let found=null;
  bubbles.forEach(b=>{{
    const dy=(b.curY||b.baseY)-my;
    if(Math.sqrt((b.x-mx)**2+dy**2)<b.r+4) found=b;
  }});
  if(found){{
    tip.style.display="block";
    tip.style.left=(e.clientX+10)+"px";
    tip.style.top=(e.clientY-40)+"px";
    tip.textContent=found.content.slice(0,120)+(found.content.length>120?"…":"");
  }} else {{
    tip.style.display="none";
  }}
}});
canvas.addEventListener("mouseleave",()=>tip.style.display="none");
</script></body></html>"""

    components.html(html, height=520, scrolling=False)


# ── VIEW 3 — TOPIC CLOUDS ────────────────────────────────────────────

def _cluster_by_similarity(rows):
    indexed = [(i, r) for i, r in enumerate(rows) if _parse_emb(r)]
    no_emb  = [(i, r) for i, r in enumerate(rows) if not _parse_emb(r)]
    clustered = set()
    clusters  = []

    for i, r in indexed:
        if i in clustered:
            continue
        emb_i = _parse_emb(r)
        cluster_rows = [r]
        clustered.add(i)
        for j, r2 in indexed:
            if j in clustered:
                continue
            emb_j = _parse_emb(r2)
            if _cosine(emb_i, emb_j) > 0.52:
                cluster_rows.append(r2)
                clustered.add(j)
        clusters.append(cluster_rows)

    for _, r in no_emb:
        clusters.append([r])

    result = []
    for cl in clusters:
        cats   = [r.get("category", "Personal") for r in cl]
        color  = CATEGORY_COLORS.get(Counter(cats).most_common(1)[0][0], _DEFAULT_COLOR)
        words  = []
        for r in cl:
            words += [w.lower().strip(".,;:!?\"'") for w in r.get("content","").split()]
        words = [w for w in words if w and w not in _STOPWORDS and len(w) > 2]
        label = Counter(words).most_common(1)[0][0].capitalize() if words else "Notes"
        result.append({
            "notes":  [r.get("content","") for r in cl],
            "color":  color,
            "label":  label,
        })
    return result


def _cluster_positions(n):
    if n == 1:  return [(450, 290)]
    if n == 2:  return [(250, 290), (650, 290)]
    if n <= 4:
        return [(250,180),(650,180),(250,400),(650,400)][:n]
    if n <= 6:
        xs = [200, 450, 700]
        return [(x, y) for y in [180,400] for x in xs][:n]
    cols = 3
    rows_n = math.ceil(n / cols)
    pts = []
    for r in range(rows_n):
        for c in range(cols):
            if len(pts) < n:
                pts.append((160 + c*260, 150 + r*220))
    return pts


def _render_topic_clouds(rows):
    _render_legend()
    if not rows:
        st.info("No notes yet.")
        return

    clusters = _cluster_by_similarity(rows)
    positions = _cluster_positions(len(clusters))

    cluster_data = [
        {"notes": c["notes"], "color": c["color"], "label": c["label"],
         "cx": positions[i][0], "cy": positions[i][1]}
        for i, c in enumerate(clusters)
    ]
    clusters_js = json.dumps(cluster_data, ensure_ascii=True)

    html = f"""<!DOCTYPE html><html><head>
<style>
  body{{margin:0;background:#0a0f1e;overflow:hidden;}}
  canvas{{display:block;}}
  #tip2{{position:absolute;display:none;background:#1e293b;color:#e2e8f0;
         border:1px solid #334155;border-radius:8px;padding:8px 12px;
         font:12px/1.5 Inter,sans-serif;max-width:260px;pointer-events:none;
         z-index:10;word-break:break-word;}}
</style></head><body>
<canvas id="c2"></canvas>
<div id="tip2"></div>
<script>
const CLUSTERS={clusters_js};
const W=Math.min(window.innerWidth,900), H=580;
const canvas=document.getElementById("c2");
canvas.width=W; canvas.height=H;
const ctx=canvas.getContext("2d");
const tip=document.getElementById("tip2");
let time=0;

function hexToRgba(hex,a){{
  const r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16);
  return `rgba(${{r}},${{g}},${{b}},${{a}})`;
}}

function draw(){{
  ctx.clearRect(0,0,W,H);

  CLUSTERS.forEach(cl=>{{
    const radius=Math.min(120,Math.max(70,55+cl.notes.length*18));

    // Glow blob
    ctx.save();
    ctx.shadowColor=cl.color; ctx.shadowBlur=28;
    ctx.beginPath();
    ctx.arc(cl.cx,cl.cy,radius,0,Math.PI*2);
    ctx.fillStyle=hexToRgba(cl.color,0.12);
    ctx.fill();
    ctx.strokeStyle=hexToRgba(cl.color,0.4);
    ctx.lineWidth=1.5;
    ctx.stroke();
    ctx.restore();

    // Label
    ctx.fillStyle=cl.color;
    ctx.font="bold 13px Inter,Arial,sans-serif";
    ctx.textAlign="center";
    ctx.fillText(cl.label,cl.cx,cl.cy+5);

    // Note count
    ctx.fillStyle="rgba(255,255,255,0.35)";
    ctx.font="10px Inter,Arial,sans-serif";
    ctx.fillText(cl.notes.length+" note"+(cl.notes.length!==1?"s":""),cl.cx,cl.cy+22);

    // Orbiting dots
    cl.notes.forEach((note,ni)=>{{
      const total=cl.notes.length;
      const angle=(2*Math.PI*ni/total)+time*(0.4+ni*0.05);
      const orb=radius*0.72+(ni%3)*10;
      const dx=cl.cx+orb*Math.cos(angle);
      const dy=cl.cy+orb*Math.sin(angle);

      ctx.save();
      ctx.shadowColor=cl.color; ctx.shadowBlur=6;
      ctx.beginPath();
      ctx.arc(dx,dy,6,0,Math.PI*2);
      ctx.fillStyle=cl.color;
      ctx.fill();
      ctx.strokeStyle="rgba(255,255,255,0.6)";
      ctx.lineWidth=1;
      ctx.stroke();
      ctx.restore();

      cl._dots=cl._dots||[];
      cl._dots[ni]={{x:dx,y:dy,content:note}};
    }});
  }});

  time+=0.003;
  requestAnimationFrame(draw);
}}
draw();

canvas.addEventListener("mousemove",e=>{{
  const rect=canvas.getBoundingClientRect();
  const mx=e.clientX-rect.left, my=e.clientY-rect.top;
  let found=null;
  CLUSTERS.forEach(cl=>{{
    (cl._dots||[]).forEach(d=>{{
      if(d&&Math.sqrt((d.x-mx)**2+(d.y-my)**2)<10) found=d;
    }});
  }});
  if(found){{
    tip2.style.display="block";
    tip2.style.left=(e.clientX+12)+"px";
    tip2.style.top=(e.clientY-45)+"px";
    tip2.textContent=found.content.slice(0,100)+(found.content.length>100?"…":"");
  }} else {{
    tip2.style.display="none";
  }}
}});
canvas.addEventListener("mouseleave",()=>tip2.style.display="none");
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
        horizontal=True, label_visibility="collapsed"
    )
    st.caption("Force Galaxy = connections · Memory River = timeline · Topic Clouds = AI groups")

    if view == "🪐 Force Galaxy":
        _render_force_galaxy(rows)
    elif view == "🌊 Memory River":
        _render_memory_river(rows)
    elif view == "☁️ Topic Clouds":
        _render_topic_clouds(rows)
