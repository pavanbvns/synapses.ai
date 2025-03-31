# backend/routers/ingest.py

import os
import uuid
import threading
import logging
import shutil
from typing import List, Optional

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
    BackgroundTasks,
    Query,
)
from backend.models.db.job import create_job, update_job
from backend.utils.config import config
from backend.utils.document_parser import extract_text_from_file, cleanup_memory
from backend.utils.utils import validate_file, compute_file_hash, save_file_to_disk
from backend.utils.vectors import (
    insert_embeddings,
    get_extracted_text_from_qdrant,
    check_or_create_collection,
    get_embedding,
    get_qdrant_client,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["Knowledge Base Ingestion"])


def ingest_file(file_bytes: bytes, filename: str, processed_dir: str) -> (str, str):
    """
    Save the file, extract text, and return the file hash and extracted text.
    """
    file_hash = compute_file_hash(file_bytes)
    file_path = save_file_to_disk(
        file_bytes, processed_dir, f"{uuid.uuid4()}_{filename}"
    )
    extracted_text = extract_text_from_file(file_path)
    return file_hash, extracted_text


def ingest_folder(
    folder_path: str, processed_dir: str, allowed_extensions: List[str]
) -> List[dict]:
    """
    Recursively iterate over files in folder_path, ingest each valid file.
    Returns a list of ingestion results.
    """
    results = []
    for root, dirs, files in os.walk(folder_path):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in allowed_extensions:
                full_path = os.path.join(root, fname)
                try:
                    with open(full_path, "rb") as f:
                        file_bytes = f.read()
                    file_hash, extracted_text = ingest_file(
                        file_bytes, fname, processed_dir
                    )
                    results.append(
                        {
                            "filename": fname,
                            "file_hash": file_hash,
                            "extracted_text": extracted_text,
                        }
                    )
                    logger.info("Ingested file: %s", full_path)
                except Exception as e:
                    logger.error("Failed to ingest file %s: %s", full_path, e)
    return results


def ingest_from_url(url: str, processed_dir: str) -> dict:
    """
    Download or extract content from a URL.
    This is a simple implementation. In production, you might want to
    use libraries like BeautifulSoup to extract text from web pages.
    """
    import requests

    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch URL: {url}")
        # Use the raw HTML as text (or improve extraction logic)
        text = response.text
        # Use URL as filename surrogate.
        filename = url.split("/")[-1] or "downloaded_content.html"
        file_bytes = text.encode("utf-8")
        file_hash = compute_file_hash(file_bytes)
        # Optionally, save the file
        file_path = save_file_to_disk(file_bytes, processed_dir, filename)
        extracted_text = extract_text_from_file(file_path)
        return {
            "filename": filename,
            "file_hash": file_hash,
            "extracted_text": extracted_text,
        }
    except Exception as e:
        logger.error("Failed to ingest from URL %s: %s", url, e)
        raise HTTPException(status_code=400, detail=f"Failed to ingest URL: {e}")


def upsert_to_qdrant(file_hash: str, filename: str, extracted_text: str):
    """
    Compute embedding and upsert the document into Qdrant.
    """
    collection_name = config.get("qdrant", {}).get(
        "collection_name", "default_collection"
    )
    vector_size = config.get("qdrant", {}).get("vector_size", 4096)
    check_or_create_collection(collection_name, vector_size=vector_size)
    # Get embedding
    llama_host = config.get("llama_server_host", "127.0.0.1")
    llama_port = int(config.get("llama_server_port", 8080))
    embedding = get_embedding(extracted_text, llama_host, llama_port)
    if not embedding or len(embedding) != vector_size:
        raise Exception(f"Embedding dimension error for file {filename}")
    # Prepare document point
    doc_point = {
        "id": str(uuid.uuid4()),
        "vector": embedding,
        "payload": {
            "file_hash": file_hash,
            "extracted_text": extracted_text,
            "filename": filename,
        },
    }
    # Upsert to Qdrant
    insert_embeddings(collection_name, [doc_point])
    logger.info(
        "Upserted embedding for file %s into collection %s.", filename, collection_name
    )


@router.post("/")
async def ingest_knowledge(
    background_tasks: BackgroundTasks,
    files: Optional[List[UploadFile]] = File(None),
    folder_path: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
):
    """
    Ingest documents into the knowledge base (Qdrant).

    Three ingestion modes:
    1. Direct file upload.
    2. Folder path (server-side).
    3. URL to download content.

    For each document, the process computes the file hash, extracts text,
    and upserts embeddings into Qdrant.
    """
    job_id = create_job("Ingest Knowledge Base")
    processed_dir = config.get("processed_dir", "./data/processed_dir")
    allowed_extensions = config.get(
        "allowed_file_extensions",
        [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".tiff", ".png"],
    )

    ingested_count = 0
    try:
        ingest_results = []

        # 1. Direct file upload ingestion
        if files:
            for file in files:
                if not validate_file(file.filename):
                    logger.error("Unsupported file type: %s", file.filename)
                    continue
                file_bytes = await file.read()
                file_hash, extracted_text = ingest_file(
                    file_bytes, file.filename, processed_dir
                )
                # Avoid duplicate ingestion if already exists in Qdrant
                cached = get_extracted_text_from_qdrant(file_hash, allowed_extensions)
                if not cached:
                    upsert_to_qdrant(file_hash, file.filename, extracted_text)
                ingest_results.append({"filename": file.filename, "method": "upload"})
                ingested_count += 1

        # 2. Folder ingestion
        if folder_path:
            if not os.path.isdir(folder_path):
                raise HTTPException(
                    status_code=400, detail="Provided folder path is not valid."
                )
            folder_results = ingest_folder(
                folder_path, processed_dir, allowed_extensions
            )
            for result in folder_results:
                # Check for duplicates (this sample does not perform a full duplicate check)
                upsert_to_qdrant(
                    result["file_hash"], result["filename"], result["extracted_text"]
                )
                ingest_results.append(
                    {"filename": result["filename"], "method": "folder"}
                )
                ingested_count += 1

        # 3. URL ingestion
        if url:
            url_result = ingest_from_url(url, processed_dir)
            upsert_to_qdrant(
                url_result["file_hash"],
                url_result["filename"],
                url_result["extracted_text"],
            )
            ingest_results.append({"filename": url_result["filename"], "method": "url"})
            ingested_count += 1

        update_job(job_id, "Completed")
        # Optionally, run cleanup in the background.
        background_tasks.add_task(cleanup_memory)
        return {
            "job_id": job_id,
            "ingested_count": ingested_count,
            "details": ingest_results,
        }

    except Exception as e:
        update_job(job_id, "Aborted")
        logger.exception("Error in /ingest endpoint: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
