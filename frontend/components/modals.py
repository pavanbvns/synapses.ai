# frontend/components/modals.py

import streamlit as st
import os
import logging

logger = logging.getLogger(__name__)


# Function to safely read markdown file content
def _load_markdown(file_path: str) -> str:
    # ... (function remains the same) ...
    try:
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        full_path = os.path.join(project_root, file_path)
        if not os.path.exists(full_path):
            logger.error(f"MD file not found: {full_path}")
            return "Error: Doc file not found."
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.exception(f"Error loading MD file {file_path}: {e}")
        return f"Error loading docs: {e}"


# --- Decorated dialog function for Help ---
@st.dialog("User Guide")
def show_help_dialog():
    """Renders the User Guide content inside a decorated dialog."""
    logger.info("Executing show_help_dialog function.")
    st.info("Scroll down to view the complete guide.")
    help_content = _load_markdown("docs/USER_GUIDE.md")
    st.markdown(help_content, unsafe_allow_html=True)
    if st.button("Close Guide", key="close_help_dialog_btn_decorated"):
        # Reset flag before closing with rerun
        st.session_state["show_help_modal"] = False
        st.rerun()


# --- Decorated dialog function for Tech Docs ---
@st.dialog("Technical Overview")
def show_tech_docs_dialog():
    """Renders the Technical Overview content inside a decorated dialog."""
    logger.info("Executing show_tech_docs_dialog function.")
    st.info("Scroll down to view the complete documentation.")
    tech_content = _load_markdown("docs/TECHNICAL_OVERVIEW.md")
    st.markdown(tech_content, unsafe_allow_html=True)
    if st.button("Close Tech Docs", key="close_tech_docs_dialog_btn_decorated"):
        # Reset flag before closing with rerun
        st.session_state["show_tech_docs_modal"] = False
        st.rerun()


# --- Functions called by app.py to trigger the dialogs ---
def render_help_modal():
    """Checks session state flag and calls the decorated dialog function."""
    if st.session_state.get("show_help_modal", False):
        show_help_dialog()
        # Dialog handles its own dismissal/rerun, but reset flag just in case user dismisses manually
        # Note: Manual dismissal (Esc, click outside) does NOT trigger rerun or reset flag easily.
        # The explicit close button is more reliable.


def render_tech_docs_modal():
    """Checks session state flag and calls the decorated dialog function."""
    if st.session_state.get("show_tech_docs_modal", False):
        show_tech_docs_dialog()
        # Similar note about dismissal vs explicit close button.
