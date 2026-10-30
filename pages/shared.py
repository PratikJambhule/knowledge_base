import streamlit as st

from services.common import query


def users(settings):
    return query(settings.database_path, "SELECT * FROM users WHERE is_active=1 ORDER BY name")


def handover_options(settings):
    return query(settings.database_path, "SELECT id,project_name,title FROM handovers ORDER BY updated_at DESC")


def user_selectbox(rows, label, key):
    options = {row["name"]: row["id"] for row in rows}
    choice = st.selectbox(label, list(options), key=key)
    return options[choice]
