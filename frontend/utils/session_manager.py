# frontend/utils/session_manager.py

import streamlit as st
import re
import logging
import os
import time  # used for brief pauses after actions

# imports functions for backend communication from api.py
from .api import lookup_user_by_email, register_user

# --- Logger Setup ---
# basic logger configuration for this module
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

# --- Session State Initialization ---


def initialize_session_state():
    """
    Initializes required keys in Streamlit's session state if not already present.
    Sets default values for user details, registration flow flags, and UI state.
    """
    # defines default values for session state variables
    defaults = {
        "user_name": "",
        "user_email": "",
        "is_registered": False,  # Tracks if user is identified for the current session
        "prompt_for_email": True,  # Controls display of initial email prompt
        "prompt_for_registration": False,  # Controls display of full registration form
        "pending_email": "",  # Temporarily stores email during registration flow
        "selected_job_id": None,  # ID of job selected for detail view
        "show_job_modal": False,  # Flag to display the job creation modal
        "last_job_result": None,  # Stores result from the last submitted job
        "current_job_page": 1,  # Current page for job list pagination
        "selected_task_for_modal": None,  # Task pre-selected via quick links
        "show_help_modal": False,  # Flag to display the help documentation modal
        "show_tech_docs_modal": False,  # Flag to display the tech docs modal
    }
    # iterates through defaults and initializes missing keys in session state
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
            logger.debug(f"Initialized session state key '{key}' with default: {value}")


# --- User Detail Validation ---


def _is_valid_email(email: str) -> bool:
    """Internal helper performs basic email format validation using regex."""
    if not email:
        return False
    # standard regex for email format check
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    is_match = re.match(pattern, email.strip()) is not None
    logger.debug(f"Email validation for '{email}': {is_match}")
    return is_match


def _is_valid_name(name: str) -> bool:
    """Internal helper checks if name is non-empty and avoids common restricted terms."""
    if not name or not name.strip():
        return False
    cleaned_name = name.strip().lower()
    # set of common placeholder/test names to disallow
    restricted_terms = {"test", "demo", "admin", "user", "sample", "na", "none"}
    is_restricted = cleaned_name in restricted_terms
    if is_restricted:
        logger.debug(f"Name validation failed: Restricted term '{name}'")
    # returns True if name is not empty and not restricted
    return not is_restricted


# --- User Detail Management (Session State Only) ---


def _save_user_details_to_session(name: str, email: str):
    """Internal function to save validated user details to session state for the current session."""
    st.session_state["user_name"] = name.strip()
    st.session_state["user_email"] = email.strip().lower()
    st.session_state["is_registered"] = (
        True  # Marks user as identified for this session
    )
    # Resets flags controlling the lookup/registration UI flow
    st.session_state["prompt_for_email"] = False
    st.session_state["prompt_for_registration"] = False
    st.session_state["pending_email"] = ""
    logger.info(
        f"User details saved to session state for email: {st.session_state['user_email']}"
    )


def get_user_details() -> dict:
    """Retrieves the current user's name and email from session state."""
    initialize_session_state()  # Ensures keys exist before access
    return {
        "user_name": st.session_state.get("user_name", ""),
        "user_email": st.session_state.get("user_email", ""),
    }


def is_user_registered() -> bool:
    """Checks if user is marked as registered *in the current session*."""
    initialize_session_state()  # Ensures key exists before checking
    is_reg = st.session_state.get("is_registered", False)
    logger.debug(f"Session registration status check: {is_reg}")
    return is_reg


# --- Registration / Lookup UI and Logic ---


