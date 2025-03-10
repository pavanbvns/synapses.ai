import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, PointStruct, Filter
from utils.config import config

# Configure module-level logger using settings from config.yml
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

def get_qdrant_client() -> QdrantClient:
    """
    Initialize and return a QdrantClient instance using configuration settings.
    """
    try:
        qdrant_config = config.get("qdrant", {})
        host = qdrant_config.get("host", "localhost")
        port = qdrant_config.get("port", 6333)
        client = QdrantClient(host=host, port=port)
        logger.info("Qdrant client initialized with host '%s' and port '%s'.", host, port)
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

    If collection_name or vector_size is not provided, they are pulled from the configuration.
    """
    try:
        qdrant_config = config.get("qdrant", {})
        if not collection_name:
            collection_name = qdrant_config.get("collection_name", "default_collection")
        if not vector_size:
            vector_size = qdrant_config.get("vector_size", 768)

        client = get_qdrant_client()
        # Map the provided distance metric to Qdrant's Distance enum.
        distance = Distance.COSINE if distance_metric.lower() == "cosine" else Distance.EUCLIDEAN

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

def insert_embeddings(collection_name: str, points: list):
    """
    Insert embeddings into the specified Qdrant collection.

    Args:
        collection_name (str): The name of the Qdrant collection.
        points (list): A list of dictionaries, each containing:
            - 'id': Unique identifier for the point.
            - 'vector': The embedding vector (list of floats).
            - 'payload': (Optional) Additional metadata.

    Returns:
        The response from the Qdrant upsert operation.
    """
    try:
        client = get_qdrant_client()
        point_structs = []
        for point in points:
            p = PointStruct(
                id=point["id"],
                vector=point["vector"],
                payload=point.get("payload", {})
            )
            point_structs.append(p)
        response = client.upsert(collection_name=collection_name, points=point_structs)
        logger.info("Inserted %d points into collection '%s'.", len(points), collection_name)
        return response
    except Exception as e:
        logger.exception("Error inserting embeddings into collection '%s': %s", collection_name, e)
        raise

def search_embeddings(
    collection_name: str, query_vector: list, top_k: int = 5, query_filter: dict = None
):
    """
    Search for the nearest neighbors of a given query vector in the specified Qdrant collection.

    Args:
        collection_name (str): The Qdrant collection name.
        query_vector (list): The query embedding vector.
        top_k (int): The number of nearest neighbors to return.
        query_filter (dict, optional): A dictionary for filtering the search.

    Returns:
        A list of search results from Qdrant.
    """
    try:
        client = get_qdrant_client()
        filter_obj = None
        if query_filter:
            # Build a Filter object from the dictionary.
            filter_obj = Filter(**query_filter)
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=filter_obj,
        )
        logger.info("Search in collection '%s' returned %d results.", collection_name, len(results))
        return results
    except Exception as e:
        logger.exception("Error searching embeddings in collection '%s': %s", collection_name, e)
        raise

def get_extracted_text_from_qdrant(file_hash: str, collection_name: str) -> str:
    """
    Search for a document in Qdrant by its file hash and return the stored extracted text.
    Returns an empty string if not found.
    """
    try:
        client = get_qdrant_client()
        # Build a filter to search by file_hash in the payload
        filter_payload = {
            "must": [
                {"key": "file_hash", "match": {"value": file_hash}}
            ]
        }
        results = client.search(
            collection_name=collection_name,
            query_vector=[0.0] * config.get("qdrant", {}).get("vector_size", 768),
            limit=1,
            query_filter=Filter(**filter_payload)
        )
        if results and results[0].payload.get("extracted_text"):
            logger.info("Found cached extracted text for file hash %s.", file_hash)
            return results[0].payload.get("extracted_text")
        else:
            logger.debug("No cached extracted text found for file hash %s.", file_hash)
            return ""
    except Exception as e:
        logger.exception("Error retrieving extracted text from Qdrant for file hash '%s': %s", file_hash, e)
        return ""