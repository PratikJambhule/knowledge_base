import streamlit as st
from datetime import date
from models.schemas import ActionItemInput
from pages.shared import users, handover_options, user_selectbox
from services.task_service import list_tasks, create_task, update_task


def render(settings):
    st.title("Task Management")
    search = st.text_input("Search tasks", placeholder="Search title or description")
    tasks = list_tasks(settings.database_path, search)
    st.metric("Tasks shown", len(tasks))
    with st.expander("Create action item"):
        handovers = handover_options(settings)
        people = users(settings)
        if handovers:
            with st.form("create_task"):
                hmap = {f"{h['project_name']} · {h['title']}": h["id"] for h in handovers}
                handover_id = hmap[st.selectbox("Knowledge transfer", list(hmap))]
                title = st.text_input("Task title")
                description = st.text_area("Description")
                owner = user_selectbox(people, "Owner", "task_owner")
                due_date = st.date_input("Due date", value=date.today())
                priority = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"])
                if st.form_submit_button("Create task"):
                    try:
                        create_task(settings.database_path, ActionItemInput(handover_id, title, description, owner, due_date, priority))
                        st.success("Task created.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
    for task in tasks:
        with st.expander(f"{task['title']} · {task['status']} · due {task['due_date']}"):
            st.write(task["description"] or "No description")
            with st.form(f"edit_{task['id']}"):
                people = users(settings)
                actor = user_selectbox(people, "Updated by", f"actor_{task['id']}")
                owner = user_selectbox(people, "Owner", f"owner_{task['id']}")
                status = st.selectbox("Status", ["Open", "In Progress", "Blocked", "Completed", "Cancelled"], index=["Open", "In Progress", "Blocked", "Completed", "Cancelled"].index(task["status"]))
                outcome = st.text_area("Completion or outcome", value=task["outcome"] or "")
                if st.form_submit_button("Save task"):
                    try:
                        update_task(settings.database_path, task["id"], status, owner, outcome, actor)
                        st.success("Task updated.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
