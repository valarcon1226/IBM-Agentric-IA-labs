import datetime
import json
import os
from typing import Any

import httpx
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8006").rstrip("/")
AUTH_HEADERS = {"Authorization": f"Bearer {os.environ.get('API_KEY', 'change_me_api_key')}"}

st.set_page_config(
    page_title="Task Scheduler Engine",
    page_icon="⏱️",
    layout="wide",
)

st.title("⏱️ Task Scheduler Engine")
st.caption("DB-backed Celery Beat scheduler with dynamic updates, dependencies and alerting")


def fetch_api(endpoint: str, method: str = "GET", data: dict | None = None) -> Any:
    url = f"{API_URL}{endpoint}"
    try:
        with httpx.Client(timeout=10.0, headers=AUTH_HEADERS) as client:
            if method == "GET":
                resp = client.get(url)
            elif method == "POST":
                resp = client.post(url, json=data)
            elif method == "PUT":
                resp = client.put(url, json=data)
            elif method == "DELETE":
                resp = client.delete(url)
            else:
                st.error(f"Unsupported method {method}")
                return None

            if resp.status_code >= 400:
                st.error(f"API Error ({resp.status_code}): {resp.text}")
                return None
            return resp.json()
    except Exception as exc:
        st.error(f"Could not connect to API at {API_URL}: {exc}")
        return None


# Sidebar
with st.sidebar:
    st.header("Engine Connection")
    health = fetch_api("/health")
    if health and health.get("status") == "healthy":
        st.success(f"API Connected ({API_URL})")
    else:
        st.error(f"API Unavailable ({API_URL})")

    if st.button("🔄 Refresh Data"):
        st.rerun()

    st.markdown("---")
    st.markdown("### Quick Stats")
    tasks_data = fetch_api("/api/v1/tasks") or []
    runs_data = fetch_api("/api/v1/runs?limit=100") or []

    st.metric("Total Tasks", len(tasks_data))
    active_tasks = sum(1 for t in tasks_data if t.get("is_active"))
    st.metric("Active Tasks", active_tasks)
    failed_runs = sum(1 for r in runs_data if r.get("status") == "FAILED")
    st.metric("Recent Failures", failed_runs)


tab_tasks, tab_upcoming, tab_runs, tab_create = st.tabs(
    ["📋 Tasks", "⏳ Next Executions", "📜 Run History & Logs", "➕ Create Task"]
)

# TAB 1: Tasks
with tab_tasks:
    st.subheader("Configured Tasks")
    if not tasks_data:
        st.info("No tasks found. Create one in the 'Create Task' tab.")
    else:
        for task in tasks_data:
            tid = task["task_id"]
            status_tag = "🟢 Active" if task["is_active"] else "⏸️ Paused"
            expander_title = f"**{task['name']}** ({task['task_type']}) — {status_tag}"
            with st.expander(expander_title, expanded=True):
                col1, col2, col3 = st.columns([3, 2, 2])
                with col1:
                    st.write(f"**ID:** `{tid}`")
                    st.write(f"**Type:** `{task['task_type']}`")
                    st.write(f"**Schedule (Cron):** `{task['schedule'] or 'None (Manual)'}`")
                    st.write(f"**Dependencies:** {task.get('depends_on') or 'None'}")
                with col2:
                    st.write(f"**Last Run:** {task.get('last_run_at') or 'Never'}")
                    st.write(f"**Consecutive Failures:** {task.get('consecutive_failures', 0)}")
                    st.write(f"**Created At:** {task.get('created_at') or 'N/A'}")
                with col3:
                    # Action buttons
                    b_col1, b_col2, b_col3 = st.columns(3)
                    with b_col1:
                        if st.button("▶️ Trigger", key=f"trig_{tid}"):
                            res = fetch_api(f"/api/v1/tasks/{tid}/trigger", method="POST")
                            if res:
                                st.success("Task triggered!")
                                st.rerun()
                    with b_col2:
                        toggle_label = "⏸️ Pause" if task["is_active"] else "▶️ Resume"
                        if st.button(toggle_label, key=f"toggle_{tid}"):
                            new_status = not task["is_active"]
                            res = fetch_api(
                                f"/api/v1/tasks/{tid}",
                                method="PUT",
                                data={"is_active": new_status},
                            )
                            if res:
                                st.success(f"Task {'resumed' if new_status else 'paused'}!")
                                st.rerun()
                    with b_col3:
                        if st.button("🗑️ Delete", key=f"del_{tid}"):
                            res = fetch_api(f"/api/v1/tasks/{tid}", method="DELETE")
                            if res:
                                st.warning("Task deleted!")
                                st.rerun()


