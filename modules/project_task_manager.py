# ── project_task_manager.py ───────────────────────────────────────────
# Module 2: Project & Task Manager
#
# Features:
# 1. Chat with UNI bot — type natural language, it creates/updates tasks
# 2. Projects tab — create and view all projects
# 3. Tasks tab — view all tasks, filter by project/status/priority
# 4. Analytics tab — charts showing project/task health
#
# How the AI bot (UNI) works:
# - User types: "Add task write report for MBA project by Friday"
# - UNI sends this to Gemini with the list of existing projects as context
# - Gemini returns a JSON command like: {"action": "add_task", "data": {...}}
# - We parse that JSON and perform the action in Google Sheets
# ─────────────────────────────────────────────────────────────────────

import streamlit as st
import json
import uuid
import pandas as pd
from utils.date_utils import now_date_str, now_time_str, now_datetime_str
from database.sheets_client import (
    get_all_rows, add_row, update_row, delete_row,
    get_as_dataframe, log_activity
)
from ai.gemini_client import generate
from config.settings import PROJECT_STATUSES, TASK_PRIORITIES, TASK_STATUSES


# ── UNI BOT HELPER ───────────────────────────────────────────────────

def build_uni_prompt(user_message: str, projects: list, tasks: list) -> str:
    """
    Builds the full prompt for UNI bot.

    We pass current projects and tasks as context so Gemini
    knows what projects exist when user says "add task to MBA project".
    """
    project_list = "\n".join(
        [f"- ID: {p.get('project_id')}, Name: {p.get('name')}, Status: {p.get('status')}"
         for p in projects]
    ) or "No projects yet."

    task_list = "\n".join(
        [f"- ID: {t.get('task_id')}, Task: {t.get('task_name')}, Project: {t.get('project_id')}, Status: {t.get('status')}"
         for t in tasks[:20]]  # only last 20 tasks to keep prompt short
    ) or "No tasks yet."

    return f"""You are UNI, an AI project assistant for UNIFIQ.
The user has told you: "{user_message}"

Current projects:
{project_list}

Recent tasks:
{task_list}

Based on the user's message, return ONLY a JSON object with this exact format:

For adding a task:
{{"action": "add_task", "project_id": "<match from list or NEW>", "task_name": "<name>", "priority": "High/Medium/Low", "due_date": "<DD Mon YYYY or empty>", "message": "<friendly reply>"}}

For adding a project:
{{"action": "add_project", "name": "<project name>", "description": "<description>", "deadline": "<DD Mon YYYY or empty>", "message": "<friendly reply>"}}

For updating task status:
{{"action": "update_task_status", "task_id": "<task_id>", "new_status": "To Do/In Progress/Done", "message": "<friendly reply>"}}

For general chat (no action needed):
{{"action": "chat", "message": "<your helpful reply>"}}

Important rules:
- Return ONLY the JSON. No text before or after it.
- Match project names case-insensitively
- If the project doesn't exist, use "NEW" as project_id
- Dates should be in format: 20 Nov 2026
- Keep messages short and friendly
"""


def parse_uni_response(response: str) -> dict:
    """
    Parses Gemini's JSON response.
    Returns the action dict or a fallback chat message.
    """
    try:
        # Find JSON in response (Gemini sometimes adds extra text)
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            return json.loads(json_str)
    except Exception:
        pass

    return {"action": "chat", "message": response}


