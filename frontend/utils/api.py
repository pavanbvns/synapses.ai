# frontend/utils/api.py

import requests
import logging
import streamlit as st
import os

# importing the specific function for getting config values safely
from .config_loader import get_config_value

# Setup logger for API utility functions
logger = logging.getLogger(__name__)
log_level_str = os.environ.get("LOG_LEVEL", "INFO")
log_level = getattr(logging, log_level_str.upper(), logging.INFO)
logger.setLevel(log_level)

# to prevent duplicate log handlers during development reloads
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s:%(filename)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def get_backend_base_url() -> str:
    """
    Retrieves the backend base URL from configuration using the safe getter.
    Provides a fallback default URL if the configuration key is missing.
    """
    # using the safe getter function from config_loader for reliability
    return get_config_value("backend_base_url", "http://127.0.0.1:8000")


# --- Generic Job API Functions ---


def create_job(job_payload: dict, endpoint: str, files: list = None):
    """
    Submits a new job creation request to a specified backend API endpoint.
    Handles multipart form data if files are provided.
    """
    base_url = get_backend_base_url()
    url = f"{base_url}/{endpoint.strip('/')}"
    logger.info(f"Attempting to submit job via POST to: {url}")
    logger.debug(f"Job Payload (data): {job_payload}")
    logger.debug(f"Number of files attached: {len(files) if files else 0}")

    try:
        response = requests.post(url, data=job_payload, files=files, timeout=600)
        response.raise_for_status()
        logger.info(
            f"Job submission successful to {url}. Status: {response.status_code}"
        )
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"Timeout occurred (600s limit) while submitting job to {url}")
        st.error(
            "The request timed out. The backend task might be taking longer than expected or is unresponsive."
        )
        raise
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error attempting to reach backend at {url}.")
        st.error("Connection Error: Could not connect to the backend server.")
        raise
    except requests.exceptions.RequestException as e:
        logger.exception(f"Request failed during job submission to {url}: {e}")
        error_detail = str(e)
        if e.response is not None:
            try:
                error_detail = e.response.json().get("detail", e.response.text)
            except Exception:
                error_detail = e.response.text if e.response.text else str(e)
        st.error(f"Job Submission Error: {error_detail}")
        raise
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred during job submission to {url}: {e}"
        )
        st.error(f"An unexpected system error occurred: {e}")
        raise


def fetch_jobs(user_name: str = None, user_email: str = None) -> list:
    """
    Fetches the job history list from the backend '/jobs' endpoint.
    Allows optional filtering by user name and email via query parameters.
    """
    base_url = get_backend_base_url()
    url = f"{base_url}/jobs"
    params = {}
    if user_name:
        params["user_name"] = user_name
    if user_email:
        params["user_email"] = user_email

    logger.info(f"Fetching jobs from: {url} with parameters: {params}")

    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs", [])
        logger.info(f"Successfully fetched {len(jobs)} jobs matching criteria.")
        return jobs
    except requests.exceptions.Timeout:
        logger.error(f"Timeout occurred while fetching jobs from {url}")
        st.warning("Request timed out while fetching job history.")
        return []
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error while fetching jobs from {url}.")
        st.warning("Could not connect to the backend to fetch job history.")
        return []
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to fetch job history from {url}: {e}")
        st.warning(f"Failed to retrieve job history: {e}")
        return []
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred during job fetch from {url}: {e}"
        )
        st.error(f"An unexpected error occurred while fetching jobs: {e}")
        return []


