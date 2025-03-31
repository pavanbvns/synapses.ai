# backend/utils/utils.py

import os
import logging

# from typing import
from .config import config  # Relative import based on new project structure
import hashlib
import requests
import time
import json

# Retrieve logging level from configuration (expected values: 'DEBUG', 'INFO', etc.)
logging_level_str = config.get("logging_level", "DEBUG")
numeric_level = getattr(logging, logging_level_str.upper(), logging.DEBUG)

logger = logging.getLogger(__name__)
logger.setLevel(numeric_level)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Retrieve allowed file extensions and file size limit from configuration
ALLOWED_EXTENSIONS = set(
    config.get(
        "allowed_file_extensions",
        [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".tiff", ".png"],
    )
)
ALLOWED_FILE_SIZE_LIMIT = config.get("allowed_file_size_limit", 10 * 1024 * 1024)


def save_file_to_disk(file_bytes: bytes, destination_dir: str, filename: str) -> str:
    """
    Save the provided file bytes to disk at the specified destination directory with the given filename.
    Returns the full path of the saved file.
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
    Return the lowercase file extension of the specified file.
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
    Validate that the file size does not exceed the allowed limit.
    """
    try:
        file_size = os.path.getsize(file_path)
        if file_size <= ALLOWED_FILE_SIZE_LIMIT:
            logger.info(
                "File '%s' size %d bytes is within the allowed limit.",
                file_path,
                file_size,
            )
            return True
        else:
            logger.warning(
                "File '%s' size %d bytes exceeds allowed limit of %d bytes.",
                file_path,
                file_size,
                ALLOWED_FILE_SIZE_LIMIT,
            )
            return False
    except Exception as e:
        logger.exception("Error validating file size for '%s': %s", file_path, e)
        raise


def load_file_bytes(file_path: str) -> bytes:
    """
    Load and return the contents of the file as bytes.
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
    Compute and return the SHA256 hash of the provided file bytes.
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


def get_embedding(
    text: str,
    llama_host: str,
    llama_port: int,
    n_predict: int = 128,
    temperature: float = 0.0,
    max_chunk_size: int = int(config.get("max_embedding_input_length", 1024)),
) -> list:
    """
    Request an embedding vector from llama-server for the given text.
    If the text is too long, it is split into chunks and the embeddings are aggregated
    via elementwise mean pooling.

    Parameters:
      - text: The input text.
      - llama_host: Hostname of the llama-server.
      - llama_port: Port number of the llama-server.
      - n_predict: A parameter carried over from text-generation APIs.
      - temperature: Temperature parameter for the embedding call.
      - max_chunk_size: Maximum number of characters per chunk (default from config).

    Returns:
      - A list of floats representing the aggregated embedding vector.

    Note:
      The expected hidden size (embedding dimension) is read from config ("embedding_hidden_size")
      and for llama 3.2 3B it is 4096. If the server returns per-token embeddings, they are aggregated
      via mean pooling.
    """
    url = f"http://{llama_host}:{llama_port}/embedding"
    expected_hidden_size = int(config.get("embedding_hidden_size", 4096))

    def request_embedding(chunk: str) -> list:
        payload = {
            "input": chunk,
            "n_predict": n_predict,
            "temperature": temperature,
            "pooling": "mean",  # Request mean pooling if supported
        }
        logger.debug("Requesting embedding for chunk of length %d.", len(chunk))
        response = requests.post(url, json=payload, timeout=120)
        if response.status_code != 200:
            logger.error("Error obtaining embedding for chunk: %s", response.text)
            raise Exception(f"Error obtaining embedding for chunk: {response.text}")
        data = response.json()
        # logger.debug("Embedding response: %s", data)

        # Extract the embedding vector from the response.
        matrix = None
        if isinstance(data, list):
            if not data:
                raise Exception("Received empty embedding list for chunk.")
            matrix = data[0].get("embedding") or data[0].get("vector")
        elif isinstance(data, dict):
            matrix = data.get("embedding") or data.get("vector")
        else:
            raise Exception(
                "Unexpected response type for embedding: " + str(type(data))
            )
        if not matrix:
            raise Exception("No embedding found in response: " + json.dumps(data))

        # If the embedding is nested (list of lists), flatten it.
        if isinstance(matrix, list) and matrix and isinstance(matrix[0], list):
            flattened = []
            for sub in matrix:
                flattened.extend(sub)
            matrix = flattened

        # Ensure the length is a multiple of expected_hidden_size.
        remainder = len(matrix) % expected_hidden_size
        if remainder != 0:
            logger.warning(
                "Returned embedding length (%d) is not a multiple of expected hidden size (%d); truncating remainder.",
                len(matrix),
                expected_hidden_size,
            )
            matrix = matrix[: len(matrix) - remainder]

        # If we received exactly one vector, return it.
        if len(matrix) == expected_hidden_size:
            return matrix
        # If multiple per-token embeddings were returned, aggregate via mean pooling.
        elif len(matrix) > expected_hidden_size:
            num_tokens = len(matrix) // expected_hidden_size
            aggregated = []
            for i in range(expected_hidden_size):
                total = sum(
                    matrix[i + j * expected_hidden_size] for j in range(num_tokens)
                )
                aggregated.append(total / num_tokens)
            return aggregated
        else:
            raise Exception(
                f"Embedding dimension mismatch: got {len(matrix)}, expected at least {expected_hidden_size}"
            )

    # Process text: if within allowed limit, process directly; otherwise, split into chunks.
    if len(text) <= max_chunk_size:
        logger.debug(
            "Input text length (%d) is within allowed limit (%d).",
            len(text),
            max_chunk_size,
        )
        return request_embedding(text)
    else:
        logger.debug(
            "Input text length (%d) exceeds limit (%d). Splitting text into chunks.",
            len(text),
            max_chunk_size,
        )
        # Split by character count. (Consider using a tokenizer for token-based splitting.)
        chunks = [
            text[i : i + max_chunk_size] for i in range(0, len(text), max_chunk_size)
        ]
        embeddings = []
        for idx, chunk in enumerate(chunks):
            logger.debug("Processing chunk %d of %d...", idx + 1, len(chunks))
            emb = request_embedding(chunk)
            embeddings.append(emb)
            time.sleep(0.1)  # slight pause to avoid overwhelming the server

        # Verify all embeddings have the same length.
        vector_lengths = [len(emb) for emb in embeddings]
        if not all(length == vector_lengths[0] for length in vector_lengths):
            logger.error(
                "Mismatch in embedding lengths among chunks: %s", vector_lengths
            )
            raise Exception("Mismatch in embedding lengths among chunks.")

        # Aggregate embeddings via elementwise mean.
        vector_length = vector_lengths[0]
        aggregated_embedding = [0.0] * vector_length
        for emb in embeddings:
            for i in range(vector_length):
                aggregated_embedding[i] += emb[i]
        aggregated_embedding = [val / len(embeddings) for val in aggregated_embedding]
        logger.debug("Aggregated embedding computed from %d chunks.", len(embeddings))
        return aggregated_embedding