def execute_uni_action(action_dict: dict, projects: list) -> str:
    """
    Executes the action from UNI bot.
    Returns a status message.
    """
    action = action_dict.get("action", "chat")
    message = action_dict.get("message", "Done!")

    if action == "add_project":
        project_id = "P" + str(uuid.uuid4())[:6].upper()
        row = [
            project_id,
            action_dict.get("name", "New Project"),
            action_dict.get("description", ""),
            action_dict.get("deadline", ""),
            "Active",
            now_date_str()
        ]
        add_row("projects", row)
        log_activity("Project Added", f"UNI added project: {action_dict.get('name')}")

    elif action == "add_task":
        task_id = "T" + str(uuid.uuid4())[:6].upper()
        project_id = action_dict.get("project_id", "")

        # If NEW project needed, create it first
        if project_id == "NEW":
            project_id = "P" + str(uuid.uuid4())[:6].upper()
            add_row("projects", [project_id, "New Project", "", "", "Active", now_date_str()])

        row = [
            task_id,
            project_id,
            action_dict.get("task_name", "New Task"),
            action_dict.get("priority", "Medium"),
            action_dict.get("due_date", ""),
            "To Do",
            now_date_str()
        ]
        add_row("tasks", row)
        log_activity("Task Added", f"UNI added task: {action_dict.get('task_name')}")

    elif action == "update_task_status":
        # Find the task row number and update it
        all_tasks = get_all_rows("tasks")
        target_id = action_dict.get("task_id", "")
        for i, task in enumerate(all_tasks, start=2):  # row 1 = header
            if task.get("task_id") == target_id:
                update_row("tasks", i, [
                    task.get("task_id"),
                    task.get("project_id"),
                    task.get("task_name"),
                    task.get("priority"),
                    task.get("due_date"),
                    action_dict.get("new_status"),
                    task.get("created_date")
                ])
                log_activity("Task Updated", f"UNI updated task {target_id} to {action_dict.get('new_status')}")
                break

    return message


# ── ANALYTICS HELPERS ────────────────────────────────────────────────

def get_project_stats(projects: list, tasks: list) -> dict:
    """
    Computes summary numbers for the analytics view.
    """
    total_projects = len(projects)
    active = sum(1 for p in projects if p.get("status") == "Active")
    completed = sum(1 for p in projects if p.get("status") == "Completed")

    total_tasks = len(tasks)
    todo = sum(1 for t in tasks if t.get("status") == "To Do")
    in_progress = sum(1 for t in tasks if t.get("status") == "In Progress")
    done = sum(1 for t in tasks if t.get("status") == "Done")
    high_priority = sum(1 for t in tasks if t.get("priority") == "High")

    return {
        "total_projects": total_projects,
        "active": active,
        "completed": completed,
        "total_tasks": total_tasks,
        "todo": todo,
        "in_progress": in_progress,
        "done": done,
        "high_priority": high_priority,
    }


# ── MAIN PAGE ────────────────────────────────────────────────────────