def fetch_job_details(job_id: int):
    """
    Fetches detailed information for a single job specified by its ID.
    Assumes a backend endpoint like '/jobs/{job_id}' exists.
    """
    base_url = get_backend_base_url()
    url = f"{base_url}/jobs/{job_id}"
    logger.info(f"Fetching details for job ID {job_id} from: {url}")

    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        logger.info(f"Successfully fetched details for job ID {job_id}.")
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"Timeout occurred while fetching details for job ID {job_id}")
        st.warning(f"Request timed out while fetching details for Job ID {job_id}.")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error while fetching details for job ID {job_id}.")
        st.warning("Could not connect to the backend to fetch job details.")
        return None
    except requests.exceptions.RequestException as e:
        if e.response is not None and e.response.status_code == 404:
            logger.warning(
                f"Job ID {job_id} not found at backend ({url}). Status code 404."
            )
            st.warning(f"Job with ID {job_id} could not be found.")
        else:
            logger.warning(f"Failed to fetch job details for job ID {job_id}: {e}")
            st.warning(f"Failed to retrieve details for Job ID {job_id}: {e}")
        return None
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred fetching details for job ID {job_id}: {e}"
        )
        st.error(f"An unexpected error occurred while fetching job details: {e}")
        return None


# --- User API Functions ---


def lookup_user_by_email(email: str) -> dict | None:
    """
    Looks up a user by email via the backend API.

    Args:
        email (str): The email address to look up.

    Returns:
        dict: The user details dictionary if found, None otherwise (handles 404).
              Raises exceptions for other connection/request errors.
    """
    base_url = get_backend_base_url()
    url = f"{base_url}/users/lookup_by_email"
    params = {"email": email}
    logger.info(f"Attempting user lookup via GET to: {url} for email: {email}")

    try:
        response = requests.get(
            url, params=params, timeout=30
        )  # shorter timeout for lookup
        # check specifically for 404 before raising for other errors
        if response.status_code == 404:
            logger.info(f"User lookup returned 404 (Not Found) for email: {email}")
            return None  # indicates user not found
        # raise exceptions for other bad status codes (e.g., 500, 400)
        response.raise_for_status()
        user_data = response.json()
        logger.info(
            f"User lookup successful for email: {email}. Found user ID: {user_data.get('id')}"
        )
        return user_data  # return the found user details
    except requests.exceptions.Timeout:
        logger.error(f"Timeout occurred during user lookup for {email} at {url}")
        st.error("Request timed out while checking user details.")
        raise  # re-raise to potentially stop execution or be caught higher up
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error during user lookup for {email} at {url}.")
        st.error("Connection Error: Could not connect to backend to verify user.")
        raise  # re-raise
    except requests.exceptions.RequestException as e:
        # handles other errors like 500, 4xx (excluding 404 handled above)
        logger.exception(f"Request failed during user lookup for {email}: {e}")
        error_detail = str(e)
        if e.response is not None:
            try:
                error_detail = e.response.json().get("detail", e.response.text)
            except Exception:
                error_detail = e.response.text if e.response.text else str(e)
        st.error(f"User Lookup Error: {error_detail}")
        raise  # re-raise
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred during user lookup for {email}: {e}"
        )
        st.error(f"An unexpected system error occurred during user lookup: {e}")
        raise  # re-raise


