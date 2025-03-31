# backend/routers/gen_summary.py

import logging
import uuid
import threading

from fastapi import APIRouter, File, Form, UploadFile, HTTPException

# Import  utility modules
from backend.utils.utils import (
    validate_file,
    save_file_to_disk,
    compute_file_hash,
)
from backend.utils.document_parser import extract_text_from_file
from backend.utils.config import config
from backend.utils.vectors import (
    get_extracted_text_from_qdrant,
    background_save_to_qdrant,
)
from backend.utils.vectors import (
    create_collection as ensure_collection,
)
from backend.utils.chatbot import chatbot_instance


# Import  DB job logic
from backend.models.db.job import create_job, update_job

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/gen_summary")
async def generate_file_summary(
    file: UploadFile = File(...), min_words: int = Form(50), max_words: int = Form(150)
):
    """
    Generate a summary for an uploaded document.

    Workflow:
      1. Validate file type and size.
      2. Compute file hash and check Qdrant for cached extracted text.
      3. If no cached text exists:
           a. Tag the file with a UUID.
           b. Depending on configuration, extract text from the file (for text models) or decode raw bytes (for vision models).
           c. Immediately generate a summary via llama‑server.
           d. In the background, compute the embedding and store file metadata and embedding in Qdrant.
      4. Return the generated summary.
    """
    job_id = None
    try:
        job_id = create_job("Generate File Summary")
        if not validate_file(file.filename):
            raise HTTPException(status_code=400, detail="Unsupported file type.")
        file_bytes = await file.read()
        allowed_file_size = config.get("allowed_file_size_limit", 10 * 1024 * 1024)
        if len(file_bytes) > allowed_file_size:
            raise HTTPException(
                status_code=400, detail="File size exceeds allowed limit."
            )

        file_hash = compute_file_hash(file_bytes)
        logger.debug("Computed file hash: %s", file_hash)

        collection_name = config.get("qdrant", {}).get(
            "collection_name", "default_collection"
        )
        cached_text = get_extracted_text_from_qdrant(file_hash, collection_name)
        # print("---------------------------------------------------------")
        # print("cached text: \n%s", cached_text)
        # print("---------------------------------------------------------")
        if cached_text:
            logger.info(
                "File '%s' already processed; using cached extracted text.",
                file.filename,
            )
            extracted_text = cached_text
            logger.info("Extracted text: \n%s", extracted_text)
        else:
            unique_id = str(uuid.uuid4())
            processed_dir = config.get("processed_dir", "processed_dir")
            model_is_vision = config.get("model_type_is_vision", False)
            if model_is_vision:
                logger.info("Configured to use vision model; skipping text extraction.")
                extracted_text = file_bytes.decode("utf-8", errors="replace")
            else:
                temp_filename = f"{unique_id}_{file.filename}"
                file_path = save_file_to_disk(file_bytes, processed_dir, temp_filename)
                logger.info("Saved file as %s for text extraction.", file_path)

                extracted_text = extract_text_from_file(file_path)
                print("Extracted text: \n", extracted_text)
                logger.info(
                    "Extracted text of length %d from '%s'.",
                    len(extracted_text),
                    file_path,
                )
                # logger.info("Extracted text: \n", extracted_text)
        # Generate summary immediately using the chatbot instance.
        model_is_vision = config.get("model_type_is_vision", False)
        if model_is_vision:
            summary = chatbot_instance.generate_summary_threadsafe(
                file_bytes, min_words, max_words
            )
        else:
            logger.info("Extracted text: \n", extracted_text)

            summary = chatbot_instance.generate_summary_threadsafe(
                # extracted_text.encode("utf-8"),
                extracted_text,
                min_words,
                max_words,
            )
        logger.info("Generated summary for file '%s'.", file.filename)
        update_job(job_id, "Completed")

        # If file was not previously processed, launch a background task to compute embeddings and save metadata.
        if not cached_text:
            llama_host = config.get("llama_server_host", "127.0.0.1")
            llama_port = int(config.get("llama_server_port", 8080))
            background_thread = threading.Thread(
                target=background_save_to_qdrant,
                args=(
                    file_bytes,
                    file_hash,
                    file.filename,
                    processed_dir,
                    unique_id,
                    extracted_text,
                    llama_host,
                    llama_port,
                    collection_name,
                ),
                daemon=True,
            )
            background_thread.start()
            logger.info("Launched background task for saving file to Qdrant.")
        return {"job_id": job_id, "summary": summary}
    except Exception as e:
        if job_id is not None:
            update_job(job_id, "Aborted")
        logger.exception("Error in /gen_summary endpoint: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
