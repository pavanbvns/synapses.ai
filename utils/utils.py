import os
import logging
from typing import Any
from utils.config import config
import hashlib

# Retrieve logging level from config (expected values: 'DEBUG', 'INFO', etc.)
logging_level_str = config.get("logging_level", "DEBUG")
numeric_level = getattr(logging, logging_level_str.upper(), None)
if not isinstance(numeric_level, int):
    numeric_level = logging.DEBUG

logger = logging.getLogger(__name__)
logger.setLevel(numeric_level)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Retrieve allowed file extensions from config
ALLOWED_EXTENSIONS = set(
    config.get(
        "allowed_file_extensions",
        [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".tiff", ".png"],
    )
)

# Retrieve allowed file size limit from config (in bytes; default: 10 MB)
ALLOWED_FILE_SIZE_LIMIT = config.get("allowed_file_size_limit", 10 * 1024 * 1024)

def save_file_to_disk(file_bytes: bytes, destination_dir: str, filename: str) -> str:
    """
    Save an uploaded file to a destination directory.

    Args:
        file_data: A file-like object (an UploadFile instance).
        destination_dir: The directory where the file should be saved.
        filename: The desired filename for the saved file.

    Returns:
        The full file path of the saved file.
    """
    try:
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)
            logger.info("Created directory '%s' for file storage.", destination_dir)
        file_path = os.path.join(destination_dir, filename)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        logger.info("File saved successfully to '%s'.", file_path)
        return file_path
    except Exception as e:
        logger.exception("Error saving file to disk: %s", e)
        raise

def get_file_extension(file_path: str) -> str:
    """
    Determine and return the lowercase file extension of a file.
    """
    try:
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        logger.debug("Determined file extension for '%s': %s", file_path, ext)
        return ext
    except Exception as e:
        logger.exception("Error determining file extension for '%s': %s", file_path, e)
        raise

def validate_file(file_path: str) -> bool:
    """
    Validate that the file has an allowed extension.
    """
    try:
        ext = get_file_extension(file_path)
        if ext in ALLOWED_EXTENSIONS:
            logger.info("File '%s' is valid with extension '%s'.", file_path, ext)
            return True
        else:
            logger.warning("File '%s' has unsupported extension '%s'.", file_path, ext)
            return False
    except Exception as e:
        logger.exception("Error validating file '%s': %s", file_path, e)
        raise

def validate_file_size(file_path: str) -> bool:
    """
    Validate that the file size does not exceed the allowed file size limit.
    """
    try:
        file_size = os.path.getsize(file_path)
        if file_size <= ALLOWED_FILE_SIZE_LIMIT:
            logger.info("File '%s' size %d bytes is within the allowed limit.", file_path, file_size)
            return True
        else:
            logger.warning("File '%s' size %d bytes exceeds allowed limit of %d bytes.", file_path, file_size, ALLOWED_FILE_SIZE_LIMIT)
            return False
    except Exception as e:
        logger.exception("Error validating file size for '%s': %s", file_path, e)
        raise

def load_file_bytes(file_path: str) -> bytes:
    """
    Load a file and return its contents as bytes.
    """
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        logger.info("Loaded file bytes from '%s'.", file_path)
        return data
    except Exception as e:
        logger.exception("Error loading file bytes from '%s': %s", file_path, e)
        raise




def compute_file_hash(file_bytes: bytes) -> str:
    """
    Compute and return the SHA256 hash of the file bytes.
    """
    try:
        sha256 = hashlib.sha256()
        sha256.update(file_bytes)
        file_hash = sha256.hexdigest()
        logger.debug("Computed SHA256 hash: %s", file_hash)
        return file_hash
    except Exception as e:
        logger.exception("Error computing file hash: %s", e)
        raise


def get_embedding(text: str, llama_host: str, llama_port: int, n_predict: int = 128, temperature: float = 0.7) -> list:
    """
    Obtain an embedding vector for the provided text by calling llama-server's embedding endpoint.
    NOTE: This is a stub function—you need to implement the actual call based on your llama-server's API.
    """
    try:
        # Example: assuming your llama-server exposes an /embedding endpoint.
        url = f"http://{llama_host}:{llama_port}/embedding"
        payload = {
            "prompt": text,
            "n_predict": n_predict,
            "temperature": temperature
        }
        logger.debug("Requesting embedding from llama-server at %s with payload: %s", url, payload)
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            embedding = data.get("embedding", [])
            logger.info("Obtained embedding vector of length %d.", len(embedding))
            return embedding
        else:
            logger.error("Failed to get embedding from llama-server. Status: %s, Response: %s",
                         response.status_code, response.text)
            return []
    except Exception as e:
        logger.exception("Error getting embedding: %s", e)
        raise