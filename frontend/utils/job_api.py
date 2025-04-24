# frontend/utils/job_api.py

import requests
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def post_job(endpoint: str, payload: dict, files: list = None) -> dict:
    """
    Send a POST request to the backend API to initiate a job.

    Args:
        endpoint (str): Full URL of the backend API endpoint.
        payload (dict): JSON/form data to send.
        files (list): List of tuples representing uploaded files, if any.

    Returns:
        dict: Parsed JSON response or error message.
    """
    try:
        logger.info("Posting job to endpoint: %s", endpoint)
        if files:
            response = requests.post(endpoint, data=payload, files=files)
        else:
            response = requests.post(endpoint, json=payload)

        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        logger.exception("Failed to post job to %s: %s", endpoint, e)
        return {"error": str(e)}
