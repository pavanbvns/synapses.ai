# frontend/components/job_history.py

import streamlit as st
import requests


def render_job_history():
    """
    Fetch and display paginated job history for the current user.
    """
    st.markdown("### 📜 Your Job History")

    # Retrieve user info from session state
    user_info = st.session_state.get("user_info", {})
    if not user_info:
        st.warning("User identity not found. Please refresh and provide your details.")
        return

    # Fetch job history from backend
    try:
        base_url = st.session_state.get("backend_base_url", "")
        response = requests.get(f"{base_url}/jobs", timeout=10)
        response.raise_for_status()
        job_list = response.json().get("jobs", [])
    except Exception as e:
        st.error(f"Failed to fetch job history: {e}")
        return

    # Filter jobs for current user
    name, email = user_info.get("name"), user_info.get("email")
    jobs = [
        job
        for job in job_list
        if job.get("submitted_by_name") == name
        and job.get("submitted_by_email") == email
    ]

    if not jobs:
        st.info("No past jobs found.")
        return

    # Pagination logic
    jobs_per_page = 5
    total_pages = (len(jobs) - 1) // jobs_per_page + 1
    current_page = st.session_state.get("job_history_page", 1)

    col1, col2, col3 = st.columns([1, 4, 1])
    with col1:
        if st.button("⬅️", disabled=current_page == 1):
            st.session_state.job_history_page = current_page - 1
    with col3:
        if st.button("➡️", disabled=current_page == total_pages):
            st.session_state.job_history_page = current_page + 1

    st.markdown(f"Page **{current_page}** of **{total_pages}**")

    start = (current_page - 1) * jobs_per_page
    end = start + jobs_per_page
    for job in jobs[start:end]:
        with st.expander(f"📌 {job['job_name']} (ID: {job['id']})"):
            st.markdown(f"**Type**: {job.get('job_type', 'N/A')}")
            st.markdown(f"**Status**: {job['status']}")
            st.markdown(f"**Start**: {job['start_time']}")
            st.markdown(f"**End**: {job.get('end_time', 'In Progress')}")
            st.markdown(f"**Description**: {job.get('description', '-')}")
