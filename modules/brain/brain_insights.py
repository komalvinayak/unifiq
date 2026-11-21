# ── brain_insights.py ────────────────────────────────────────────────
# Mufakkir — Pattern Intelligence tab.
# Shows thinking patterns: active days/times, top keywords,
# category distribution, weekly AI summary.
# All times in IST.
# ─────────────────────────────────────────────────────────────────────

import datetime
import re
from collections import Counter
import streamlit as st
import plotly.graph_objects as go
from ai.gemini_client import generate
from utils.date_utils import now_ist
from config.settings import BRAIN_CATEGORIES

CAT_EMOJI = {
    "Work": "💼", "Learning": "📚", "Personal": "🌱",
    "Technical": "💻", "Career": "🎯",
}
_CAT_COLOR = {
    "Work": "#4F46E5", "Learning": "#16A34A", "Personal": "#D97706",
    "Technical": "#7C3AED", "Career": "#DC2626",
}
_STOPWORDS = {
    "the","a","an","is","in","of","to","and","or","for","with","it","this","that",
    "are","was","be","as","at","by","from","on","not","we","you","have","has","i",
    "my","our","your","their","its","can","do","did","will","would","should","could",
    "may","might","which","who","when","where","what","how","s","t","re","ve","ll",
    "d","m","also","about","more","just","like","there","than","then","so","very",
    "some","all","been","had","they","but","if","up","out","one","get","time",
}