def register_user(name: str, email: str) -> dict | None:
    """
    Registers a new user via the backend API.

    Args:
        name (str): The user's full name.
        email (str): The user's email address.

    Returns:
        dict: The created user's details dictionary on success.
              Returns None if registration fails (e.g., email conflict (409), validation error (400)).
              Raises exceptions for other connection/request errors.
    """
    base_url = get_backend_base_url()
    url = f"{base_url}/users/register"
    payload = {"name": name, "email": email}
    logger.info(f"Attempting user registration via POST to: {url} for email: {email}")

    try:
        response = requests.post(url, json=payload, timeout=60)
        # check for specific conflict/validation errors before raising generally
        if response.status_code == 409:  # Conflict (email exists)
            logger.warning(
                f"Registration failed: Email '{email}' already exists (409 Conflict)."
            )
            st.error(f"This email address ({email}) is already registered.")
            return None
        if (
            response.status_code == 422
        ):  # Unprocessable Entity (Pydantic validation error)
            logger.warning(
                f"Registration failed: Invalid data provided (422). Payload: {payload}, Response: {response.text}"
            )
            try:
                error_detail = response.json().get("detail", "Invalid input data.")
                # you might want to parse pydantic's detailed errors here if needed
            except Exception:
                error_detail = "Invalid input data provided."
            st.error(f"Registration failed: {error_detail}")
            return None

        # raise exceptions for other bad status codes (e.g., 500)
        response.raise_for_status()
        user_data = response.json()
        logger.info(
            f"User registration successful for email: {email}. User ID: {user_data.get('id')}"
        )
        return user_data  # return the created user details
    except requests.exceptions.Timeout:
        logger.error(f"Timeout occurred during user registration for {email} at {url}")
        st.error("Request timed out during registration.")
        raise  # re-raise
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error during user registration for {email} at {url}.")
        st.error("Connection Error: Could not connect to backend for registration.")
        raise  # re-raise
    except requests.exceptions.RequestException as e:
        # handles other errors like 500
        logger.exception(f"Request failed during user registration for {email}: {e}")
        error_detail = str(e)
        if e.response is not None:
            try:
                error_detail = e.response.json().get("detail", e.response.text)
            except Exception:
                error_detail = e.response.text if e.response.text else str(e)
        st.error(f"Registration Error: {error_detail}")
        raise  # re-raise - let higher level decide if it stops execution
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred during user registration for {email}: {e}"
        )
        st.error(f"An unexpected system error occurred during registration: {e}")
        raise  # re-raise


# --- Specific Job Result Fetchers ---


def _fetch_job_result_generic(job_id: int, result_type: str) -> dict | None:
    """Generic helper to fetch specific result types for a job."""
    base_url = get_backend_base_url()
    # assumes backend has endpoints like /jobs/{job_id}/summary, /jobs/{job_id}/qa etc.
    url = f"{base_url}/jobs/{job_id}/{result_type}"
    logger.info(
        f"Fetching job result type '{result_type}' for job ID {job_id} from: {url}"
    )
    try:
        response = requests.get(
            url, timeout=120
        )  # Longer timeout for potentially larger results
        if response.status_code == 404:
            logger.warning(
                f"Result type '{result_type}' not found for job ID {job_id} (404)."
            )
            st.warning(f"Result '{result_type}' not available for this job.")
            return None
        response.raise_for_status()  # Handle other errors
        logger.info(
            f"Successfully fetched result type '{result_type}' for job ID {job_id}."
        )
        # Backend might return result directly or within a JSON structure
        # Assuming it returns JSON for consistency
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching result '{result_type}' for job ID {job_id}")
        st.error(f"Request timed out fetching job {result_type}.")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(
            f"Connection error fetching result '{result_type}' for job ID {job_id}."
        )
        st.error(f"Connection error fetching job {result_type}.")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(
            f"Failed fetching result '{result_type}' for job ID {job_id}: {e}"
        )
        st.warning(f"Failed to retrieve job {result_type}: {e}")
        return None
    except Exception as e:
        logger.exception(
            f"Unexpected error fetching result '{result_type}' for job ID {job_id}: {e}"
        )
        st.error(f"Unexpected error fetching job {result_type}: {e}")
        return None


# --- Public functions for specific result types ---


def fetch_job_summary_result(job_id: int) -> dict | None:
    """Fetches summary result for a job."""
    return _fetch_job_result_generic(job_id, "summary")


def fetch_job_qa_result(job_id: int) -> dict | None:
    """Fetches Q&A result for a job."""
    return _fetch_job_result_generic(job_id, "qa")  # Ensure backend endpoint matches


def fetch_job_obligations_result(job_id: int) -> dict | None:
    """Fetches obligations result for a job."""
    return _fetch_job_result_generic(job_id, "obligations")


def fetch_job_risks_result(job_id: int) -> dict | None:
    """Fetches risks result for a job."""
    return _fetch_job_result_generic(job_id, "risks")


