import streamlit as st

from config.settings import get_settings
from database.connection import initialize_database
from pages import (
    ai_assistant,
    analytics,
    create_transfer,
    dashboard,
    knowledge_base,
    task_management,
    transfer_details,
    meetings,
)
from utils.logging_config import configure_logging


st.set_page_config(
    page_title="KnowledgeBridge AI",
    page_icon="🌉",
    layout="wide",
    initial_sidebar_state="expanded",
)

settings = get_settings()
configure_logging(settings.log_path)
initialize_database(settings.database_path)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; }
    [data-testid="stMetric"] { border: 1px solid #e8edf5; padding: 1rem; border-radius: .75rem; }
    .kb-muted { color: #64748b; font-size: .9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("🌉 KnowledgeBridge")
    st.caption("Person-to-person knowledge transfer")
    page = st.radio(
        "Navigate",
        [
            "Dashboard",
            "Create Knowledge Transfer",
            "Knowledge Transfer Details",
            "Task Management",
            "Meetings",
            "Knowledge Base",
            "AI Assistant",
            "Analytics",
        ],
    )
    st.divider()
    st.caption("AI outputs are suggestions. Review before saving.")

if page == "Dashboard":
    dashboard.render(settings)
elif page == "Create Knowledge Transfer":
    create_transfer.render(settings)
elif page == "Knowledge Transfer Details":
    transfer_details.render(settings)
elif page == "Task Management":
    task_management.render(settings)
elif page == "Meetings":
    meetings.render(settings)
elif page == "Knowledge Base":
    knowledge_base.render(settings)
elif page == "AI Assistant":
    ai_assistant.render(settings)
else:
    analytics.render(settings)
