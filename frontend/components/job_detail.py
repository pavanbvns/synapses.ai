# frontend/components/job_detail.py

import streamlit as st

# import requests # No longer needed
import logging
import json  # Keep for parsing obligations/risks if returned as JSON strings

# use consolidated API functions
from utils.api import (
    fetch_job_details,  # Assumes this fetches basic metadata
    fetch_job_summary_result,
    fetch_job_qa_result,
    fetch_job_obligations_result,
    fetch_job_risks_result,
    fetch_job_ingest_result,
    # Add imports for other result types if needed
)

# uses utility for rendering previews/results
from utils.render_utils import render_file_preview, render_response_content

# setup logger
logger = logging.getLogger(__name__)
# logger configured globally or in app.py


def render_job_detail(job_id: int):
    """
    Fetches and renders detailed view of a selected job using its ID.
    Fetches basic metadata first, then fetches specific task results via API helpers.
    """
    if not job_id:
        st.error("Invalid Job ID provided for detail view.")
        return

    logger.info(f"Rendering details for job ID: {job_id}")

    # --- Fetch Basic Job Metadata ---
    # assumes a /jobs/{job_id} endpoint exists and is handled by fetch_job_details
    job_metadata = fetch_job_details(job_id)

    if not job_metadata:
        st.error(f"Could not retrieve details for Job ID: {job_id}.")
        # Button to go back might be placed in app.py which calls this
        return

    # --- Display Metadata ---
    st.subheader(f"Job Details: {job_metadata.get('job_name', 'N/A')}")
    # Use st.columns for better layout of metadata
    meta1, meta2 = st.columns(2)
    with meta1:
        st.markdown(f"**Job ID:** `{job_id}`")
        st.markdown(f"**Status:** `{job_metadata.get('status', 'Unknown')}`")
        st.markdown(f"**Task Type:** `{job_metadata.get('task_type', 'N/A')}`")
    with meta2:
        st.markdown(f"**Started At:** `{job_metadata.get('start_time', 'N/A')}`")
        st.markdown(f"**Ended At:** `{job_metadata.get('end_time', '-')}`")
        st.markdown(
            f"**Submitted By:** `{job_metadata.get('submitted_by_name', '-')} ({job_metadata.get('submitted_by_email', '-')})`"
        )

    st.markdown(f"**Description:** {job_metadata.get('description', '-')}")
    st.divider()

    # --- Display Uploaded Files (Placeholder) ---
    # Note: Fetching actual file previews might require more complex backend setup
    # Currently shows placeholder based on metadata if available
    st.markdown("#### Uploaded Files")
    uploaded_files_meta = job_metadata.get(
        "uploaded_files", []
    )  # Assuming backend includes this
    if uploaded_files_meta:
        # Simple list for now
        for file_meta in uploaded_files_meta:
            st.markdown(f"- {file_meta.get('filename', 'Unnamed File')}")
            # Placeholder for preview functionality
            # render_file_preview("Preview not available", filename=file_meta.get('filename'))
    else:
        st.info("No file information associated with this job.")
    st.divider()

    # --- Display Task-Specific Output ---
    st.markdown("#### Task Output")
    task_type = job_metadata.get("task_type")
    api_response_data = None  # Variable to hold fetched result data

    try:
        if not task_type:
            st.warning("Task type unknown, cannot display specific results.")
        elif task_type == "Generate Document Summary":
            api_response_data = fetch_job_summary_result(job_id)
            if api_response_data:
                render_response_content(
                    api_response_data.get("summary", "No summary found.")
                )
        elif task_type == "Ask Questions on Documents":
            api_response_data = fetch_job_qa_result(job_id)
            if api_response_data:
                qa_pairs = api_response_data.get("qa_pairs", [])
                if qa_pairs:
                    for pair in qa_pairs:
                        st.markdown(f"**Q:** {pair.get('question', '?')}")
                        st.markdown(f"**A:** {pair.get('answer', '-')}")
                        st.markdown("---")
                else:
                    st.info("No Q&A pairs found.")
        elif task_type == "Chat with Documents":
            # Requires dedicated UI, maybe store/fetch history differently
            st.info("Chat history display is not yet implemented.")
        elif task_type == "Find Obligations in Document":
            api_response_data = fetch_job_obligations_result(job_id)
            if api_response_data:
                try:
                    # Assuming backend returns obligations as a JSON string field named 'obligations'
                    obligations = json.loads(api_response_data.get("obligations", "[]"))
                    if obligations:
                        for item in obligations:
                            for k, v in item.items():
                                st.markdown(f"- **{k}**: {v}")
                            st.markdown("---")
                    else:
                        st.info("No obligations extracted.")
                except json.JSONDecodeError:
                    st.error("Could not parse obligations data.")
                    st.text(
                        api_response_data.get("obligations", "")
                    )  # Show raw data on error
                except Exception as parse_e:
                    st.error(f"Error displaying obligations: {parse_e}")
        elif task_type == "Find Risks in Document":
            api_response_data = fetch_job_risks_result(job_id)
            # Similar parsing and display logic as obligations
            if api_response_data:
                try:
                    risks = json.loads(api_response_data.get("risks", "[]"))
                    if risks:
                        for item in risks:
                            for k, v in item.items():
                                st.markdown(f"- **{k}**: {v}")
                            st.markdown("---")
                    else:
                        st.info("No risks extracted.")
                except json.JSONDecodeError:
                    st.error("Could not parse risks data.")
                    st.text(api_response_data.get("risks", ""))
                except Exception as parse_e:
                    st.error(f"Error displaying risks: {parse_e}")
        elif task_type == "Ingest Documents into Knowledge Base":
            api_response_data = fetch_job_ingest_result(job_id)
            if api_response_data:
                st.success(
                    f"Documents Ingested: {api_response_data.get('ingested_count', 0)}"
                )
                st.json(api_response_data.get("details", {}))  # Display details as JSON
        # Add cases for Podcast tasks here if applicable
        # elif task_type == "Generate monologue audio podcast": ...
        # elif task_type == "Generate dialogue audio podcast": ...
        else:
            st.warning("Output rendering not implemented for this task type.")

        # Handle cases where fetching the specific result failed (api_response_data is None)
        if task_type and api_response_data is None:
            # Error/warning is already displayed by the API function call
            logger.warning(
                f"Fetching specific result for task '{task_type}' failed for job {job_id}."
            )

    except Exception as ex:
        st.error(f"An error occurred while displaying job output: {str(ex)}")
        logger.exception(f"Error rendering output for job {job_id}: {ex}")

    # Back button handled in app.py
