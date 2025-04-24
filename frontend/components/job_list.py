# frontend/components/job_list.py

import streamlit as st
from datetime import datetime
import logging

# uses consolidated API functions and session manager
from utils.api import fetch_jobs  # Changed import
from utils.session_manager import get_user_details

# setup logger for this component
logger = logging.getLogger(__name__)
# logger configured globally or in app.py


def render_job_list():
    """
    Fetches and renders the list of jobs for the current user using the backend API.
    Uses functions from api.py and session_manager.py for consistency.
    Provides pagination and triggers detail view via session state.
    """
    # retrieve user details from session state
    user_details = get_user_details()
    user_name = user_details.get("user_name")
    user_email = user_details.get("user_email")

    # checks if user details are available in session
    if not user_name or not user_email:
        st.warning("User details not found in session. Cannot fetch jobs.")
        logger.warning("Attempted to render job list without user details in session.")
        return

    # fetches jobs using the centralized API function
    # fetch_jobs handles errors internally, returning [] on failure
    logger.info(f"Fetching jobs for user: {user_name} ({user_email})")
    jobs = fetch_jobs(user_name=user_name, user_email=user_email)  # Use fetch_jobs

    # displays message if no jobs found or fetch failed
    if not jobs:
        # Message changed slightly from uploaded version for clarity
        st.info("No recent jobs found for your account.")
        # fetch_jobs logs warnings/errors internally
        return

    # sorts jobs by start time (newest first), handling potential missing values
    try:
        # Use a default old date for sorting robustness if start_time is missing
        jobs = sorted(
            jobs, key=lambda x: x.get("start_time", "1970-01-01T00:00:00"), reverse=True
        )
    except Exception as e:
        logger.error(f"Error sorting jobs: {e}")
        st.warning("Could not sort job list.")

    # --- Pagination Logic ---
    jobs_per_page = 5  # configure items per page
    total_jobs = len(jobs)
    total_pages = (total_jobs + jobs_per_page - 1) // jobs_per_page
    if total_pages <= 0:
        total_pages = 1  # ensure at least one page

    # gets/validates current page number from session state
    current_page = st.session_state.get("current_job_page", 1)
    current_page = max(1, min(current_page, total_pages))  # clamp page number
    st.session_state["current_job_page"] = current_page

    # calculates start/end indices for slicing the job list
    start_idx = (current_page - 1) * jobs_per_page
    end_idx = start_idx + jobs_per_page
    paginated_jobs = jobs[start_idx:end_idx]

    # --- Pagination Controls (only show if multiple pages) ---
    if total_pages > 1:
        # Uses 5 columns for better button placement
        nav_cols = st.columns([1, 1, 5, 1, 1])
        with nav_cols[0]:
            # previous page button
            if st.button("⬅️ Prev", key="prev_job_page", disabled=(current_page <= 1)):
                st.session_state["current_job_page"] -= 1
                st.rerun()
        with nav_cols[4]:
            # next page button
            if st.button(
                "Next ➡️", key="next_job_page", disabled=(current_page >= total_pages)
            ):
                st.session_state["current_job_page"] += 1
                st.rerun()
        with nav_cols[2]:
            # page number display
            st.markdown(
                f"<div style='text-align: center; margin-top: 5px;'>Page {current_page} of {total_pages}</div>",
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)  # adds vertical space

    # --- Display Paginated Jobs ---
    if not paginated_jobs:
        st.info("No jobs to display on this page.")
        return

    # iterates through the jobs for the current page
    for job in paginated_jobs:
        job_id = job.get("id")  # Use .get for safety
        job_name = job.get("job_name", "Unnamed Job")
        job_status = job.get("status", "Unknown")
        job_start = job.get("start_time", None)

        # safely formats start time
        formatted_start = "N/A"
        if job_start:
            try:
                formatted_start = datetime.fromisoformat(job_start).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except (ValueError, TypeError):
                formatted_start = str(job_start)

        # uses expander to show job summary, details revealed on click
        # Removed brain emoji to adhere to standards [cite: 1]
        expander_title = f"{job_name} (ID: {job_id}) - Status: {job_status} - Started: {formatted_start}"
        with st.expander(expander_title):
            # displays basic details within the expander
            st.markdown(f"**Job ID:** `{job_id}`")
            st.markdown(f"**Task Type:** {job.get('task_type', 'N/A')}")
            st.markdown(f"**Status:** {job_status}")
            st.markdown(f"**Submitted:** {formatted_start}")
            end_time = job.get("end_time")
            formatted_end = (
                "In Progress"
                if job_status not in ["Completed", "Aborted", "Failed"]
                else "-"
            )  # Added Failed status
            if end_time:
                try:
                    formatted_end = datetime.fromisoformat(end_time).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except (ValueError, TypeError):
                    formatted_end = str(end_time)
            st.markdown(f"**Completed:** {formatted_end}")
            st.markdown(f"**Description:** {job.get('description', '-')}")

            # Changed button text for clarity
            if st.button(
                "View Full Results",
                key=f"detail_{job_id}",
                help="Go to the detailed view for this job",
            ):
                if job_id:
                    st.session_state["selected_job_id"] = job_id
                    st.rerun()  # triggers app.py to render the detail view
                else:
                    st.warning("Job ID is missing, cannot view details.")