def render_lookup_or_registration():
    """
    Manages the user identification flow using backend API calls.
    Displays UI for email lookup or full registration based on session state flags.
    Handles API calls and updates session state accordingly.
    Returns True if UI was displayed (halting app execution), False otherwise.
    """
    # return False immediately if user is already identified in the current session
    if is_user_registered():
        return False

    # renders email lookup form if prompt_for_email flag is set
    if st.session_state.get("prompt_for_email", True):
        st.markdown("#### Welcome to Synapses.AI")
        st.markdown("Please enter your email address to begin or resume.")
        # uses a form for email input
        with st.form("email_lookup_form"):
            email_input = st.text_input(
                "Email Address*",
                key="lookup_email",
                placeholder="your.email@example.com",
            )
            lookup_button = st.form_submit_button("Continue")

            if lookup_button:
                # validates email format before API call
                if not _is_valid_email(email_input):
                    st.warning("Please enter a valid email address format.")
                else:
                    submitted_email = email_input.strip().lower()
                    logger.info(f"Attempting lookup for email: {submitted_email}")
                    try:
                        # calls backend API via helper function
                        user_data = lookup_user_by_email(submitted_email)

                        if user_data:  # User found
                            logger.info(
                                "User found via lookup. Saving details to session."
                            )
                            _save_user_details_to_session(
                                user_data["name"], user_data["email"]
                            )
                            st.success(
                                f"Welcome back, {st.session_state['user_name']}!"
                            )
                            time.sleep(1)  # brief pause to show message
                            st.rerun()  # refresh app to show main UI
                        else:  # User not found (API returned None/404)
                            logger.info(
                                "User not found via lookup. Prompting for full registration."
                            )
                            # updates state to show registration form next
                            st.session_state["pending_email"] = submitted_email
                            st.session_state["prompt_for_email"] = False
                            st.session_state["prompt_for_registration"] = True
                            st.rerun()  # refresh app to show registration form

                    except Exception as e:
                        # handles API errors (timeout, connection, etc.)
                        logger.error(f"Error during email lookup API call: {e}")
                        # error message displayed by api.py; halt execution here
                        st.stop()
        # indicates that UI was shown
        return True

    # renders full registration form if prompt_for_registration flag is set
    elif st.session_state.get("prompt_for_registration", False):
        st.markdown("#### Complete Registration")
        st.markdown(
            "We couldn't find an existing account for this email. Please provide your name."
        )
        # uses a form for name input (email is pre-filled)
        with st.form("full_registration_form"):
            email_input = st.text_input(
                "Email Address*",
                value=st.session_state.get("pending_email", ""),
                disabled=True,
            )
            name_input = st.text_input(
                "Full Name*", key="reg_name", placeholder="Your Full Name"
            )
            register_button = st.form_submit_button("Register")

            if register_button:
                final_email = st.session_state.get("pending_email")
                final_name = name_input.strip()

                # validates name before API call
                if not _is_valid_name(final_name):
                    st.warning(
                        "Please enter a valid full name (avoid 'test', 'demo', etc.)."
                    )
                # validates email again (safety check)
                elif not final_email or not _is_valid_email(final_email):
                    st.error(
                        "An error occurred with the email address. Please refresh and start over."
                    )
                    # resets state to restart the flow
                    st.session_state["prompt_for_email"] = True
                    st.session_state["prompt_for_registration"] = False
                    st.session_state["pending_email"] = ""
                    time.sleep(1)
                    st.rerun()
                else:
                    logger.info(
                        f"Attempting registration via API for email: {final_email} with name: {final_name}"
                    )
                    try:
                        # calls backend API via helper function
                        user_data = register_user(final_name, final_email)

                        if user_data:  # Registration successful
                            logger.info(
                                "Registration successful via API. Saving details to session."
                            )
                            _save_user_details_to_session(
                                user_data["name"], user_data["email"]
                            )
                            st.success(
                                f"Welcome, {st.session_state['user_name']}! Registration complete."
                            )
                            time.sleep(1)  # brief pause
                            st.rerun()  # refresh app to show main UI
                        else:
                            # registration failed (e.g., 409 conflict handled in api.py)
                            logger.warning(
                                "Registration API call indicated failure (error shown by api.py)."
                            )
                            # form remains visible for user

                    except Exception as e:
                        # handles API errors (timeout, connection, etc.)
                        logger.error(f"Error during registration API call: {e}")
                        # error message displayed by api.py
        # indicates that UI was shown
        return True

    else:
        # fallback case if state is inconsistent
        logger.warning(
            "Reached unexpected state in render_lookup_or_registration function."
        )
        return False
