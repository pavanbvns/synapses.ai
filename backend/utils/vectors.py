# backend/utils/vectors.py

import logging
import hashlib
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, PointStruct, Filter

from backend.utils.config import config
from backend.utils.utils import (
    save_file_to_disk,
    get_embedding,
)

# Configure module-level logger using settings from config.yml
logging_level_str = config.get("logging_level", "DEBUG")
numeric_level = getattr(logging, logging_level_str.upper(), logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(numeric_level)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def get_qdrant_client() -> QdrantClient:
    """
    Bootstraps and returns a connected QdrantClient instance.
    """
    try:
        qdrant_config = config.get("qdrant", {})
        host = qdrant_config.get("host", "localhost")
        port = qdrant_config.get("port", 6333)
        client = QdrantClient(host=host, port=port)
        logger.info("Qdrant client initialized on %s:%d", host, port)
        return client
    except Exception as e:
        logger.exception("Failed to initialize Qdrant client: %s", e)
        raise


def create_collection(
    collection_name: str = None,
    vector_size: int = None,
    distance_metric: str = "Cosine",
):
    """
    Creates (or recreates) a collection in Qdrant with specified parameters.
    """
    try:
        qdrant_config = config.get("qdrant", {})
        collection_name = collection_name or qdrant_config.get(
            "collection_name", "default_collection"
        )
        vector_size = vector_size or qdrant_config.get("vector_size", 4096)
        distance = (
            Distance.COSINE
            if distance_metric.lower() == "cosine"
            else Distance.EUCLIDEAN
        )

        client = get_qdrant_client()
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=distance),
        )
        logger.info(
            "Collection '%s' created with size %d and metric '%s'.",
            collection_name,
            vector_size,
            distance_metric,
        )
    except Exception as e:
        logger.exception("Error creating collection '%s': %s", collection_name, e)
        raise


def check_or_create_collection(collection_name: str, vector_size: int = 768):
    """
    Ensures the specified collection exists. If not, it is created.
    """
    try:
        client = get_qdrant_client()
        if not client.collection_exists(collection_name):
            logger.info("Collection '%s' not found. Creating now...", collection_name)
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size, distance=Distance.COSINE
                ),
            )
            logger.info("Collection '%s' created successfully.", collection_name)
        else:
            logger.info(
                "Collection '%s' already exists. Skipping creation.", collection_name
            )
    except Exception as e:
        logger.exception("Error ensuring collection '%s': %s", collection_name, e)
        raise


def insert_embeddings(collection_name: str, points: list):
    """
    Inserts the given vector points into the specified Qdrant collection.
    """
    try:
        client = get_qdrant_client()
        point_structs = [
            PointStruct(id=pt["id"], vector=pt["vector"], payload=pt.get("payload", {}))
            for pt in points
        ]
        response = client.upsert(collection_name=collection_name, points=point_structs)
        logger.info(
            "Inserted %d vectors into collection '%s'.", len(points), collection_name
        )
        return response
    except Exception as e:
        logger.exception(
            "Failed to insert embeddings into '%s': %s", collection_name, e
        )
        raise


def search_embeddings(
    collection_name: str, query_vector: list, top_k: int = 5, query_filter: dict = None
):
    """
    Executes a similarity search using the query vector and optional filter.
    """
    try:
        client = get_qdrant_client()
        filter_obj = Filter(**query_filter) if query_filter else None
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=filter_obj,
        )
        logger.info(
            "Search returned %d results in collection '%s'.",
            len(results),
            collection_name,
        )
        return results
    except Exception as e:
        logger.exception("Search failed in collection '%s': %s", collection_name, e)
        raise


def get_extracted_text_from_qdrant(file_hash: str, collection_name: str) -> str:
    """
    Retrieves previously stored extracted text using file hash as identifier.
    """
    try:
        client = get_qdrant_client()
        filter_payload = {"must": [{"key": "file_hash", "match": {"value": file_hash}}]}
        dummy_query = [0.0] * config.get("qdrant", {}).get("vector_size", 4096)
        results = client.search(
            collection_name=collection_name,
            query_vector=dummy_query,
            limit=1,
            query_filter=Filter(**filter_payload),
        )
        if results and results[0].payload.get("extracted_text"):
            logger.info("Extracted text retrieved for file hash '%s'.", file_hash)
            return results[0].payload.get("extracted_text")
        logger.info("No extracted text found for file hash '%s'.", file_hash)
        return ""
    except Exception as e:
        logger.exception("Failed to retrieve text for hash '%s': %s", file_hash, e)
        return ""


def background_save_to_qdrant(
    file_bytes: bytes,
    file_hash: str,
    file_name: str,
    processed_dir: str,
    unique_id: str,
    extracted_text: str,
    llama_host: str,
    llama_port: int,
    collection_name: str,
):
    """
    Background thread task to save document embeddings and metadata to Qdrant.
    """
    try:
        new_filename = f"{unique_id}_{file_name}"
        file_path = save_file_to_disk(file_bytes, processed_dir, new_filename)
        logger.info("Saved processed file to disk: %s", file_path)

        embedding = get_embedding(extracted_text, llama_host, llama_port)
        logger.info("Generated embedding vector of length %d.", len(embedding))

        check_or_create_collection(collection_name, vector_size=len(embedding))
        point = {
            "id": unique_id,
            "vector": embedding,
            "payload": {
                "file_hash": file_hash,
                "extracted_text": extracted_text,
                "filename": file_name,
            },
        }
        insert_embeddings(collection_name, [point])
        logger.info("Stored document vector in Qdrant with UUID: %s", unique_id)
    except Exception as e:
        logger.exception("Error in background embedding save task: %s", e)


def compute_sha256(file_path: str) -> str:
    """
    Computes the SHA-256 hash of the given file. Useful for deduplication.
    """
    try:
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256()
            while chunk := f.read(8192):
                file_hash.update(chunk)
            return file_hash.hexdigest()
    except Exception as e:
        logger.exception("Failed to compute SHA-256 hash for %s: %s", file_path, e)
        return ""