def show():
    """
    Renders the Project & Task Manager page.
    Called from app.py.
    """
    st.title("📋 Project & Task Manager")
    st.caption("Manage projects, tasks, and talk to UNI — your AI project assistant.")

    # Load data once
    projects = get_all_rows("projects")
    tasks = get_all_rows("tasks")

    # ── TABS ─────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["🤖 UNI Bot", "📁 Projects", "✅ Tasks", "📊 Analytics"])

    # ── TAB 1: UNI BOT ───────────────────────────────────────────────
    with tab1:
        st.subheader("Chat with UNI")
        st.caption("Tell UNI what you need. Add tasks, create projects, or ask questions.")

        # Initialize chat history
        if "uni_chat" not in st.session_state:
            st.session_state.uni_chat = [
                {
                    "role": "assistant",
                    "content": "Hi! I'm UNI 👋 Tell me what you need. Try: 'Add a task to submit MBA report by Friday' or 'Create a new project for case competition'"
                }
            ]

        # Display chat history
        for msg in st.session_state.uni_chat:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        # User input
        user_input = st.chat_input("Tell UNI what to do...")

        if user_input:
            # Add user message to history
            st.session_state.uni_chat.append({"role": "user", "content": user_input})

            with st.chat_message("user"):
                st.write(user_input)

            # Get UNI response
            with st.chat_message("assistant"):
                with st.spinner("UNI is thinking..."):
                    try:
                        prompt = build_uni_prompt(user_input, projects, tasks)
                        raw_response = generate(prompt)
                        action_dict = parse_uni_response(raw_response)
                        reply = execute_uni_action(action_dict, projects)

                        st.write(reply)
                        st.session_state.uni_chat.append({"role": "assistant", "content": reply})

                        # Refresh data after action
                        if action_dict.get("action") != "chat":
                            st.rerun()

                    except Exception as e:
                        err_msg = f"UNI hit an error: {e}"
                        st.error(err_msg)
                        st.session_state.uni_chat.append({"role": "assistant", "content": err_msg})

    # ── TAB 2: PROJECTS ──────────────────────────────────────────────
    with tab2:
        st.subheader("All Projects")

        # Quick stats
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Projects", len(projects))
        col2.metric("Active", sum(1 for p in projects if p.get("status") == "Active"))
        col3.metric("Completed", sum(1 for p in projects if p.get("status") == "Completed"))

        st.divider()

        # Add project form
        with st.expander("➕ Add New Project"):
            with st.form("add_project_form"):
                p_name = st.text_input("Project Name", placeholder="e.g. MBA Case Competition")
                p_desc = st.text_input("Description (optional)")
                p_deadline = st.text_input("Deadline (optional)", placeholder="e.g. 20 Dec 2026")
                p_status = st.selectbox("Status", PROJECT_STATUSES)

                if st.form_submit_button("Add Project", type="primary"):
                    if p_name.strip():
                        pid = "P" + str(uuid.uuid4())[:6].upper()
                        add_row("projects", [pid, p_name, p_desc, p_deadline, p_status, now_date_str()])
                        log_activity("Project Added", p_name)
                        st.success(f"Project '{p_name}' added!")
                        st.rerun()
                    else:
                        st.warning("Please enter a project name.")

        # Show projects
        if not projects:
            st.info("No projects yet. Use UNI bot or the form above to add your first project.")
        else:
            for project in projects:
                status = project.get("status", "Active")
                status_color = {"Active": "🟢", "On Hold": "🟡", "Completed": "✅", "Cancelled": "🔴"}.get(status, "⚪")

                # Count tasks for this project
                project_tasks = [t for t in tasks if t.get("project_id") == project.get("project_id")]
                done_count = sum(1 for t in project_tasks if t.get("status") == "Done")

                with st.expander(f"{status_color} {project.get('name')} — {done_count}/{len(project_tasks)} tasks done"):
                    col1, col2 = st.columns(2)
                    col1.write(f"**ID:** {project.get('project_id')}")
                    col2.write(f"**Status:** {status}")
                    if project.get("description"):
                        st.write(f"**Description:** {project.get('description')}")
                    if project.get("deadline"):
                        st.write(f"**Deadline:** {project.get('deadline')}")
                    st.write(f"**Created:** {project.get('created_date')}")

                    # Task list inside project
                    if project_tasks:
                        st.write("**Tasks:**")
                        for t in project_tasks:
                            priority_icon = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(t.get("priority"), "⚪")
                            task_status = t.get("status", "To Do")
                            done_icon = "✅" if task_status == "Done" else "⬜"
                            st.write(f"{done_icon} {priority_icon} {t.get('task_name')} — {task_status}")

    # ── TAB 3: TASKS ─────────────────────────────────────────────────
    with tab3:
        st.subheader("All Tasks")

        # Filters
        col1, col2, col3 = st.columns(3)

        with col1:
            project_options = ["All Projects"] + [p.get("name", "") for p in projects]
            filter_project = st.selectbox("Project", project_options)

        with col2:
            filter_status = st.selectbox("Status", ["All"] + TASK_STATUSES)

        with col3:
            filter_priority = st.selectbox("Priority", ["All"] + TASK_PRIORITIES)

        # Build project id → name map
        pid_to_name = {p.get("project_id"): p.get("name") for p in projects}

        # Filter tasks
        filtered_tasks = tasks

        if filter_project != "All Projects":
            # Find project_id for selected name
            matching_pid = next(
                (p.get("project_id") for p in projects if p.get("name") == filter_project),
                None
            )
            if matching_pid:
                filtered_tasks = [t for t in filtered_tasks if t.get("project_id") == matching_pid]

        if filter_status != "All":
            filtered_tasks = [t for t in filtered_tasks if t.get("status") == filter_status]

        if filter_priority != "All":
            filtered_tasks = [t for t in filtered_tasks if t.get("priority") == filter_priority]

        # Quick stats
        st.write(f"Showing **{len(filtered_tasks)}** tasks")

        # Add task form
        with st.expander("➕ Add New Task"):
            with st.form("add_task_form"):
                project_names = [p.get("name", "") for p in projects]
                if project_names:
                    t_project = st.selectbox("Project", project_names)
                else:
                    st.warning("Create a project first.")
                    t_project = None

                t_name = st.text_input("Task Name")
                t_priority = st.selectbox("Priority", TASK_PRIORITIES)
                t_due = st.text_input("Due Date (optional)", placeholder="e.g. 25 Nov 2026")

                if st.form_submit_button("Add Task", type="primary"):
                    if t_name.strip() and t_project:
                        pid = next(
                            (p.get("project_id") for p in projects if p.get("name") == t_project),
                            ""
                        )
                        tid = "T" + str(uuid.uuid4())[:6].upper()
                        add_row("tasks", [tid, pid, t_name, t_priority, t_due, "To Do", now_date_str()])
                        log_activity("Task Added", t_name)
                        st.success("Task added!")
                        st.rerun()
                    else:
                        st.warning("Please fill in task name and select a project.")

        # Show tasks as table
        if filtered_tasks:
            # Build a clean display dataframe
            display_rows = []
            for t in filtered_tasks:
                priority = t.get("priority", "Medium")
                status = t.get("status", "To Do")
                project_name = pid_to_name.get(t.get("project_id"), t.get("project_id", ""))

                priority_icon = {"High": "🔴 High", "Medium": "🟡 Medium", "Low": "🟢 Low"}.get(priority, priority)
                status_icon = {"To Do": "⬜ To Do", "In Progress": "🔄 In Progress", "Done": "✅ Done"}.get(status, status)

                display_rows.append({
                    "ID": t.get("task_id"),
                    "Task": t.get("task_name"),
                    "Project": project_name,
                    "Priority": priority_icon,
                    "Status": status_icon,
                    "Due Date": t.get("due_date", ""),
                })

            df = pd.DataFrame(display_rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No tasks match the filters. Try a different filter or add tasks via UNI bot.")

    # ── TAB 4: ANALYTICS ─────────────────────────────────────────────
    with tab4:
        st.subheader("Project & Task Analytics")

        stats = get_project_stats(projects, tasks)

        # Row 1: Overview metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Projects", stats["total_projects"])
        c2.metric("Active Projects", stats["active"])
        c3.metric("Total Tasks", stats["total_tasks"])
        c4.metric("High Priority", stats["high_priority"])

        st.divider()

        # Row 2: Task status breakdown
        st.subheader("Task Status")
        task_col1, task_col2, task_col3 = st.columns(3)

        # Progress bar for each status
        total = stats["total_tasks"] or 1  # avoid divide by zero

        task_col1.metric("To Do", stats["todo"])
        task_col1.progress(stats["todo"] / total)

        task_col2.metric("In Progress", stats["in_progress"])
        task_col2.progress(stats["in_progress"] / total)

        task_col3.metric("Done", stats["done"])
        task_col3.progress(stats["done"] / total)

        st.divider()

        # Row 3: Per-project breakdown
        if projects:
            st.subheader("Tasks per Project")
            project_summary = []
            for project in projects:
                pid = project.get("project_id")
                project_tasks = [t for t in tasks if t.get("project_id") == pid]
                todo_c = sum(1 for t in project_tasks if t.get("status") == "To Do")
                prog_c = sum(1 for t in project_tasks if t.get("status") == "In Progress")
                done_c = sum(1 for t in project_tasks if t.get("status") == "Done")

                project_summary.append({
                    "Project": project.get("name"),
                    "Status": project.get("status"),
                    "Total Tasks": len(project_tasks),
                    "To Do": todo_c,
                    "In Progress": prog_c,
                    "Done": done_c,
                })

            if project_summary:
                df_proj = pd.DataFrame(project_summary)
                st.dataframe(df_proj, use_container_width=True, hide_index=True)

        # Row 4: Priority breakdown
        if tasks:
            st.divider()
            st.subheader("Priority Breakdown")
            high = stats["high_priority"]
            medium = sum(1 for t in tasks if t.get("priority") == "Medium")
            low = sum(1 for t in tasks if t.get("priority") == "Low")

            p1, p2, p3 = st.columns(3)
            p1.metric("🔴 High", high)
            p2.metric("🟡 Medium", medium)
            p3.metric("🟢 Low", low)
