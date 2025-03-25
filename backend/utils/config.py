# backend/utils/config.py

import os
import yaml
import logging

# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


class Config:
    def __init__(self, config_file: str = None):
        # If no config file path is provided, assume it is in the project root.
        if config_file is None:
            # Compute the project root (assumes this file is in backend/utils/)
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            config_file = os.path.join(base_dir, "config.yml")
        self.config_file = config_file
        self.data = {}
        self.load_config()

    def load_config(self):
        try:
            if not os.path.exists(self.config_file):
                logger.error("Config file '%s' not found.", self.config_file)
                raise FileNotFoundError(f"Config file '{self.config_file}' not found.")
            with open(self.config_file, "r") as f:
                self.data = yaml.safe_load(f)
                if self.data is None:
                    logger.warning(
                        "Config file '%s' is empty. Using empty configuration.",
                        self.config_file,
                    )
                    self.data = {}
                else:
                    logger.info(
                        "Configuration loaded successfully from '%s'.", self.config_file
                    )
        except yaml.YAMLError as ye:
            logger.exception("YAML error while parsing the config file: %s", ye)
            raise
        except Exception as e:
            logger.exception("Unexpected error occurred while loading config: %s", e)
            raise

    def get(self, key, default=None):
        try:
            return self.data.get(key, default)
        except Exception as e:
            logger.exception("Error retrieving config key '%s': %s", key, e)
            return default


# Create a singleton instance for import in other modules
try:
    config = Config()
except Exception as e:
    logger.critical("Failed to initialize configuration: %s", e)
    raise
