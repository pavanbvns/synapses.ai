# backend/utils/config.py

import os
import yaml
import logging

# Set up logger for this module
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class Config:
    def __init__(self, config_file: str = None):
        """
        Initialize and load configuration from YAML file.
        Priority: ENV override > config.yml
        """
        if config_file is None:
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            config_file = os.path.join(base_dir, "config.yml")

        self.config_file = config_file
        self.data = {}
        self.load_config()

    def load_config(self):
        """Load and parse YAML config into dictionary."""
        try:
            if not os.path.exists(self.config_file):
                logger.error("Config file '%s' not found.", self.config_file)
                raise FileNotFoundError(f"Config file '{self.config_file}' not found.")

            with open(self.config_file, "r") as f:
                raw_config = yaml.safe_load(f) or {}

            self.data = self._apply_env_overrides(raw_config)
            logger.info("Configuration loaded from '%s'.", self.config_file)
        except yaml.YAMLError as ye:
            logger.exception("YAML error while parsing the config file: %s", ye)
            raise
        except Exception as e:
            logger.exception("Unexpected error occurred while loading config: %s", e)
            raise

    def _apply_env_overrides(self, config_data: dict) -> dict:
        """Override config values from environment variables (if present)."""
        env_overrides = {
            "llama_server_host": os.getenv("LLAMA_SERVER_HOST"),
            "llama_server_port": os.getenv("LLAMA_SERVER_PORT"),
            "backend_base_url": os.getenv("BACKEND_BASE_URL"),
            "frontend_base_url": os.getenv("FRONTEND_BASE_URL"),
            "database_url": os.getenv("DATABASE_URL"),
        }
        for key, value in env_overrides.items():
            if value is not None:
                config_data[key] = type(config_data.get(key, value))(value)
                logger.info("Overriding '%s' from environment: %s", key, value)
        return config_data

    def get(self, key, default=None):
        try:
            return self.data.get(key, default)
        except Exception as e:
            logger.exception("Error retrieving config key '%s': %s", key, e)
            return default


# Global config singleton
try:
    config = Config()
except Exception as e:
    logger.critical("Failed to initialize configuration: %s", e)
    raise
