# frontend/components/job_modal.py

import streamlit as st
import logging
import json

# uses consolidated API function and user details getter
from utils.api import create_job
from utils.session_manager import get_user_details

# setup logger
logger = logging.getLogger(__name__)

# Define constants
ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".tiff", ".png"]
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Define available tasks (TODO: Move to config)
AVAILABLE_TASKS = [
    "Generate Document Summary",
    "Ask Questions on Documents",
    "Chat with Documents",
    "Ingest Documents into Knowledge Base",
    "Find Obligations in Document",
    "Find Risks in Document",
    "Generate monologue audio podcast",
    "Generate dialogue audio podcast",
]

# Maps tasks to backend endpoints (TODO: Verify paths)
ENDPOINT_MAP = {
    "Generate Document Summary": "gen_summary",
    "Ask Questions on Documents": "qna_on_docs/qna_on_docs",
    "Chat with Documents": "chat_with_docs",
    "Ingest Documents into Knowledge Base": "ingest",
    "Find Obligations in Document": "find_obligations",
    "Find Risks in Document": "find_risks",
    "Generate monologue audio podcast": "gen_mono_podcast",
    "Generate dialogue audio podcast": "gen_dialog_podcast",
}


# --- This function IS the dialog, decorated with @st.dialog ---
@st.dialog("Create & Start New AI Job")  # Apply decorator with the dialog title
def job_creation_dialog():  # Function name can be descriptive
    """
    Renders the job creation dialog using @st.dialog decorator.
    Handles form input, validation, task pre-selection, and job submission.
    """
    logger.info("Executing job_creation_dialog function (decorated with @st.dialog).")
    # --- Get Pre-selected Task ---
    # Reads task from session state, set by the Quick Link buttons in app.py
    selected_task = st.session_state.get("selected_task_for_modal", AVAILABLE_TASKS[0])
    default_task_index = 0
    if selected_task and selected_task in AVAILABLE_TASKS:
        try:
            default_task_index = AVAILABLE_TASKS.index(selected_task)
        except ValueError:
            logger.warning(f"Task '{selected_task}' not valid.")
            selected_task = AVAILABLE_TASKS[0]

    # --- Job Form ---
    # Elements defined here will appear inside the decorated dialog
    st.markdown("### Job Configuration")
    # Use a unique form key
    with st.form("new_job_form_decorated_dialog", clear_on_submit=True):
        job_name = st.text_input(
            "Job Name*", placeholder="e.g., Summarize Report Q4", max_chars=100
        )
        job_description = st.text_area(
            "Job Description (Optional)", placeholder="Brief description...", height=80
        )
        # Set the index based on pre-selected task
        task_type = st.selectbox(
            "Select AI Task*",
            options=AVAILABLE_TASKS,
            index=default_task_index,
            key="decorated_dialog_task_select",
        )
        uploaded_files = st.file_uploader(
            "Upload Document(s)*",
            type=[ext.lstrip(".") for ext in ALLOWED_EXTENSIONS],
            accept_multiple_files=True,
            key="decorated_dialog_file_uploader",
            help=f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}. Max size: {MAX_FILE_SIZE_MB}MB.",
        )

        # --- Task-Specific Inputs ---
        questions_data = None
        chat_query = None
        if task_type == "Ask Questions on Documents":
            st.markdown("##### Questions to Ask")
            questions = []
            for i in range(3):
                q = st.text_input(f"Question {i + 1}", key=f"decorated_dialog_q_{i}")
            if q and q.strip():
                questions.append(q.strip())
            if questions:
                qna_items = [
                    {"question": q, "response_type": "specific"} for q in questions
                ]
                questions_data = json.dumps(qna_items)
        elif task_type == "Chat with Documents":
            st.markdown("##### Start Conversation")
            chat_query = st.text_input(
                "Your initial message*", key="decorated_dialog_chat_query"
            )

        # --- Form Submission Button ---
        submitted = st.form_submit_button("Create and Start Job")
        if submitted:
            logger.info(f"Decorated dialog job form submitted for task: {task_type}")
            # --- Validation ---
            validation_passed = True
            if not job_name or not job_name.strip():
                st.warning("Job Name required.")
                validation_passed = False
            if task_type != "Chat with Knowledge Base" and not uploaded_files:
                st.warning("Upload document(s).")
                validation_passed = False
            elif uploaded_files:
                for up_file in uploaded_files:
                    if up_file.size > MAX_FILE_SIZE_BYTES:
                        st.warning(f"File '{up_file.name}' > {MAX_FILE_SIZE_MB}MB.")
                        validation_passed = False
                        break
            if task_type == "Ask Questions on Documents" and not questions_data:
                st.warning("Enter question(s).")
                validation_passed = False
            if task_type == "Chat with Documents" and (
                not chat_query or not chat_query.strip()
            ):
                st.warning("Enter initial message.")
                validation_passed = False

            # --- API Call ---
            if validation_passed:
                logger.info("Decorated dialog form validation passed.")
                user_details = get_user_details()
                payload = {
                    "job_name": job_name.strip(),
                    "description": job_description.strip(),
                    "submitted_by_name": user_details.get("user_name", ""),
                    "submitted_by_email": user_details.get("user_email", ""),
                }
                if task_type == "Ask Questions on Documents":
                    payload["qna_items_str"] = questions_data
                elif task_type == "Chat with Documents":
                    payload["new_message"] = chat_query.strip()
                elif task_type == "Generate Document Summary":
                    payload["min_words"], payload["max_words"] = 50, 150
                files_data = (
                    [("files", (f.name, f.getvalue(), f.type)) for f in uploaded_files]
                    if uploaded_files
                    else []
                )
                endpoint_path = ENDPOINT_MAP.get(task_type)
                if not endpoint_path:
                    st.error(f"Config Error: No endpoint for task '{task_type}'.")
                    logger.error(f"Endpoint missing: {task_type}")
                else:
                    try:
                        with st.spinner(f"Submitting job '{job_name}'..."):
                            api_response = create_job(
                                job_payload=payload,
                                endpoint=endpoint_path,
                                files=files_data,
                            )
                        st.session_state.last_job_result = api_response
                        st.success(f"Job '{job_name}' submitted!")
                        logger.info(
                            f"Job submitted via decorated dialog. Response: {api_response}"
                        )
                        st.session_state["selected_task_for_modal"] = None
                        # Close dialog programmatically on success using rerun inside the dialog function
                        st.rerun()
                    except Exception as e:
                        logger.error(
                            f"Job submission failed from decorated dialog: {e}"
                        )  # Keep dialog open on error
            else:
                logger.warning("Decorated dialog form validation failed.")

    # The dialog handles its own dismissal (X, Esc, click outside).
    # A 'Cancel' button could be added here inside the function if explicit cancel is needed.
    # if st.button("Cancel"):
    #    st.rerun() # Closes the dialog
