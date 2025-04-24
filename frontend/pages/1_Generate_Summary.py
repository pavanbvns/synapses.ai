# frontend/pages/1_Generate_Summary.py

import streamlit as st
import logging
import os
import time

# Import necessary functions from utils
from utils.api import create_job_record, update_job_status, call_gen_summary_endpoint
from utils.session_manager import get_user_details, is_user_registered
from utils.config_loader import load_config  # To get allowed extensions etc.

# Setup logger
logger = logging.getLogger(__name__)
# Assuming logger configured in main app or here if run standalone
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s:%(filename)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# --- Page Configuration ---
st.set_page_config(
    page_title="Generate Summary - Synapses.AI",
    layout="wide",
    initial_sidebar_state="collapsed",
)
# --- Hide Default Elements ---
# Use CSS from app.py or define necessary parts here if run standalone
st.markdown(
    """ <style> #MainMenu { visibility: hidden !important; } footer { display: none !important; } header[data-testid="stHeader"] { display: none !important; visibility: hidden !important; } [data-testid="stSidebar"] { display: none; } .block-container { padding: 1rem 0.5rem 2rem 0.5rem !important; } h1 { padding-bottom: 1rem; } </style> """,
    unsafe_allow_html=True,
)


# --- Page Content ---
st.title("✨ Generate Document Summary")

# Basic check if user is identified in session
if not is_user_registered():
    st.warning("Please log in via the main page first.")
    if st.button("Go to Home"):
        st.switch_page("app.py")
    st.stop()

# --- Load Config for File Upload ---
config = load_config()
allowed_extensions = config.get(
    "allowed_file_extensions",
    [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".tiff", ".png"],
)
allowed_types = [ext.lstrip(".") for ext in allowed_extensions]
max_size_mb = config.get("allowed_file_size_limit", 10 * 1024 * 1024) / (1024 * 1024)

# --- Initialize Page State ---
# Initialize keys specific to this page if they don't exist
page_state_defaults = {
    "summary_page_job_id": None,
    "summary_page_result": None,
    "summary_page_running": False,
    "summary_page_error": None,
    "summary_files_for_api": None,
}
for key, default_value in page_state_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# --- Layout ---
col1, col2 = st.columns([1, 1], gap="medium")  # 2 columns

# --- Inputs Column ---
with col1:
    st.subheader("Job Configuration")
    # Task Type (Display Only)
    st.text_input("Task Type", value="Generate Document Summary", disabled=True)
    # Job ID (Display Only, filled after creation)
    st.text_input(
        "Job ID",
        value=st.session_state.summary_page_job_id or "",
        disabled=True,
        key="summary_job_id_display",
    )
    # Job Name (Input) - Key matches state access later
    job_name_input = st.text_input(
        "Job Name*", placeholder="e.g., Summary of Q1 Report", key="summary_job_name"
    )
    # Job Description (Input) - Key matches state access later
    job_desc_input = st.text_area("Job Description (Optional)", key="summary_job_desc")
    # Min/Max words - Keys match state access later
    st.markdown("###### Summary Options")
    min_words_input = st.number_input(
        "Min Words",
        min_value=10,
        max_value=500,
        value=50,
        step=10,
        key="summary_min_words",
    )
    max_words_input = st.number_input(
        "Max Words",
        min_value=min_words_input + 10,
        max_value=1000,
        value=150,
        step=10,
        key="summary_max_words",
    )
    # File Uploader - Key matches state access later
    uploaded_files_input = st.file_uploader(
        "Upload Document(s)*",
        type=allowed_types,
        accept_multiple_files=True,
        key="summary_file_uploader",
        help=f"Max size: {max_size_mb:.0f}MB per file.",
    )

    # Start Job Button
    start_button_disabled = st.session_state.summary_page_running
    if st.button("Start Job", key="summary_start_job", disabled=start_button_disabled):
        # Reset result/error state before starting
        st.session_state.summary_page_job_id = None
        st.session_state.summary_page_result = None
        st.session_state.summary_page_error = None
        st.session_state.summary_files_for_api = None  # Clear previous files

        # --- Validation ---
        # Use the widget values directly (stored in session state by Streamlit via keys)
        if (
            not st.session_state.summary_job_name
            or not st.session_state.summary_job_name.strip()
        ):
            st.warning("Job Name is required.")
        elif (
            not st.session_state.summary_file_uploader
        ):  # Check uploader state directly
            st.warning("Please upload at least one document.")
        else:
            # Check file sizes and read valid files
            valid_files = True
            files_for_api = []
            try:
                for uploaded_file in st.session_state.summary_file_uploader:
                    if uploaded_file.size > (max_size_mb * 1024 * 1024):
                        st.warning(
                            f"File '{uploaded_file.name}' exceeds {max_size_mb:.0f}MB limit."
                        )
                        valid_files = False
                        break
                    else:
                        # Read file bytes for API call
                        files_for_api.append(
                            (
                                "files",
                                (
                                    uploaded_file.name,
                                    uploaded_file.getvalue(),
                                    uploaded_file.type,
                                ),
                            )
                        )
                st.session_state.summary_files_for_api = (
                    files_for_api  # Store file data for use after rerun
                )
                logger.debug(f"Stored {len(files_for_api)} files in session state.")
            except Exception as read_err:
                st.error(f"Error reading uploaded files: {read_err}")
                valid_files = False

            if valid_files:
                # --- Set running flag and trigger rerun ---
                # REMOVED the direct assignment lines like: st.session_state.summary_job_name = job_name_input
                st.session_state.summary_page_running = True
                logger.info("Validation passed, setting run flag and rerunning.")
                st.rerun()  # Rerun to show spinner and execute job logic

