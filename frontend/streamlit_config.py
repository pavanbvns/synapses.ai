# frontend/streamlit_config.py
import yaml
import os


def load_config(config_path="../config.yml"):
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to load config: {e}")
        return {}
