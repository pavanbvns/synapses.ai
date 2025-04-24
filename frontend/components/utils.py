# frontend/components/utils.py

import streamlit as st
import re


def validate_name(name: str) -> bool:
    """
    Validate name is non-empty and not a default/test string.
    """
    if not name.strip():
        return False
    if re.search(r"test", name, re.IGNORECASE):
        return False
    return True


def validate_email(email: str) -> bool:
    """
    Basic email format validation.
    """
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(pattern, email))


def reset_job_modal_state():
    """
    Reset modal-related session state entries.
    """
    for key in [
        "job_name",
        "job_description",
        "selected_task",
        "uploaded_files",
        "qa_questions",
        "chat_messages",
    ]:
        st.session_state.pop(key, None)


def init_user_identity():
    """
    Prompt for and store user name and email if not already stored.
    """
    if "user_name" not in st.session_state or "user_email" not in st.session_state:
        with st.form("identity_form", clear_on_submit=False):
            st.markdown("### Welcome to Synapses.AI")
            name = st.text_input("Full Name", "")
            email = st.text_input("Email Address", "")
            submit = st.form_submit_button("Enter")

            if submit:
                if not validate_name(name):
                    if st.session_state.get("name_retry", False):
                        st.session_state["user_name"] = name.strip()
                    else:
                        st.warning("Please provide a proper name.")
                        st.session_state["name_retry"] = True
                        return
                elif not validate_email(email):
                    st.warning("Please enter a valid email address.")
                    return
                else:
                    st.session_state["user_name"] = name.strip()
                    st.session_state["user_email"] = email.strip()
                    st.success(f"Welcome, {name}!")
                    st.rerun()


def load_app_config():
    """
    Load and persist the backend config from config.yml.
    This should be executed once on startup.
    """
    import yaml
    import os

    if "config" not in st.session_state:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        config_path = os.path.join(base_dir, "config.yml")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
                st.session_state["config"] = data or {}
        else:
            st.session_state["config"] = {}