def fetch_job_ingest_result(job_id: int) -> dict | None:
    """Fetches ingest result for a job."""
    return _fetch_job_result_generic(
        job_id, "ingest_result"
    )  # Ensure backend endpoint matches


def create_job_record(
    job_name: str, task_type: str, description: str | None, user_details: dict
) -> dict | None:
    """Calls backend POST /jobs to create a job DB record."""
    base_url = get_backend_base_url()
    url = f"{base_url}/jobs/"  # Endpoint for creating job record (ensure trailing slash if needed by backend)
    # Construct payload matching the backend's JobCreateRequest model
    payload = {
        "job_name": job_name,
        "task_type": task_type,
        "description": description,
        "submitted_by_name": user_details.get(
            "user_name"
        ),  # Use correct keys from user_details
        "submitted_by_email": user_details.get("user_email"),
    }
    logger.info(f"Creating job record via POST to {url} with payload: {payload}")
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        job_data = response.json()
        logger.info(f"Job record created successfully. Job ID: {job_data.get('id')}")
        return job_data  # Returns created job details including ID
    except requests.exceptions.RequestException as e:
        logger.exception(f"Failed to create job record: {e}")
        error_detail = str(e)
        if e.response is not None:
            try:
                error_detail = e.response.json().get("detail", e.response.text)
            except Exception as e:
                error_detail = e.response.text or str(e)
        st.error(f"Error creating job record: {error_detail}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error creating job record: {e}")
        st.error(f"An unexpected error occurred creating the job record: {str(e)}")
        return None


def update_job_status(
    job_id: int, status: str, result_summary: str | None = None
) -> dict | None:
    """Calls backend PUT /jobs/{job_id}/status to update job status."""
    base_url = get_backend_base_url()
    url = f"{base_url}/jobs/{job_id}/status"
    payload = {"status": status, "result_summary": result_summary}
    logger.info(f"Updating job {job_id} status to '{status}' via PUT to {url}")
    try:
        response = requests.put(url, json=payload, timeout=30)
        response.raise_for_status()
        job_data = response.json()
        logger.info(f"Job {job_id} status updated successfully.")
        return job_data
    except requests.exceptions.RequestException as e:
        logger.exception(f"Failed to update job {job_id} status: {e}")
        error_detail = str(e)
        if e.response is not None:
            try:
                error_detail = e.response.json().get("detail", e.response.text)
            except Exception as e:
                error_detail = e.response.text or str(e)
        st.error(f"Error updating job status: {error_detail}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error updating job {job_id} status: {e}")
        st.error(f"An unexpected error occurred updating job status: {str(e)}")
        return None


# --- MODIFIED: Specific Task Endpoints (e.g., Summary) ---
# Renamed old create_job to avoid confusion, now specific to task endpoints
def call_gen_summary_endpoint(payload: dict, files: list):
    """Calls the specific /gen_summary endpoint (no job metadata here)."""
    base_url = get_backend_base_url()
    endpoint_path = "gen_summary"  # Specific endpoint
    url = f"{base_url}/{endpoint_path}"
    logger.info(f"Calling Generate Summary endpoint: {url}")
    try:
        # Note: Payload here should only contain task-specific params like min/max words
        # Files are passed separately
        response = requests.post(url, data=payload, files=files, timeout=600)
        response.raise_for_status()
        logger.info("Generate Summary endpoint call successful.")
        return response.json()  # Expects {'summary': '...'}
    except requests.exceptions.RequestException as e:
        logger.exception(f"Failed Generate Summary API call: {e}")
        error_detail = str(e)
        if e.response is not None:
            try:
                error_detail = e.response.json().get("detail", e.response.text)
            except Exception as e:
                error_detail = e.response.text or str(e)
        st.error(f"Generate Summary failed: {error_detail}")
        raise  # Re-raise to be caught by the page logic
    except Exception as e:
        logger.exception(f"Unexpected error in Generate Summary call: {e}")
        st.error(f"An unexpected error occurred: {str(e)}")
        raise  # Re-raise
