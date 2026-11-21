import json
import math
import streamlit as st
import streamlit.components.v1 as components

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

const BASE_W = 900;
CLUSTERS.forEach(cl => {{
  cl.cx = Math.round(cl.cx * W / BASE_W);
  cl.cy = Math.round(cl.cy);
  cl._dots = [];
}});

function drawCloud(cl) {{
  const count  = cl.notes.length;
  const radius = Math.min(130, Math.max(68, 60 + count * 12));

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

  ctx.save();
  ctx.fillStyle = cl.color;
  ctx.font = "bold 14px Inter,Arial,sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(cl.label, cl.cx, cl.cy - 7);
  ctx.restore();

  ctx.save();
  ctx.fillStyle = "#64748b";
  ctx.font = "11px Inter,Arial,sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.fillText(count + " note" + (count !== 1 ? "s" : ""), cl.cx, cl.cy + 7);
  ctx.restore();

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