def _parse_date(raw: str):
    for fmt in ("%d %b %Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(str(raw).strip(), fmt)
        except Exception:
            continue
    return None


def _parse_time_hour(raw: str) -> int | None:
    for fmt in ("%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.datetime.strptime(str(raw).strip(), fmt).hour
        except Exception:
            continue
    return None


def _get_week_notes(notes: list) -> list:
    now = now_ist()
    week_ago = (now - datetime.timedelta(days=7)).date()
    result = []
    for n in notes:
        d = _parse_date(n.get("date", "") or n.get("created_time", ""))
        if d and d.date() >= week_ago:
            result.append(n)
    return result


def _show_heatmap(all_notes: list):
    st.markdown("**🗓️ Thought Frequency Heatmap**")
    st.caption("Your note-taking activity over the last 12 months.")

    now = now_ist()
    today = now.date()
    cutoff = (now - datetime.timedelta(days=365)).date()

    date_counts: Counter = Counter()
    date_cats: dict = {}

    for n in all_notes:
        d = _parse_date(n.get("date", "") or n.get("created_time", ""))
        if d and d.date() >= cutoff:
            ds = d.date().isoformat()
            date_counts[ds] += 1
            cat = n.get("category", "Personal")
            if ds not in date_cats:
                date_cats[ds] = Counter()
            date_cats[ds][cat] += 1

    unique_days = len(date_counts)
    if unique_days < 7:
        st.info("Keep adding thoughts — your activity map is building.")
        return

    # Align grid start to Monday of the cutoff week
    start = cutoff - datetime.timedelta(days=cutoff.weekday())
    end_week = today + datetime.timedelta(days=(6 - today.weekday()))
    total_days = (end_week - start).days + 1
    total_weeks = (total_days + 6) // 7

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    z_raw = [[0] * total_weeks for _ in range(7)]
    text_grid = [[""] * total_weeks for _ in range(7)]

    for i in range(total_days):
        d = start + datetime.timedelta(days=i)
        wk = i // 7
        dy = d.weekday()
        if wk >= total_weeks:
            break
        ds = d.isoformat()
        count = date_counts.get(ds, 0)
        z_raw[dy][wk] = count
        top_cat = ""
        if ds in date_cats:
            top_cat = date_cats[ds].most_common(1)[0][0]
        hover = f"{d.strftime('%d %b %Y')}<br>{count} note{'s' if count != 1 else ''}"
        if top_cat:
            hover += f"<br>Top: {top_cat}"
        text_grid[dy][wk] = hover

    def _bucket(v):
        if v == 0: return 0
        if v <= 2: return 1
        if v <= 5: return 2
        return 3

    z_mapped = [[_bucket(v) for v in row] for row in z_raw]
    colorscale = [[0.0, "#EBEDF0"], [0.33, "#C7D2FE"], [0.66, "#818CF8"], [1.0, "#4F46E5"]]

    prev_month = None
    x_labels = []
    for w in range(total_weeks):
        ws = start + datetime.timedelta(weeks=w)
        if ws.month != prev_month:
            x_labels.append(ws.strftime("%b"))
            prev_month = ws.month
        else:
            x_labels.append("")

    fig = go.Figure(go.Heatmap(
        z=z_mapped, x=x_labels, y=day_names,
        text=text_grid, hovertemplate="%{text}<extra></extra>",
        colorscale=colorscale, showscale=False,
        xgap=2, ygap=2, zmin=0, zmax=3,
    ))
    fig.update_layout(
        height=180, margin=dict(l=40, r=10, t=10, b=30),
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        yaxis=dict(autorange="reversed", tickfont=dict(size=11), gridcolor="rgba(0,0,0,0)"),
        xaxis=dict(tickfont=dict(size=10), tickangle=0, gridcolor="rgba(0,0,0,0)", side="top"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Stats ────────────────────────────────────────────────────────
    all_dates_sorted = sorted(date_counts.keys())

    # Current streak (from today or yesterday)
    current_streak = 0
    check = today if today.isoformat() in date_counts else today - datetime.timedelta(days=1)
    if check.isoformat() in date_counts:
        while check.isoformat() in date_counts:
            current_streak += 1
            check -= datetime.timedelta(days=1)

    # Longest streak
    longest_streak = 0
    longest_start = longest_end = None
    if all_dates_sorted:
        cur = 1
        cur_start_d = datetime.date.fromisoformat(all_dates_sorted[0])
        for i in range(1, len(all_dates_sorted)):
            prev_d = datetime.date.fromisoformat(all_dates_sorted[i - 1])
            curr_d = datetime.date.fromisoformat(all_dates_sorted[i])
            if (curr_d - prev_d).days == 1:
                cur += 1
            else:
                if cur > longest_streak:
                    longest_streak = cur
                    longest_start = cur_start_d
                    longest_end = prev_d
                cur = 1
                cur_start_d = curr_d
        if cur > longest_streak:
            longest_streak = cur
            longest_start = cur_start_d
            longest_end = datetime.date.fromisoformat(all_dates_sorted[-1])

    # Day-of-week note totals
    dow_totals: Counter = Counter()
    for ds, cnt in date_counts.items():
        d = datetime.date.fromisoformat(ds)
        dow_totals[d.strftime("%A")] += cnt

    total_note_count = len(all_notes)
    days_with_notes = len(date_counts)
    daily_avg = total_note_count / max(1, days_with_notes)

    stat_cols = st.columns(4)
    stat_cols[0].metric("Total Notes", total_note_count)

    if unique_days >= 7:
        if current_streak >= 7:
            s_start = today - datetime.timedelta(days=current_streak - 1)
            stat_cols[1].metric("Current Streak", f"{current_streak} days",
                                f"{s_start.strftime('%d %b')} – {today.strftime('%d %b')}")
        else:
            stat_cols[1].metric("Current Streak",
                                f"{current_streak} day{'s' if current_streak != 1 else ''}")

        if longest_streak >= 7 and longest_start and longest_end:
            stat_cols[2].metric("Longest Streak", f"{longest_streak} days",
                                f"{longest_start.strftime('%d %b')} – {longest_end.strftime('%d %b')}")

        if dow_totals:
            top_day, top_day_total = dow_totals.most_common(1)[0]
            day_occ = sum(1 for ds in date_counts
                          if datetime.date.fromisoformat(ds).strftime("%A") == top_day)
            day_avg_n = top_day_total / max(1, day_occ)
            if daily_avg > 0 and day_avg_n >= 2 * daily_avg:
                stat_cols[3].metric("Most Active Day", top_day,
                                    f"avg {day_avg_n:.1f} vs {daily_avg:.1f} overall")

    with st.expander("How is this calculated?"):
        st.markdown("""
**Heatmap**: Each cell = one day. Color = notes saved that day (white → light blue → indigo = more notes).
**Current streak**: Consecutive days ending today (or yesterday if you haven't saved yet today).
**Longest streak**: The longest run of consecutive days with at least one note.
**Most active day**: Only shown when that day averages 2× the overall daily average.
""")


_MOOD_EMOJI_MAP = {
    "Curious": "🔍", "Anxious": "😟", "Excited": "🔥",
    "Confused": "😕", "Motivated": "💪", "Neutral": "⚪",
}
_MOOD_COLORS = {
    "Curious": "#6366F1", "Anxious": "#F59E0B", "Excited": "#EF4444",
    "Confused": "#8B5CF6", "Motivated": "#10B981",
}


def _show_mood_trends(all_notes: list):
    st.markdown("**🎭 Mood Trends**")
    st.caption("How you feel when you write — detected from your words at save time.")

    if len(all_notes) < 10:
        st.info("Add at least 10 notes to see your mood patterns.")
        return

    mood_counts: Counter = Counter()
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    mood_by_day: dict = {d: Counter() for d in days_order}

    for n in all_notes:
        mood = n.get("mood", "") or "Neutral"
        if mood not in _MOOD_EMOJI_MAP:
            mood = "Neutral"
        mood_counts[mood] += 1
        dow = n.get("day_of_week", "")
        if not dow:
            d = _parse_date(n.get("date", "") or n.get("created_time", ""))
            if d:
                dow = d.strftime("%A")
        if dow in mood_by_day:
            mood_by_day[dow][mood] += 1

    non_neutral = {m: c for m, c in mood_counts.items() if m != "Neutral" and c > 0}
    if not non_neutral:
        st.info("Not enough emotional content in your notes yet.")
        return

    moods = list(non_neutral.keys())
    counts = [non_neutral[m] for m in moods]
    colors = [_MOOD_COLORS.get(m, "#6B7280") for m in moods]

    col1, col2 = st.columns(2)
    with col1:
        fig1 = go.Figure(go.Bar(
            x=[f"{_MOOD_EMOJI_MAP.get(m, '')} {m}" for m in moods],
            y=counts,
            marker_color=colors,
            text=counts, textposition="outside",
        ))
        fig1.update_layout(
            title="Mood Frequency", height=280,
            margin=dict(l=20, r=20, t=40, b=20),
            paper_bgcolor="white", plot_bgcolor="white", showlegend=False,
            yaxis=dict(gridcolor="#F3F4F6"),
            xaxis=dict(tickfont=dict(size=11)),
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        traces = []
        for mood, color in _MOOD_COLORS.items():
            vals = [mood_by_day[d].get(mood, 0) for d in days_order]
            if any(v > 0 for v in vals):
                traces.append(go.Bar(
                    name=f"{_MOOD_EMOJI_MAP.get(mood, '')} {mood}",
                    x=day_labels, y=vals, marker_color=color,
                ))
        if traces:
            fig2 = go.Figure(data=traces)
            fig2.update_layout(
                title="Mood by Day", barmode="stack", height=280,
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="white", plot_bgcolor="white",
                yaxis=dict(gridcolor="#F3F4F6"),
                legend=dict(font=dict(size=10)),
            )
            st.plotly_chart(fig2, use_container_width=True)

    # Gemini insight only when one mood is 3× more common than the second
    top_moods = sorted(non_neutral.items(), key=lambda x: x[1], reverse=True)
    if len(top_moods) >= 2 and top_moods[0][1] >= 3 * top_moods[1][1]:
        if "mood_insight" not in st.session_state:
            with st.spinner("Generating mood insight…"):
                mb_day_str = {d: dict(mood_by_day[d]) for d in days_order if mood_by_day[d]}
                prompt = f"""Based on this mood frequency data, give ONE specific insight.
Only state something if the pattern is clear and significant.
If no clear pattern exists, return exactly: "No strong pattern detected yet."
Do not mention note content. Maximum 2 sentences.

Mood counts: {dict(non_neutral)}
Mood by day: {mb_day_str}
Total notes analyzed: {len(all_notes)}
"""
                st.session_state["mood_insight"] = generate(prompt)
        insight = st.session_state.get("mood_insight", "")
        if insight:
            st.markdown(
                f'<div style="background:#F0F0FF;border:1px solid #C7D2FE;border-radius:10px;'
                f'padding:14px 16px;font-size:0.9rem;color:#1E1E2E;margin:10px 0;">'
                f'🤖 {insight}</div>',
                unsafe_allow_html=True
            )

    st.caption(
        f"Based on {len(all_notes)} notes · "
        f"Last updated {now_ist().strftime('%d %b %Y, %I:%M %p')} IST"
    )
    with st.expander("How is this calculated?"):
        st.markdown("""
**Mood detection**: When you save a note, Mufakkir asks Gemini to detect the emotional tone from your words alone.
**Neutral notes**: Factual notes or notes under 5 words are marked Neutral and excluded from these charts.
**Day breakdown**: Shows which moods appear on which days of the week.
**AI insight**: Only generated when one mood is 3× more common than the second — otherwise the pattern isn't strong enough.
""")


_BLIND_SPOT_AREAS = ["Health", "Relationships", "Finance", "Creativity",
                     "Rest", "Career", "Learning", "Personal Growth"]


def _extract_blind_spot_json(raw: str, _json) -> dict:
    """Try multiple strategies to pull the 8-key dict out of an LLM response."""
    import re as _re

    # Strip markdown code fences if present
    cleaned = _re.sub(r"```[a-z]*", "", raw).strip()

    # Strategy 1: find first { ... last }
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            obj = _json.loads(cleaned[start:end + 1])
            if isinstance(obj, dict) and any(k in obj for k in _BLIND_SPOT_AREAS):
                return {k: int(obj.get(k, 0)) for k in _BLIND_SPOT_AREAS}
        except Exception:
            pass

    # Strategy 2: scan for "Key": number pairs
    pairs = _re.findall(r'"([^"]+)"\s*:\s*(\d+)', raw)
    if pairs:
        obj = {k: int(v) for k, v in pairs}
        if any(k in obj for k in _BLIND_SPOT_AREAS):
            return {k: int(obj.get(k, 0)) for k in _BLIND_SPOT_AREAS}

    return {}


def _show_blind_spot(all_notes: list):
    import json as _json

    st.markdown("**🔭 Blind Spot Detector**")
    st.caption("Which parts of life dominate your thinking — and which are absent?")

    if len(all_notes) < 20:
        st.info("Add at least 20 notes for an accurate blind spot analysis.")
        return

    unique_cats = {n.get("category", "") for n in all_notes if n.get("category")}
    if len(unique_cats) <= 1:
        st.info("Your notes need more variety for blind spot detection.")
        return

    if st.button("🔄 Refresh Analysis", key="blind_spot_refresh"):
        st.session_state.pop("blind_spot_data", None)
        st.session_state.pop("blind_spot_insight", None)

    # Date range label
    all_date_objs = []
    for n in all_notes:
        d = _parse_date(n.get("date", "") or n.get("created_time", ""))
        if d:
            all_date_objs.append(d.date())
    date_range = "—"
    if all_date_objs:
        date_range = (
            f"{min(all_date_objs).strftime('%d %b %Y')} – "
            f"{max(all_date_objs).strftime('%d %b %Y')}"
        )

    if "blind_spot_data" not in st.session_state:
        note_texts = "\n".join(
            f"- {n.get('content', '')[:150]}"
            for n in all_notes[:60]
        )
        prompt = (
            "Count how many of the notes below clearly mention each life area.\n"
            "Only count a note if it explicitly mentions that area. Do not infer.\n"
            "Return ONLY a JSON object — no markdown, no explanation, no extra text.\n\n"
            "Required output format (fill in the numbers):\n"
            '{"Health": 0, "Relationships": 0, "Finance": 0, "Creativity": 0, '
            '"Rest": 0, "Career": 0, "Learning": 0, "Personal Growth": 0}\n\n'
            f"Notes:\n{note_texts}"
        )
        with st.spinner("Analysing your life areas…"):
            raw = generate(prompt)

        topic_counts = _extract_blind_spot_json(raw, _json)

        if topic_counts:
            st.session_state["blind_spot_data"] = topic_counts
        else:
            st.warning("Could not parse life area analysis — the AI returned an unexpected format.")
            with st.expander("Show raw AI response (for debugging)"):
                st.code(raw)
            return

    topic_counts = st.session_state.get("blind_spot_data", {})
    if not topic_counts:
        return

    frequent = {a: c for a, c in topic_counts.items() if c > 3}
    rare = {a: c for a, c in topic_counts.items() if c == 0}

    col_f, col_r = st.columns(2)
    with col_f:
        st.markdown("**You think a lot about:**")
        if frequent:
            for area, cnt in sorted(frequent.items(), key=lambda x: x[1], reverse=True):
                st.markdown(
                    f'<div style="margin:5px 0;padding:8px 12px;background:#DCFCE7;border-radius:8px;'
                    f'display:flex;justify-content:space-between;align-items:center;">'
                    f'<span style="font-weight:600;color:#15803D;">{area}</span>'
                    f'<span style="color:#16A34A;font-size:0.85rem;">{cnt} notes</span></div>',
                    unsafe_allow_html=True
                )
        else:
            st.caption("No area mentioned in 4+ notes yet.")

    with col_r:
        st.markdown("**Rarely on your mind:**")
        if rare:
            for area in sorted(rare.keys()):
                st.markdown(
                    f'<div style="margin:5px 0;padding:8px 12px;background:#FEF3C7;border-radius:8px;'
                    f'display:flex;justify-content:space-between;align-items:center;">'
                    f'<span style="font-weight:600;color:#B45309;">{area}</span>'
                    f'<span style="color:#D97706;font-size:0.85rem;">0 notes</span></div>',
                    unsafe_allow_html=True
                )
        else:
            st.caption("All life areas appear in your notes.")

    if "blind_spot_insight" not in st.session_state:
        with st.spinner("Generating observation…"):
            prompt2 = f"""Based on this topic frequency data, give ONE specific factual observation.
Only state what the numbers clearly show.
If data is not conclusive, return exactly: "Keep adding notes for a clearer picture."
Maximum 2 sentences.

Data: {topic_counts}
Total notes: {len(all_notes)}
Date range: {date_range}
"""
            st.session_state["blind_spot_insight"] = generate(prompt2)

    insight = st.session_state.get("blind_spot_insight", "")
    if insight:
        st.markdown(
            f'<div style="background:#F8F9FA;border:1px solid #E5E7EB;border-radius:10px;'
            f'padding:14px 16px;margin:12px 0;font-size:0.9rem;color:#1E1E2E;">'
            f'🤖 {insight}</div>',
            unsafe_allow_html=True
        )

    st.caption(
        f"Based on {len(all_notes)} notes from {date_range} · "
        f"Last updated {now_ist().strftime('%d %b %Y, %I:%M %p')} IST"
    )
    with st.expander("How is this calculated?"):
        st.markdown("""
**Life area counting**: Gemini reads your notes and counts how many explicitly mention each life area. It never infers — if a note doesn't clearly mention an area, it's not counted.
**Frequent (4+ notes)**: Areas that appear more than 3 times across your notes.
**Rarely on your mind (0 notes)**: Areas with zero mentions across all notes — not 1 or 2, exactly 0.
**AI observation**: Only states what the numbers clearly show. If the data is mixed or unclear, it says so.
""")


def show_insights(all_notes: list):
    st.subheader("📊 Pattern Intelligence")
    st.caption("Understand your thinking patterns — when, what, and how often.")

    if not all_notes:
        st.info("Add some notes first to see your thinking patterns.")
        return

    _show_heatmap(all_notes)
    st.divider()

    # ── QUICK STATS ROW ──────────────────────────────────────────────
    total = len(all_notes)
    week_notes = _get_week_notes(all_notes)
    cat_counts = Counter(n.get("category", "Personal") for n in all_notes)
    top_cat = cat_counts.most_common(1)[0][0] if cat_counts else "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Notes", total)
    c2.metric("This Week", len(week_notes))
    c3.metric("Most Common Category", f"{CAT_EMOJI.get(top_cat,'')} {top_cat}")
    c4.metric("Categories Used", len(cat_counts))

    st.divider()

    col_left, col_right = st.columns(2)

    # ── MOST ACTIVE DAY OF WEEK ───────────────────────────────────────
    with col_left:
        st.markdown("**📅 Most Active Thinking Day**")
        day_counts = Counter()
        for n in all_notes:
            # Try stored day_of_week first
            dow = n.get("day_of_week", "")
            if dow:
                day_counts[dow] += 1
            else:
                d = _parse_date(n.get("date", "") or n.get("created_time", ""))
                if d:
                    day_counts[d.strftime("%A")] += 1

        if day_counts:
            days_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            day_data = {d: day_counts.get(d, 0) for d in days_order}
            max_count = max(day_data.values()) or 1
            for day, count in day_data.items():
                bar_w = int(count / max_count * 100)
                top = day == day_counts.most_common(1)[0][0]
                color = "#4F46E5" if top else "#E5E7EB"
                label_color = "#4F46E5" if top else "#6B7280"
                st.markdown(
                    f'<div style="margin:4px 0;display:flex;align-items:center;gap:8px;">'
                    f'<div style="width:80px;font-size:0.82rem;color:{label_color};font-weight:{"600" if top else "400"};">{day[:3]}</div>'
                    f'<div style="flex:1;background:#F3F4F6;border-radius:4px;height:16px;overflow:hidden;">'
                    f'<div style="width:{bar_w}%;background:{color};height:100%;border-radius:4px;"></div></div>'
                    f'<div style="width:28px;font-size:0.78rem;color:#9CA3AF;text-align:right;">{count}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.caption("Not enough data yet.")

    # ── MOST ACTIVE TIME OF DAY ───────────────────────────────────────
    with col_right:
        st.markdown("**🕐 Most Active Thinking Time (IST)**")
        hour_counts = Counter()
        for n in all_notes:
            h = _parse_time_hour(n.get("time", "") or n.get("created_time", ""))
            if h is not None:
                hour_counts[h] += 1

        if hour_counts:
            # Group into blocks
            blocks = {
                "Morning (6–12)":   sum(hour_counts.get(h, 0) for h in range(6, 12)),
                "Afternoon (12–17)": sum(hour_counts.get(h, 0) for h in range(12, 17)),
                "Evening (17–21)":  sum(hour_counts.get(h, 0) for h in range(17, 21)),
                "Night (21–6)":     sum(hour_counts.get(h, 0) for h in list(range(21, 24)) + list(range(0, 6))),
            }
            max_b = max(blocks.values()) or 1
            top_block = max(blocks, key=blocks.get)
            for label, count in blocks.items():
                bar_w = int(count / max_b * 100)
                top = label == top_block
                color = "#4F46E5" if top else "#E5E7EB"
                lc    = "#4F46E5" if top else "#6B7280"
                st.markdown(
                    f'<div style="margin:4px 0;display:flex;align-items:center;gap:8px;">'
                    f'<div style="width:140px;font-size:0.82rem;color:{lc};font-weight:{"600" if top else "400"};">{label}</div>'
                    f'<div style="flex:1;background:#F3F4F6;border-radius:4px;height:16px;overflow:hidden;">'
                    f'<div style="width:{bar_w}%;background:{color};height:100%;border-radius:4px;"></div></div>'
                    f'<div style="width:28px;font-size:0.78rem;color:#9CA3AF;text-align:right;">{count}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.caption("Not enough time data yet.")

    st.divider()

    col_kw, col_cat = st.columns(2)

    # ── TOP 5 KEYWORDS ────────────────────────────────────────────────
    with col_kw:
        st.markdown("**🔑 Top 5 Repeated Keywords**")
        word_counts = Counter()
        for n in all_notes:
            words = re.findall(r"\b[a-zA-Z]{3,}\b", n.get("content", "").lower())
            word_counts.update(w for w in words if w not in _STOPWORDS)

        top_words = word_counts.most_common(5)
        if top_words:
            max_wc = top_words[0][1] or 1
            for word, count in top_words:
                bar_w = int(count / max_wc * 100)
                st.markdown(
                    f'<div style="margin:6px 0;display:flex;align-items:center;gap:8px;">'
                    f'<div style="width:100px;font-size:0.85rem;color:#1E1E2E;font-weight:500;">{word.capitalize()}</div>'
                    f'<div style="flex:1;background:#F3F4F6;border-radius:4px;height:18px;overflow:hidden;">'
                    f'<div style="width:{bar_w}%;background:#4F46E5;height:100%;border-radius:4px;"></div></div>'
                    f'<div style="width:32px;font-size:0.8rem;color:#9CA3AF;text-align:right;">{count}×</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.caption("Not enough data yet.")

    # ── CATEGORY DISTRIBUTION ─────────────────────────────────────────
    with col_cat:
        st.markdown("**📂 Category Distribution**")
        if cat_counts:
            total_cats = sum(cat_counts.values())
            for cat in BRAIN_CATEGORIES:
                count = cat_counts.get(cat, 0)
                pct = int(count / total_cats * 100) if total_cats else 0
                color = _CAT_COLOR.get(cat, "#6B7280")
                emoji = CAT_EMOJI.get(cat, "📝")
                st.markdown(
                    f'<div style="margin:6px 0;display:flex;align-items:center;gap:8px;">'
                    f'<div style="width:100px;font-size:0.82rem;color:#374151;">{emoji} {cat}</div>'
                    f'<div style="flex:1;background:#F3F4F6;border-radius:4px;height:16px;overflow:hidden;">'
                    f'<div style="width:{pct}%;background:{color};height:100%;border-radius:4px;"></div></div>'
                    f'<div style="width:40px;font-size:0.78rem;color:#9CA3AF;text-align:right;">{count} ({pct}%)</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

    st.divider()

    # ── TIMELINE VIEW ─────────────────────────────────────────────────
    st.markdown("**📅 Timeline View**")
    tl_filter = st.selectbox(
        "Show", ["This Week", "This Month", "All Time"],
        key="insights_timeline_filter",
        label_visibility="visible",
    )

    now = now_ist()
    if tl_filter == "This Week":
        cutoff = (now - datetime.timedelta(days=7)).date()
    elif tl_filter == "This Month":
        cutoff = (now - datetime.timedelta(days=30)).date()
    else:
        cutoff = None

    tl_notes = []
    for n in all_notes:
        d = _parse_date(n.get("date", "") or n.get("created_time", ""))
        if cutoff is None or (d and d.date() >= cutoff):
            tl_notes.append((d, n))

    tl_notes.sort(key=lambda x: x[0] or datetime.datetime.min, reverse=True)

    if not tl_notes:
        st.info("No notes in this period.")
    else:
        for d, n in tl_notes[:50]:
            cat   = n.get("category", "Personal")
            color = _CAT_COLOR.get(cat, "#6B7280")
            emoji = CAT_EMOJI.get(cat, "📝")
            date_label = d.strftime("%d %b %Y, %I:%M %p") if d else n.get("date", "")
            content = n.get("content", "")
            st.markdown(
                f'<div style="display:flex;gap:12px;margin:8px 0;padding:10px 14px;'
                f'background:#F8F9FA;border:1px solid #E5E7EB;border-radius:8px;'
                f'border-left:3px solid {color};">'
                f'<div style="min-width:140px;font-size:0.78rem;color:#9CA3AF;">{date_label}</div>'
                f'<div style="flex:1;">'
                f'<span style="background:{color}20;color:{color};'
                f'border-radius:12px;padding:1px 8px;font-size:0.72rem;font-weight:600;">'
                f'{emoji} {cat}</span>'
                f'<div style="margin-top:4px;font-size:0.88rem;color:#1E1E2E;">'
                f'{content[:160]}{"…" if len(content)>160 else ""}</div>'
                f'</div></div>',
                unsafe_allow_html=True
            )
        if len(tl_notes) > 50:
            st.caption(f"Showing 50 of {len(tl_notes)} notes. Use Browse Notes tab to see all.")

    st.divider()

    # ── WEEKLY AI SUMMARY ─────────────────────────────────────────────
    st.markdown("**🤖 Weekly AI Summary**")
    if week_notes:
        if st.button("Generate Weekly Summary", type="primary", key="gen_weekly_summary"):
            with st.spinner("Analysing your week…"):
                week_text = "\n".join(
                    f"[{n.get('category','')}] {n.get('content','')[:100]}"
                    for n in week_notes[:25]
                )
                prompt = f"""You are Mufakkir, a personal brain assistant.
The user saved these notes this week:

{week_text}

Write a 2-3 sentence summary of their thinking this week:
- What topics dominated their mind?
- Any patterns or themes?
- One insight or observation.

Be personal, warm, and specific. Mention actual topics from the notes."""
                summary = generate(prompt)
                st.session_state["weekly_summary"] = summary

        if "weekly_summary" in st.session_state:
            st.markdown(
                f'<div style="background:#F0F0FF;border:1px solid #C7D2FE;border-radius:10px;'
                f'padding:16px 18px;font-size:0.95rem;color:#1E1E2E;line-height:1.6;">'
                f'{st.session_state["weekly_summary"]}</div>',
                unsafe_allow_html=True
            )
    else:
        st.caption("No notes this week yet. Start capturing thoughts!")

    st.divider()
    _show_mood_trends(all_notes)

    st.divider()
    _show_blind_spot(all_notes)

    st.divider()
    st.markdown("**☁️ Topic Clouds**")
    st.caption("Your notes grouped by category — hover over dots to read them.")
    from modules.brain.brain_map import render_topic_clouds
    render_topic_clouds(all_notes)
