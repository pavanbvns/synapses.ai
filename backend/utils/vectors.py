import logging
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
    Initialize and return a QdrantClient instance using configuration settings.
    """
    try:
        qdrant_config = config.get("qdrant", {})
        host = qdrant_config.get("host", "localhost")
        port = qdrant_config.get("port", 6333)
        client = QdrantClient(host=host, port=port)
        logger.info(
            "Qdrant client initialized with host '%s' and port '%s'.", host, port
        )
        return client
    except Exception as e:
        logger.exception("Error initializing Qdrant client: %s", e)
        raise


def create_collection(
    collection_name: str = None,
    vector_size: int = None,
    distance_metric: str = "Cosine",
):
    """
    Create (or recreate) a Qdrant collection with the specified name, vector size, and distance metric.
    """
    try:
        qdrant_config = config.get("qdrant", {})
        if not collection_name:
            collection_name = qdrant_config.get("collection_name", "default_collection")
        if not vector_size:
            vector_size = qdrant_config.get("vector_size", 4096)
        client = get_qdrant_client()
        # Map the provided distance metric to Qdrant's Distance enum.
        distance = (
            Distance.COSINE
            if distance_metric.lower() == "cosine"
            else Distance.EUCLIDEAN
        )
        # Recreate the collection with the new parameters.
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=distance),
        )
        logger.info(
            "Collection '%s' created with vector size %d and distance metric '%s'.",
            collection_name,
            vector_size,
            distance_metric,
        )
    except Exception as e:
        logger.exception("Error creating collection '%s': %s", collection_name, e)
        raise


def check_or_create_collection(collection_name: str, vector_size: int = 768):
    """
    Ensure that the specified Qdrant collection exists.
    If it doesn't, create it using the provided vector size and COSINE distance.
    """
    try:
        client = get_qdrant_client()
        if not client.collection_exists(collection_name):
            logger.info(
                "Collection '%s' does not exist. Creating collection.", collection_name
            )
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size, distance=Distance.COSINE
                ),
            )
            logger.info("Collection '%s' created successfully.", collection_name)
        else:
            logger.info("Collection '%s' already exists.", collection_name)
    except Exception as e:
        logger.exception(
            "Error checking or creating collection '%s': %s", collection_name, e
        )
        raise


def insert_embeddings(collection_name: str, points: list):
    """
    Insert embeddings into the specified Qdrant collection.
    """
    try:
        client = get_qdrant_client()
        point_structs = []
        for point in points:
            p = PointStruct(
                id=point["id"], vector=point["vector"], payload=point.get("payload", {})
            )
            point_structs.append(p)
        response = client.upsert(collection_name=collection_name, points=point_structs)
        logger.info(
            "Inserted %d points into collection '%s'.", len(points), collection_name
        )
        return response
    except Exception as e:
        logger.exception(
            "Error inserting embeddings into collection '%s': %s", collection_name, e
        )
        raise


def search_embeddings(
    collection_name: str, query_vector: list, top_k: int = 5, query_filter: dict = None
):
    """
    Search for the nearest neighbors of a given query vector in the specified Qdrant collection.
    """
    try:
        client = get_qdrant_client()
        filter_obj = None
        if query_filter:
            filter_obj = Filter(**query_filter)
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=filter_obj,
        )
        logger.info(
            "Search in collection '%s' returned %d results.",
            collection_name,
            len(results),
        )
        # print("---------------------------------------------------------")
        # print("cached results: \n", results)
        # print("---------------------------------------------------------")
        return results
    except Exception as e:
        logger.exception(
            "Error searching embeddings in collection '%s': %s", collection_name, e
        )
        raise


def get_extracted_text_from_qdrant(file_hash: str, collection_name: str) -> str:
    """
    Search for a document in Qdrant by its file hash and return the stored extracted text.
    Returns an empty string if not found.
    """
    try:
        client = get_qdrant_client()
        filter_payload = {"must": [{"key": "file_hash", "match": {"value": file_hash}}]}
        results = client.search(
            collection_name=collection_name,
            query_vector=[0.0] * config.get("qdrant", {}).get("vector_size", 4096),
            limit=1,
            query_filter=Filter(**filter_payload),
        )
        # print("---------------------------------------------------------")
        # print("Qdrant cache text: \n", results[0].payload.get("extracted_text"))
        # print("---------------------------------------------------------")
        if results and results[0].payload.get("extracted_text"):
            logger.info("Found cached extracted text for file hash %s.", file_hash)
            return results[0].payload.get("extracted_text")
        else:
            logger.debug("No cached extracted text found for file hash %s.", file_hash)
            return ""
    except Exception as e:
        logger.exception(
            "Error retrieving extracted text from Qdrant for file hash '%s': %s",
            file_hash,
            e,
        )
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
    Background task to compute embedding from the extracted text and store file metadata and embedding in Qdrant.
    """
    try:
        new_filename = f"{unique_id}_{file_name}"
        file_path = save_file_to_disk(file_bytes, processed_dir, new_filename)
        logger.info("Background task: saved file as %s", file_path)
        embedding = get_embedding(extracted_text, llama_host, llama_port)
        logger.info(
            "Background task: obtained embedding vector of length %d.", len(embedding)
        )
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
        logger.info(
            "Background task: stored processed file in Qdrant with UUID: %s", unique_id
        )
    except Exception as e:
        logger.exception("Background task: error saving file to Qdrant: %s", e)
