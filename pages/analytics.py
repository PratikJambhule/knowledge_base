import pandas as pd
import plotly.express as px
import streamlit as st
from services.common import query


def render(settings):
    st.title("Analytics")
    tasks = query(settings.database_path, "SELECT status,priority FROM tasks")
    handovers = query(settings.database_path, "SELECT project_name,readiness_score FROM handovers")
    left, right = st.columns(2)
    with left:
        st.subheader("Task completion")
        if tasks:
            frame = pd.DataFrame([dict(row) for row in tasks])
            st.plotly_chart(px.pie(frame, names="status", title="Tasks by status"), use_container_width=True)
        else:
            st.info("No task data yet.")
    with right:
        st.subheader("Handover readiness")
        if handovers:
            frame = pd.DataFrame([dict(row) for row in handovers])
            st.plotly_chart(px.bar(frame, x="project_name", y="readiness_score", range_y=[0, 100], title="Readiness score"), use_container_width=True)
        else:
            st.info("No handover data yet.")
