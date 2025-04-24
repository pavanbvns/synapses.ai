# frontend/utils/config_loader.py

import os
import yaml
import streamlit as st
import logging

# Setup logger for this module
# using INFO level for standard operation, DEBUG for detailed tracing
logger = logging.getLogger(__name__)
log_level_str = os.environ.get("LOG_LEVEL", "INFO")  # Example: Use env var or default
log_level = getattr(logging, log_level_str.upper(), logging.INFO)
logger.setLevel(log_level)

# to prevent duplicate handlers if this module is reloaded
if not logger.handlers:
    handler = logging.StreamHandler()
    # using a detailed formatter for better debugging
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s:%(filename)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Determine the base directory of the project
# assuming this file is in project_root/frontend/utils/
# resulting path points to the directory containing config.yml
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yml")


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """
    Loads configuration from the YAML file at the project root into session state.
    This function is designed to be called once at the start of the app session.

    Args:
        config_path (str): Absolute path to the config.yml file.

    Returns:
        dict: Parsed configuration dictionary, also stored in st.session_state['config'].
              Returns an empty dict if loading fails, logging the error.
    """
    # check if configuration is already loaded in the current session state
    if "config" in st.session_state and st.session_state["config"]:
        logger.debug("Configuration already present in session state.")
        return st.session_state["config"]

    # check if the configuration file exists at the specified path
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found at path: '{config_path}'")
        st.error(
            f"Critical Error: Configuration file '{os.path.basename(config_path)}' is missing."
        )
        # store empty dict in session state to prevent repeated load attempts
        st.session_state["config"] = {}
        return {}

    try:
        # attempt to open and parse the YAML configuration file
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
            # handle case where the YAML file is empty
            if config_data is None:
                config_data = {}
            st.session_state["config"] = config_data
            logger.info(f"Configuration loaded successfully from '{config_path}'.")
            return config_data
    except (yaml.YAMLError, IOError) as e:
        # handle errors during file reading or YAML parsing
        logger.exception(
            f"Failed to load or parse configuration from '{config_path}': {e}"
        )
        st.error(
            f"Critical Error: Failed to load configuration. Please check the file '{os.path.basename(config_path)}'."
        )
        # store empty dict in session state to prevent repeated load attempts
        st.session_state["config"] = {}
        return {}
    except Exception as e:
        # handle any other unexpected errors during the loading process
        logger.exception(
            f"An unexpected error occurred during configuration loading from '{config_path}': {e}"
        )
        st.error(
            "Critical Error: An unexpected error occurred while loading configuration."
        )
        st.session_state["config"] = {}
        return {}


def get_config_value(key: str, default: any = None) -> any:
    """
    Safely retrieves a configuration value from the loaded dictionary in session state.
    Supports nested keys using dot notation (e.g., 'qdrant.host').

    Args:
        key (str): The configuration key to retrieve.
        default (any): The value to return if the key is not found or an error occurs.

    Returns:
        any: The requested configuration value or the provided default.
    """
    # check if config exists in session state; attempt to load if missing
    if "config" not in st.session_state:
        logger.warning(
            "Config not found in session state during get_config_value call. Attempting recovery load."
        )
        load_config()  # Note: This might fail if called too early in Streamlit lifecycle

    config_dict = st.session_state.get("config", {})
    value = config_dict
    try:
        # navigate through nested keys if dot notation is used
        keys = key.split(".")
        for k in keys:
            # check if the current level is a dictionary and contains the key
            if isinstance(value, dict):
                # using get allows specifying a temporary default (None here) if key is missing
                value = value.get(k)
            else:
                # current level is not a dictionary, so cannot proceed further
                value = None
                break  # exit the loop as the path is broken

        # if the final value is None (key not found or path broken), return default
        if value is None:
            logger.warning(
                f"Configuration key '{key}' not found. Returning default value: {default}"
            )
            return default
        # otherwise, return the found value
        return value
    except Exception as e:
        # handle unexpected errors during key access
        logger.error(
            f"Error accessing configuration key '{key}': {e}. Returning default value: {default}"
        )
        return default
