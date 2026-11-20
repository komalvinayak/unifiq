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


def show_insights(all_notes: list):
    st.subheader("📊 Pattern Intelligence")
    st.caption("Understand your thinking patterns — when, what, and how often.")

    if not all_notes:
        st.info("Add some notes first to see your thinking patterns.")
        return

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
