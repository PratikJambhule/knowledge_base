import streamlit as st
from services.handover_service import list_handovers, get_handover, update_handover_status
from services.common import query
from services.document_service import list_documents
from services.readiness_service import calculate_readiness
from services.ai_service import AIServiceError, analyze_readiness_gaps, generate_handover_brief
from pages.shared import users, user_selectbox


def render(settings):
    st.title("Knowledge Transfer Details")
    handovers = list_handovers(settings.database_path)
    if not handovers:
        st.info("No knowledge transfers yet.")
        return
    labels = {f"#{h['id']} · {h['project_name']} · {h['incoming_name']}": h["id"] for h in handovers}
    selected = st.selectbox("Select transfer", list(labels))
    handover_id = labels[selected]
    handover = get_handover(settings.database_path, handover_id)
    score = calculate_readiness(settings.database_path, handover_id)
    st.header(handover["project_name"])
    st.caption(f"{handover['outgoing_name']} → {handover['incoming_name']} · Transfer date: {handover['transfer_date']} · Scope: {handover['transfer_scope']}")
    st.write(handover["description"])
    people = users(settings)
    state_options = ["Draft", "In Progress", "Pending Acceptance", "Accepted", "Completed"]
    with st.form("transfer_state"):
        actor = user_selectbox(people, "Action performed by", "transfer_actor")
        status = st.selectbox("Transfer state", state_options, index=state_options.index(handover["status"]) if handover["status"] in state_options else 0)
        if st.form_submit_button("Update transfer state"):
            try:
                update_handover_status(settings.database_path, handover_id, status, actor)
                st.success(f"Transfer moved to {status}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    score_col, action_col = st.columns([3, 1])
    score_col.metric("AI Handover Readiness", f"{score['overall']}/100", score["explanation"])
    if action_col.button("Recalculate score", key=f"recalc_{handover_id}"):
        score = calculate_readiness(settings.database_path, handover_id)
        st.rerun()
    st.caption(score["disclaimer"])
    with st.expander("Readiness breakdown", expanded=True):
        for category in score["categories"]:
            st.progress(category["score"] / category["max"], text=f"{category['label']}: {category['score']}/{category['max']}")
        if score["missing"]:
            st.warning("Missing information: " + ", ".join(score["missing"]))
        if score["warnings"]:
            st.error("Critical warnings: " + " ".join(score["warnings"]))
        if score["recommendations"]:
            st.info("Recommendations:\n\n" + "\n".join(f"- {item}" for item in score["recommendations"]))
        if st.button("Run AI evidence review", key=f"ai_readiness_{handover_id}"):
            evidence = "\n".join(
                [handover["description"] or "", handover["notes"] or ""]
                + [doc["extracted_text"] for doc in list_documents(settings.database_path, handover_id)]
                + [row["decision_text"] for row in query(settings.database_path, "SELECT decision_text FROM decisions WHERE handover_id=?", (handover_id,))]
            )
            try:
                ai_gaps = analyze_readiness_gaps(settings.gemini_api_key, settings.gemini_model, evidence)
                st.session_state[f"ai_readiness_{handover_id}"] = ai_gaps
            except AIServiceError as exc:
                st.error(str(exc))
        ai_gaps = st.session_state.get(f"ai_readiness_{handover_id}")
        if ai_gaps:
            st.subheader("AI evidence review")
            for label, key in (("AI missing information", "missing_information"), ("AI critical warnings", "critical_warnings"), ("AI recommendations", "recommendations")):
                if ai_gaps[key]:
                    st.write(f"**{label}**")
                    for item in ai_gaps[key]:
                        st.write(f"- {item}")
    tabs = st.tabs(["Documents", "Decisions", "Tasks", "AI handover brief", "Transfer history"])
    with tabs[0]:
        for doc in list_documents(settings.database_path, handover_id):
            st.write(f"📄 **{doc['file_name']}**")
            with st.expander("Preview"):
                st.text(doc["extracted_text"][:1500])
    with tabs[1]:
        for row in query(settings.database_path, "SELECT * FROM decisions WHERE handover_id=? ORDER BY created_at DESC", (handover_id,)):
            st.info(row["decision_text"])
    with tabs[2]:
        for row in query(settings.database_path, "SELECT t.*,u.name owner_name FROM tasks t LEFT JOIN users u ON u.id=t.owner_id WHERE t.handover_id=? ORDER BY t.due_date", (handover_id,)):
            st.write(f"**{row['title']}** · {row['status']} · {row['owner_name'] or 'Unassigned'} · due {row['due_date']}")
    with tabs[3]:
        if st.button("Generate AI handover brief", key="brief"):
            context = "\n".join(d["extracted_text"] for d in list_documents(settings.database_path, handover_id))
            context += "\n" + "\n".join(str(r["title"]) for r in query(settings.database_path, "SELECT title FROM tasks WHERE handover_id=?", (handover_id,)))
            try:
                st.write(generate_handover_brief(settings.gemini_api_key, settings.gemini_model, handover["incoming_name"], handover["project_name"], context))
            except AIServiceError as exc:
                st.error(str(exc))
    with tabs[4]:
        history = query(settings.database_path, """SELECT hh.*,u.name actor_name
            FROM handover_history hh LEFT JOIN users u ON u.id=hh.actor_id
            WHERE hh.handover_id=? ORDER BY hh.created_at DESC""", (handover_id,))
        for row in history:
            st.write(f"**{row['created_at']}** · {row['actor_name'] or 'System'} · {row['event_type']} · {row['details'] or ''}")
        st.subheader("Unresolved work")
        unresolved = query(settings.database_path, """SELECT t.id,t.title,t.status,t.due_date,u.name owner_name
            FROM tasks t LEFT JOIN users u ON u.id=t.owner_id
            WHERE t.handover_id=? AND t.status NOT IN ('Completed','Cancelled') ORDER BY t.due_date""", (handover_id,))
        for task in unresolved:
            st.warning(f"Task #{task['id']} · {task['title']} · {task['owner_name'] or 'Unassigned'} · due {task['due_date']}")
