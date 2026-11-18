# ── command_centre.py ────────────────────────────────────────────────
# Module 1: Personal Command Centre
#
# This is your dashboard — the first screen you see.
# Shows an overview of everything happening across UNIFIQ.
#
# What's shown:
# 1. Greeting + current time (IST)
# 2. Quick summary cards (projects, tasks, brain notes)
# 3. Activity feed (last 10 things you did in the app)
# 4. AI Active Key — which Gemini key is being used
# ─────────────────────────────────────────────────────────────────────

import streamlit as st
from utils.date_utils import greeting, now_datetime_str, now_date_str
from database.sheets_client import get_all_rows, get_as_dataframe
from ai.gemini_client import get_active_key_name


def show():
    """
    Renders the Command Centre page.
    Called from app.py.
    """

    # ── HEADER ───────────────────────────────────────────────────────
    col_left, col_right = st.columns([3, 1])
    with col_left:
        st.title(f"⚡ {greeting()}, Welcome to UNIFIQ")
        st.caption(f"🕐 {now_datetime_str()} IST")
    with col_right:
        st.metric("AI Engine", get_active_key_name())

    st.divider()

    # ── LOAD DATA ────────────────────────────────────────────────────
    projects = get_all_rows("projects")
    tasks = get_all_rows("tasks")
    brain_notes = get_all_rows("brain_notes")
    activity_log = get_all_rows("command_log")

    # ── SECTION 1: SUMMARY CARDS ─────────────────────────────────────
    st.subheader("Quick Overview")

    col1, col2, col3, col4 = st.columns(4)

    # Projects
    active_projects = sum(1 for p in projects if p.get("status") == "Active")
    col1.metric(
        label="📁 Active Projects",
        value=active_projects,
        delta=f"{len(projects)} total"
    )

    # Tasks
    pending_tasks = sum(1 for t in tasks if t.get("status") in ["To Do", "In Progress"])
    done_tasks = sum(1 for t in tasks if t.get("status") == "Done")
    col2.metric(
        label="✅ Pending Tasks",
        value=pending_tasks,
        delta=f"{done_tasks} done"
    )

    # High priority tasks
    high_priority = sum(1 for t in tasks if t.get("priority") == "High" and t.get("status") != "Done")
    col3.metric(
        label="🔴 High Priority",
        value=high_priority,
        delta="need attention" if high_priority > 0 else "all clear"
    )

    # Brain notes
    col4.metric(
        label="🧠 Brain Notes",
        value=len(brain_notes),
        delta="thoughts stored"
    )

    st.divider()

    # ── SECTION 2: PROJECT HEALTH ─────────────────────────────────────
    if projects:
        st.subheader("Project Health")
        st.caption("Quick view of each active project and its task completion.")

        active_p = [p for p in projects if p.get("status") == "Active"]
        if active_p:
            for project in active_p:
                pid = project.get("project_id")
                p_name = project.get("name", "Unknown")

                # Count tasks for this project
                p_tasks = [t for t in tasks if t.get("project_id") == pid]
                total_p_tasks = len(p_tasks)
                done_p = sum(1 for t in p_tasks if t.get("status") == "Done")

                # Progress percentage
                progress = (done_p / total_p_tasks) if total_p_tasks > 0 else 0

                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.write(f"**{p_name}**")
                    st.progress(progress)
                with col_b:
                    st.write(f"{done_p}/{total_p_tasks} tasks")

                if project.get("deadline"):
                    st.caption(f"Deadline: {project.get('deadline')}")

                st.write("")  # spacing
        else:
            st.info("No active projects. Go to Project & Task Manager to create one.")

    st.divider()

    # ── SECTION 3: TASK QUICK VIEW ────────────────────────────────────
    st.subheader("Tasks Needing Attention")
    st.caption("High priority and In Progress tasks.")

    urgent_tasks = [
        t for t in tasks
        if t.get("priority") == "High" and t.get("status") != "Done"
        or t.get("status") == "In Progress"
    ]

    if urgent_tasks:
        # Show as a clean table
        import pandas as pd
        pid_to_name = {p.get("project_id"): p.get("name") for p in projects}

        rows = []
        for t in urgent_tasks[:10]:  # max 10
            rows.append({
                "Task": t.get("task_name", ""),
                "Project": pid_to_name.get(t.get("project_id"), "-"),
                "Priority": t.get("priority", ""),
                "Status": t.get("status", ""),
                "Due": t.get("due_date", "-"),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.success("No urgent tasks right now. 🎉 All caught up!")

    st.divider()

    # ── SECTION 4: RECENT ACTIVITY ────────────────────────────────────
    st.subheader("Recent Activity")
    st.caption("What you've been doing in UNIFIQ.")

    if activity_log:
        # Show last 10 activities, newest first
        recent = list(reversed(activity_log))[:10]
        for log in recent:
            event = log.get("event_type", "")
            details = log.get("details", "")
            date = log.get("date", "")
            time = log.get("time", "")

            # Icon per event type
            icon = {
                "Brain Note": "🧠",
                "Project Added": "📁",
                "Task Added": "✅",
                "Task Updated": "🔄",
            }.get(event, "📌")

            st.write(f"{icon} **{event}** — {details}")
            st.caption(f"{date} at {time}")

    else:
        st.info("No activity yet. Start by adding a project or brain note!")

    st.divider()

    # ── SECTION 5: BRAIN NOTES PREVIEW ───────────────────────────────
    st.subheader("Latest Brain Notes")

    if brain_notes:
        latest_notes = list(reversed(brain_notes))[:3]  # last 3
        for note in latest_notes:
            cat = note.get("category", "Personal")
            emoji = {"Work": "💼", "Learning": "📚", "Personal": "🌱"}.get(cat, "📝")
            content = note.get("content", "")
            st.write(f"{emoji} {content[:100]}{'...' if len(content) > 100 else ''}")
            st.caption(f"{cat} · {note.get('date')} at {note.get('time')}")
            st.write("")
    else:
        st.info("No brain notes yet. Go to UNIFIQ Brain to dump your first thought.")
