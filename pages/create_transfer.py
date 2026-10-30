import streamlit as st
from datetime import date
from models.schemas import HandoverInput
from services.handover_service import create_handover, update_handover_status
from services.document_service import extract_text, save_document
from pages.shared import users, user_selectbox
from services.ai_service import AIServiceError, extract_insights


def render(settings):
    st.title("Create Knowledge Transfer")
    people = users(settings)
    with st.form("create_transfer"):
        left, right = st.columns(2)
        outgoing = user_selectbox(people, "Outgoing employee", "outgoing")
        incoming = user_selectbox(people, "Incoming employee", "incoming")
        project = left.text_input("Project or workstream")
        transfer_date = right.date_input("Transfer date", value=date.today())
        scope = st.text_input("Transfer scope", placeholder="Service ownership, client context, release operations...")
        description = st.text_area("Description", placeholder="What responsibility is changing hands?")
        notes = st.text_area("Meeting notes, project updates, pending work or exported emails")
        documents = st.file_uploader(
            "Upload documents, meeting notes, project updates or exported emails",
            type=["pdf", "docx", "txt"], accept_multiple_files=True,
        )
        submitted = st.form_submit_button("Create knowledge transfer", type="primary")
    if submitted:
        try:
            if not notes.strip() and not documents:
                raise ValueError("Add meeting notes, pending work, or at least one source document.")
            handover_id = create_handover(settings.database_path, HandoverInput(outgoing, incoming, project, transfer_date, scope, description, notes))
            extracted_sources = [description, notes]
            for document in documents or []:
                save_document(settings.database_path, settings.upload_dir, handover_id, document.name, document.getvalue(), settings.chroma_dir)
                extracted_sources.append(extract_text(document.name, document.getvalue()))
            try:
                insights = extract_insights(settings.gemini_api_key, settings.gemini_model, "\n\n".join(extracted_sources))
                st.session_state["pending_transfer_review"] = {"handover_id": handover_id, "data": insights}
                st.success(f"Transfer #{handover_id} created as Draft. Review the AI extraction below.")
            except AIServiceError as exc:
                st.warning(f"Transfer #{handover_id} created as Draft without AI extraction: {exc}")
        except (ValueError, OSError) as exc:
            st.error(str(exc))
    pending = st.session_state.get("pending_transfer_review")
    if pending:
        st.subheader("Review extracted transfer knowledge")
        data = pending["data"]
        st.write(data.get("summary", ""))
        with st.form("confirm_transfer_knowledge"):
            decisions = st.text_area("Decisions", value="\n".join(str(item) for item in data.get("decisions", [])))
            risks = st.text_area("Risks", value="\n".join(str(item) for item in data.get("risks", [])))
            unresolved = st.text_area("Unresolved issues", value="\n".join(str(item) for item in data.get("unresolved_questions", [])))
            extracted_tasks = data.get("action_items", [])
            selected_tasks = st.multiselect(
                "Action items to save",
                list(range(len(extracted_tasks))),
                format_func=lambda index: extracted_tasks[index].get("title", "Untitled task"),
            )
            if st.form_submit_button("Confirm extraction and start transfer", type="primary"):
                from services.common import execute
                from services.task_service import create_task
                from models.schemas import ActionItemInput
                people = {row["name"]: row["id"] for row in users(settings)}
                execute(settings.database_path, "UPDATE handovers SET notes=?,status='In Progress',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (f"{data.get('summary', '')}\n\nRisks:\n{risks}\n\nUnresolved:\n{unresolved}", pending["handover_id"]))
                for decision in [item.strip() for item in decisions.splitlines() if item.strip()]:
                    execute(settings.database_path, "INSERT INTO decisions(handover_id,decision_text) VALUES(?,?)", (pending["handover_id"], decision))
                for index in selected_tasks:
                    item = extracted_tasks[index]
                    due_date = None
                    try:
                        due_date = date.fromisoformat(item["due_date"]) if item.get("due_date") else None
                    except (TypeError, ValueError):
                        due_date = None
                    create_task(settings.database_path, ActionItemInput(
                        pending["handover_id"], item["title"], item.get("description", ""),
                        people.get(item.get("owner_name")), due_date, "Medium",
                    ), actor_id=outgoing)
                update_handover_status(settings.database_path, pending["handover_id"], "In Progress", outgoing)
                st.session_state.pop("pending_transfer_review")
                st.success("Reviewed knowledge committed and transfer moved to In Progress.")
