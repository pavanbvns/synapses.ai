# frontend/app.py

import streamlit as st
import logging
import os
import time

# --- Core App Components ---
from components.header import render_header

# Ensure correct import based on @st.dialog decorator pattern
from components.job_modal import job_creation_dialog
from components.job_list import render_job_list
from components.job_detail import render_job_detail

# Ensure modals.py uses the @st.dialog decorator pattern
from components.modals import render_help_modal, render_tech_docs_modal

# --- Utilities ---
from utils.session_manager import (
    initialize_session_state,
    render_lookup_or_registration,
    get_user_details,
    is_user_registered,
)
from utils.config_loader import load_config

# --- Logger Setup ---
logger = logging.getLogger(__name__)
# ... (logger setup remains the same) ...
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s:%(filename)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# --- Page Configuration ---
# Removing hide_deploy_button=True as it caused issues before.
# We will hide using CSS instead.
st.set_page_config(
    page_title="Synapses.AI",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Global Styles & Hide Default Elements ---
st.markdown(
    """
    <style>
      /* Hide default Streamlit elements */
      #MainMenu { visibility: hidden !important; }
      footer { display: none !important; } /* Hide default footer */
      /* Hide the specific Streamlit header bar using data-testid */
      header[data-testid="stHeader"] {
          display: none !important;
          visibility: hidden !important;
      }

      /* Adjust padding */
      .block-container {
          padding: 1rem 0.5rem 2rem 0.5rem !important;
      }
      /* Style for the greeting card */
      .greeting-card {
          background-color: #f0f4f8; border: 1px solid #d0d7de; border-radius: 8px;
          padding: 1.5rem; height: 100%;
          display: flex; flex-direction: column; justify-content: center;
          min-height: 280px; /* Adjust as needed */
      }
      .greeting-content { flex-grow: 1; display: flex; flex-direction: column; justify-content: center;}

       /* Style for Quick Link buttons */
      .stButton>button {
          width: 100%; min-height: 65px; padding: 8px 5px; font-size: 0.9rem;
          font-weight: 500; border-radius: 6px; border: 1px solid #d0d7de;
          background-color: #f8f9fa; color: #004080; display: flex; align-items: center;
          justify-content: center; text-align: center; line-height: 1.3;
          margin-bottom: 8px; word-wrap: break-word; white-space: normal;
      }
      .stButton>button:hover { border-color: #004080; background-color: #e9ecef; color: #003366;}

      /* Style for Quick Links title */
      h5.quick-links-title { color: #004080; font-weight: 600; text-align: center; margin-bottom: 15px; margin-top: 5px;}
      /* Style for nested column labels */
      h6.quick-start-header { color: #004080; font-weight: 600; margin-bottom: 10px; margin-top: 0; text-align: left; font-size: 0.9rem;}

      /* Footer Styling (Attempt to push down if main content is short) */
       /* This often requires the parent (.stApp) to be flex-column with min-height 100vh */
       /* Applying to .stApp directly via CSS is difficult/unreliable */
       /* The structure should naturally push it down if Job Management renders */
       div.custom-footer {
           text-align: center;
           padding: 15px 0px 5px 0px; /* Add padding top/bottom */
           font-size: 0.8em;
           color: #586069;
           width: 100%;
           /* margin-top: auto; /* This might work if parent has flex properties */
       }

    </style>
    """,
    unsafe_allow_html=True,
)

# --- Initialize Session State and Load Config ---
initialize_session_state()
config_data = load_config()

# --- Handle Modal Query Parameters *BEFORE* Registration Check ---
# ... (Query parameter handling logic remains the same) ...
query_params = st.query_params.to_dict()
modal_requested = False
if "show_help" in query_params:
    if not st.session_state.get("show_help_modal", False):
        st.session_state.show_help_modal = True
        modal_requested = True
if "show_tech_docs" in query_params:
    if not st.session_state.get("show_tech_docs_modal", False):
        st.session_state.show_tech_docs_modal = True
        modal_requested = True
if modal_requested:
    st.query_params.clear()
    st.rerun()

# --- Handle User Lookup / Registration ---
# ... (User lookup/registration logic remains the same) ...
lookup_or_reg_form_rendered = False
if not is_user_registered():
    if not st.session_state.get("show_help_modal", False) and not st.session_state.get(
        "show_tech_docs_modal", False
    ):
        lookup_or_reg_form_rendered = render_lookup_or_registration()
        if lookup_or_reg_form_rendered:
            st.stop()

# --- Main App UI ---
user_details = get_user_details()
user_name = user_details.get("user_name") or "Guest"
if is_user_registered():
    logger.info(f"Rendering main UI for user: {user_name}")
else:
    logger.info("Rendering UI (modal active or user not identified).")

# --- Handle 'new_job' Query Parameter ---
# ... (New job query param handling remains the same, calls job_creation_dialog) ...
if "new_job" in query_params:
    st.session_state["selected_task_for_modal"] = None
    st.query_params.clear()
    logger.debug("Activating job creation dialog via query parameter.")
    job_creation_dialog()

# --- Render UI Components ---
render_header()  # Renders custom header

# --- Render Dashboard Area ---
# Uses 2 main columns, ratio adjusted previously
main_col1, main_col2 = st.columns([1, 2.5], gap="medium")
with main_col1:  # Greeting Card
    greeting = "Welcome"
    st.markdown(
        f"""<div class="greeting-card"><div class="greeting-content"><h4 style="margin: 0; color: #0e4d92; font-weight: 600;">{greeting},<br>{user_name}</h4><p style="margin-top: 8px; color: #586069; font-size: 0.9em;">Select a task to start.</p></div></div>""",
        unsafe_allow_html=True,
    )
with main_col2:  # Quick Links Container
    # Re-added the container with border=True
    with st.container(border=True):
        st.markdown(
            "<h5 class='quick-links-title'>Quick Links</h5>", unsafe_allow_html=True
        )
        # Creates the 4 nested columns for buttons INSIDE the container
        nested_col_doc, nested_col_kb, nested_col_legal, nested_col_podcast = (
            st.columns(4, gap="small")
        )
        # Task definitions
        doc_tasks = [
            "Generate Document Summary",
            "Chat with Documents",
            "Ask Questions on Documents",
        ]
        kb_tasks = ["Ingest Documents into Knowledge Base", "Chat with Knowledge Base"]
        legal_tasks = ["Find Obligations in Document", "Find Risks in Document"]
        podcast_tasks = [
            "Generate monologue audio podcast",
            "Generate dialogue audio podcast",
        ]
        # --- Corrected Button Loops ---
        with nested_col_doc:
            st.markdown(
                "<h6 class='quick-start-header'>Document based</h6>",
                unsafe_allow_html=True,
            )
            for task in doc_tasks:
                button_key = f"quick_start_doc_{task.lower().replace(' ', '_')}"
                if st.button(task, key=button_key, help=f"Start job: {task}"):
                    if task == "Generate Document Summary":
                        # Navigate to the dedicated page
                        st.switch_page("pages/1_Generate_Summary.py")
                    else:
                        # Keep existing logic for other buttons (trigger dialog)
                        st.session_state["selected_task_for_modal"] = task
                        logger.info(f"Button clicked: {task}")
                        job_creation_dialog()  # Calls decorated dialog
        with nested_col_kb:
            st.markdown(
                "<h6 class='quick-start-header'>Knowledge Base based</h6>",
                unsafe_allow_html=True,
            )
            for task in kb_tasks:
                button_key = f"quick_start_kb_{task.lower().replace(' ', '_')}"  # Use unique prefixes for keys
                if st.button(task, key=button_key, help=f"Start job: {task}"):
                    st.session_state["selected_task_for_modal"] = task
                    logger.info(f"Button clicked: {task}")
                    job_creation_dialog()
        with nested_col_legal:
            st.markdown(
                "<h6 class='quick-start-header'>Legal</h6>", unsafe_allow_html=True
            )
            for task in legal_tasks:
                button_key = f"quick_start_legal_{task.lower().replace(' ', '_')}"  # Use unique prefixes for keys
                if st.button(task, key=button_key, help=f"Start job: {task}"):
                    st.session_state["selected_task_for_modal"] = task
                    logger.info(f"Button clicked: {task}")
                    job_creation_dialog()
        with nested_col_podcast:
            st.markdown(
                "<h6 class='quick-start-header'>Podcast</h6>", unsafe_allow_html=True
            )
            for task in podcast_tasks:
                button_key = f"quick_start_podcast_{task.lower().replace(' ', '_')}"  # Use unique prefixes for keys
                if st.button(task, key=button_key, help=f"Start job: {task}"):
                    st.session_state["selected_task_for_modal"] = task
                    logger.info(f"Button clicked: {task}")
                    job_creation_dialog()

# --- Render Modals/Dialogs ---
# Help/Tech Docs triggered by query params handled above
render_help_modal()  # Checks flag internally and calls decorated function
render_tech_docs_modal()  # Checks flag internally and calls decorated function
# Job creation dialog is triggered directly by button calls above

# --- Main Content Area (Job List or Job Detail) ---
# Wrap this section in a container to potentially help footer positioning
# Using a flag to ensure it only renders when appropriate
should_render_main_content = (
    is_user_registered()
    and not st.session_state.get("show_help_modal", False)
    and not st.session_state.get("show_tech_docs_modal", False)
    # We don't need to check show_job_modal as dialogs are overlays
)

if should_render_main_content:
    with st.container():  # Contains the job management section
        st.markdown("---")
        st.subheader("Job Management")
        selected_job_id = st.session_state.get("selected_job_id")
        if selected_job_id:
            render_job_detail(selected_job_id)
            if st.button("⬅️ Back to Job List", key="back_to_list"):
                st.session_state.selected_job_id = None
                st.rerun()
        else:
            try:
                render_job_list()
            except Exception as e:
                logger.exception("Error rendering job list.")
                st.error(f"Error displaying job list: {e}")
                st.warning("Ensure backend is running.")
else:
    # Optionally add a placeholder or spacer if nothing is rendered to help push footer
    st.markdown(
        "<div style='min-height: 300px;'></div>", unsafe_allow_html=True
    )  # Placeholder height


# --- Footer ---
# Renders the custom footer using markdown
st.markdown("---")  # Divider before footer
footer_html = """<div class="custom-footer">Synapses.AI Platform developed by Pavan Kumar B V N S (pbondala@opentext.com) for internal demonstration purposes.</div>"""
st.markdown(footer_html, unsafe_allow_html=True)