# --- Execution / Result Column ---
with col2:
    st.subheader("Job Status & Result")

    if st.session_state.summary_page_running:
        # This block runs AFTER the rerun caused by clicking "Start Job"
        with st.spinner("Processing... Please wait."):
            job_id = None
            try:
                # 1. Create Job Record via Backend API
                user_details = get_user_details()
                job_record_payload = {
                    # Retrieve values directly from session state using widget keys
                    "job_name": st.session_state.summary_job_name,
                    "task_type": "Generate Document Summary",
                    "description": st.session_state.summary_job_desc,
                    # "submitted_by_name": user_details.get("user_name"),
                    # "submitted_by_email": user_details.get("user_email"),
                    "user_details": user_details,
                }
                logger.debug(f"Creating job record with payload: {job_record_payload}")
                created_job_info = create_job_record(
                    job_name=job_record_payload["job_name"],
                    task_type=job_record_payload["task_type"],
                    description=job_record_payload["description"],
                    user_details=job_record_payload["user_details"],
                )

                if not created_job_info or "id" not in created_job_info:
                    raise Exception("Failed to create job record via API.")

                job_id = created_job_info["id"]
                st.session_state.summary_page_job_id = job_id  # Store returned Job ID
                logger.info(f"Created job record with ID: {job_id}")

                # 2. Call the actual Task Endpoint (/gen_summary)
                task_payload = {
                    # Retrieve min/max values directly from session state
                    "min_words": st.session_state.summary_min_words,
                    "max_words": st.session_state.summary_max_words,
                }
                # Retrieve file data stored in session state before the rerun
                files_for_api = st.session_state.get("summary_files_for_api", [])
                if not files_for_api:
                    raise Exception("File data not found in session state after rerun.")

                logger.debug(
                    f"Calling summary endpoint with payload: {task_payload} and {len(files_for_api)} files."
                )
                summary_result = call_gen_summary_endpoint(
                    payload=task_payload, files=files_for_api
                )

                if not summary_result or "summary" not in summary_result:
                    raise Exception(
                        "Summary endpoint did not return expected 'summary' field."
                    )

                st.session_state.summary_page_result = summary_result[
                    "summary"
                ]  # Store result

                # 3. Update Job Status via Backend API
                logger.debug(f"Updating job {job_id} status to Completed.")
                update_job_status(
                    job_id, "Completed", result_summary="Summary generated."
                )

                # 4. Clear running flag and temporary file data
                st.session_state.summary_page_running = False
                st.session_state.summary_files_for_api = None
                st.success("Job Completed!")
                st.rerun()  # Rerun one last time to display results correctly below

            except Exception as e:
                logger.exception(
                    f"Error during summary job processing (Job ID: {job_id}): {e}"
                )
                st.session_state.summary_page_error = f"Job failed: {str(e)}"
                if job_id:  # Try to mark as failed
                    try:
                        update_job_status(job_id, "Failed", result_summary=str(e))
                    except:
                        pass  # Ignore error during error handling
                # Clear running flag and temporary file data on error
                st.session_state.summary_page_running = False
                st.session_state.summary_files_for_api = None
                st.rerun()  # Rerun to show error message below

    # --- Display Results or Status ---
    # This runs after the processing block OR if not currently running

    # Display Error if it occurred on the last run
    if st.session_state.summary_page_error:
        st.error(st.session_state.summary_page_error)

    # Display Result if available
    if st.session_state.summary_page_result:
        st.markdown("###### Generated Summary")
        # Use the key here if needed, otherwise just display
        st.text_area(
            "Summary Output",
            value=st.session_state.summary_page_result,
            height=300,
            disabled=True,
            key="summary_result_text_area",
        )
        # Render Close button only after result is shown
        if st.button("Close", key="summary_close"):
            # Clean up page-specific state before switching
            st.session_state.summary_page_job_id = None
            st.session_state.summary_page_result = None
            st.session_state.summary_page_error = None
            st.session_state.summary_files_for_api = None
            # Switch back to the main app page
            st.switch_page("app.py")
    elif (
        not st.session_state.summary_page_running
        and not st.session_state.summary_page_error
    ):
        # Show prompt if not running and no result/error yet
        st.info("Configure job settings on the left and click 'Start Job'.")
