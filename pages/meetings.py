import streamlit as st
from datetime import date
from models.schemas import MeetingInput
from pages.shared import handover_options
from services.meeting_service import create_meeting, list_meetings
from services.ai_service import AIServiceError, extract_insights, generate_carry_forward_summary
from services.common import execute
from services.common import query
from services.task_service import create_task
from models.schemas import ActionItemInput
from pages.shared import users


def render(settings):
    st.title("Meetings")
    handovers = handover_options(settings)
    if not handovers:
        st.info("Create a knowledge transfer before adding meetings.")
        return
    hmap = {f"{h['project_name']} · {h['title']}": h["id"] for h in handovers}
    selected = st.selectbox("Knowledge transfer", list(hmap))
    handover_id = hmap[selected]
    with st.form("meeting"):
        title = st.text_input("Meeting title")
        meeting_date = st.date_input("Meeting date", value=date.today())
        participants = st.text_input("Participants", placeholder="Names separated by commas")
        agenda = st.text_area("Agenda")
        notes = st.text_area("Notes or transcript")
        open_tasks = query(settings.database_path, "SELECT id,title FROM tasks WHERE handover_id=? AND status NOT IN ('Completed','Cancelled') ORDER BY due_date", (handover_id,))
        carry_forward = st.multiselect(
            "Carry forward open actions",
            options=[task["id"] for task in open_tasks],
            format_func=lambda task_id: next(task["title"] for task in open_tasks if task["id"] == task_id),
        )
        if st.form_submit_button("Save meeting", type="primary"):
            try:
                meeting_id = create_meeting(settings.database_path, MeetingInput(handover_id, title, meeting_date, agenda, participants, notes))
                for task_id in carry_forward:
                    execute(
                        settings.database_path,
                        "INSERT INTO task_history(task_id,event_type,new_value,note) VALUES(?,?,?,?)",
                        (task_id, "carried_forward", str(meeting_id), f"Carried into meeting {meeting_id}"),
                    )
                try:
                    insights = extract_insights(settings.gemini_api_key, settings.gemini_model, notes)
                    st.session_state["pending_insights"] = {"meeting_id": meeting_id, "handover_id": handover_id, "data": insights}
                    st.success("Meeting saved. Review the AI suggestions below before saving them.")
                except AIServiceError as exc:
                    st.warning(f"Meeting saved without AI extraction: {exc} Enter decisions and tasks manually.")
            except ValueError as exc:
                st.error(str(exc))
    pending = st.session_state.get("pending_insights")
    if pending and pending["handover_id"] == handover_id:
        insights = pending["data"]
        st.subheader("Review AI extraction")
        st.write(insights.get("summary", ""))
        with st.form("confirm_ai_extraction"):
            decisions = st.text_area("Decisions to save, one per line", value="\n".join(insights.get("decisions", [])))
            tasks = insights.get("action_items", [])
            selected_tasks = st.multiselect("Action items to save", list(range(len(tasks))), format_func=lambda index: tasks[index].get("title", "Untitled task"))
            if st.form_submit_button("Confirm and save extracted knowledge"):
                execute(settings.database_path, "UPDATE meetings SET summary=? WHERE id=?", (insights.get("summary", ""), pending["meeting_id"]))
                for decision in [item.strip() for item in decisions.splitlines() if item.strip()]:
                    execute(settings.database_path, "INSERT INTO decisions(handover_id,meeting_id,decision_text) VALUES(?,?,?)", (handover_id, pending["meeting_id"], decision))
                people = {row["name"]: row["id"] for row in users(settings)}
                for index in selected_tasks:
                    task = tasks[index]
                    owner_id = people.get(task.get("owner_name"))
                    due_date = task.get("due_date")
                    try:
                        parsed_date = date.fromisoformat(due_date) if due_date else None
                    except ValueError:
                        parsed_date = None
                    create_task(settings.database_path, ActionItemInput(handover_id, task["title"], task.get("description", ""), owner_id, parsed_date, "Medium"), pending["meeting_id"])
                st.session_state.pop("pending_insights")
                st.success("Confirmed AI knowledge saved.")
    if st.button("Prepare carry-forward summary", key=f"carry_summary_{handover_id}"):
        records = query(settings.database_path, "SELECT title,status,due_date,outcome FROM tasks WHERE handover_id=? AND status NOT IN ('Completed','Cancelled')", (handover_id,))
        decisions = query(settings.database_path, "SELECT decision_text FROM decisions WHERE handover_id=? ORDER BY created_at DESC", (handover_id,))
        text = f"Open tasks: {records}\nPrevious decisions: {decisions}"
        try:
            st.info(generate_carry_forward_summary(settings.gemini_api_key, settings.gemini_model, text))
        except AIServiceError as exc:
            st.error(str(exc))
    st.subheader("Meeting history")
    for meeting in list_meetings(settings.database_path, handover_id):
        with st.expander(f"{meeting['meeting_date']} · {meeting['title']}"):
            st.write(meeting["summary"] or meeting["notes"])
