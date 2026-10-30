import streamlit as st
from datetime import date
from services.common import query
from services.handover_service import list_handovers
from services.readiness_service import calculate_readiness


def render(settings):
    st.title("Dashboard")
    st.caption("A living view of knowledge moving between people and teams.")
    handovers = list_handovers(settings.database_path)
    tasks = query(settings.database_path, "SELECT * FROM tasks")
    overdue = [t for t in tasks if t["due_date"] and t["due_date"] < date.today().isoformat() and t["status"] not in ("Completed", "Cancelled")]
    cols = st.columns(4)
    cols[0].metric("Total handovers", len(handovers))
    cols[1].metric("Active projects", len({h["project_name"] for h in handovers if h["status"] != "Completed"}))
    cols[2].metric("Pending tasks", sum(t["status"] not in ("Completed", "Cancelled") for t in tasks))
    cols[3].metric("Overdue tasks", len(overdue), delta="Needs attention" if overdue else "On track", delta_color="inverse")
    st.subheader("Handover readiness overview")
    if handovers:
        for handover in handovers[:6]:
            score = calculate_readiness(settings.database_path, handover["id"])["overall"]
            cols = st.columns([4, 1])
            cols[0].progress(score / 100, text=f"{handover['project_name']} · {handover['incoming_name']} · {score}/100")
            if cols[1].button("Recalculate", key=f"dash_recalc_{handover['id']}"):
                st.rerun()
    else:
        st.info("Create your first knowledge transfer to see readiness here.")
    st.subheader("Recently transferred knowledge")
    recent = query(settings.database_path, "SELECT * FROM meetings ORDER BY created_at DESC LIMIT 5")
    for row in recent:
        with st.expander(f"{row['title']} · {row['meeting_date']}"):
            st.write(row["summary"] or row["notes"] or "No summary recorded yet.")