# TAB 2: Next Executions
with tab_upcoming:
    st.subheader("Upcoming Scheduled Runs")
    upcoming_list = []
    from sqlalchemy_celery_beat.models import CrontabSchedule

    now_utc = datetime.datetime.now(datetime.UTC)

    for task in tasks_data:
        sched = task.get("schedule")
        if sched and task.get("is_active"):
            parts = sched.strip().split()
            if len(parts) == 5:
                try:
                    c = CrontabSchedule(
                        minute=parts[0],
                        hour=parts[1],
                        day_of_month=parts[2],
                        month_of_year=parts[3],
                        day_of_week=parts[4],
                        timezone="UTC",
                    )
                    ct = CrontabSchedule.aware_crontab(c)
                    _, next_in = ct.is_due(now_utc)
                    next_run = now_utc + datetime.timedelta(seconds=next_in)
                    upcoming_list.append(
                        {
                            "Task Name": task["name"],
                            "Type": task["task_type"],
                            "Schedule": sched,
                            "Next Estimated Run (UTC)": next_run.strftime("%Y-%m-%d %H:%M:%S"),
                            "Seconds Remaining": int(next_in),
                        }
                    )
                except Exception:
                    pass

    if upcoming_list:
        upcoming_list.sort(key=lambda x: x["Seconds Remaining"])
        st.dataframe(upcoming_list, use_container_width=True)
    else:
        st.info("No active scheduled tasks.")


# TAB 3: Run History & Logs
with tab_runs:
    st.subheader("Execution History & Logs")
    task_options = {"All Tasks": "all"}
    for t in tasks_data:
        task_options[f"{t['name']} ({t['task_id'][:8]})"] = t["task_id"]

    selected_filter = st.selectbox("Filter by Task:", list(task_options.keys()))
    selected_id = task_options[selected_filter]

    if selected_id == "all":
        runs = fetch_api("/api/v1/runs?limit=50") or []
    else:
        runs = fetch_api(f"/api/v1/tasks/{selected_id}/runs?limit=50") or []

    if not runs:
        st.info("No execution runs recorded yet.")
    else:
        for r in runs:
            status_emoji = {
                "SUCCESS": "✅",
                "FAILED": "❌",
                "RUNNING": "⏳",
                "SKIPPED": "⏭️",
                "RETRYING": "🔁",
            }.get(r["status"], "ℹ️")

            title = (
                f"{status_emoji} {r['status']} | Started: {r['started_at']} | "
                f"Duration: {r.get('duration_ms', 0)} ms | Exit Code: {r.get('exit_code')}"
            )
            with st.expander(title):
                st.write(f"**Run ID:** `{r['run_id']}` | **Task ID:** `{r['task_id']}`")
                if r.get("stdout"):
                    st.markdown("**Stdout:**")
                    st.code(r["stdout"])
                if r.get("stderr"):
                    st.markdown("**Stderr:**")
                    st.code(r["stderr"])


# TAB 4: Create Task
with tab_create:
    st.subheader("Create a New Task")
    with st.form("create_task_form"):
        name = st.text_input("Task Name", value="Sample Task")
        task_type = st.selectbox("Task Type", ["HTTP", "SHELL", "PYTHON"])

        st.markdown("##### Task Payload")
        payload = {}
        if task_type == "HTTP":
            url = st.text_input("Target URL", value="http://webhook-sink:8080/sample")
            method = st.selectbox("HTTP Method", ["GET", "POST", "PUT", "DELETE"])
            default_headers = '{"Content-Type": "application/json"}'
            headers_str = st.text_area("Headers (JSON)", value=default_headers)
            body_str = st.text_area("JSON Body (optional)", value='{"hello": "world"}')
            payload = {
                "url": url,
                "method": method,
            }
            if headers_str.strip():
                try:
                    payload["headers"] = json.loads(headers_str)
                except Exception:
                    pass
            if body_str.strip():
                try:
                    payload["json"] = json.loads(body_str)
                except Exception:
                    pass
        elif task_type == "SHELL":
            command = st.text_input("Script/Command Name (inside jobs/)", value="backup.sh")
            args_str = st.text_input("Arguments (space separated)", value="production_db")
            args = args_str.split() if args_str.strip() else []
            payload = {"command": command, "args": args}
        elif task_type == "PYTHON":
            script = st.text_input("Python Script Name (inside jobs/)", value="demo_success.py")
            args_str = st.text_input("Arguments (space separated)", value="arg1 arg2")
            args = args_str.split() if args_str.strip() else []
            payload = {"script": script, "args": args}

        schedule = st.text_input(
            "Schedule (Cron expression 5 fields, e.g. '*/1 * * * *', leave empty for manual only)",
            value="",
        )
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            max_retries = st.number_input("Max Retries", min_value=0, max_value=20, value=3)
        with col_r2:
            retry_backoff = st.number_input(
                "Retry Backoff (seconds)", min_value=1, max_value=3600, value=10
            )

        existing_task_map = {f"{t['name']} ({t['task_id'][:8]})": t["task_id"] for t in tasks_data}
        selected_deps = st.multiselect(
            "Dependencies (Prerequisites that must SUCCEED before this task runs)",
            options=list(existing_task_map.keys()),
        )

        submitted = st.form_submit_button("Create Task")
        if submitted:
            dep_ids = [existing_task_map[d] for d in selected_deps]
            create_payload = {
                "name": name,
                "task_type": task_type,
                "payload": payload,
                "schedule": schedule.strip() if schedule.strip() else None,
                "max_retries": int(max_retries),
                "retry_backoff": int(retry_backoff),
                "depends_on": dep_ids,
            }
            res = fetch_api("/api/v1/tasks", method="POST", data=create_payload)
            if res:
                st.success(f"Task '{name}' created successfully with ID {res.get('task_id')}!")
                st.rerun()
