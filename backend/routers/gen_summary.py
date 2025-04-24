# backend/routers/gen_summary.py

import logging
import uuid
import threading

from fastapi import APIRouter, File, Form, UploadFile, HTTPException

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
from backend.utils.chatbot import chatbot_instance
from backend.models.db.job import create_job, update_job

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/gen_summary")
async def generate_file_summary(
    file: UploadFile = File(...), min_words: int = Form(50), max_words: int = Form(150)
):
    """
    Generate a summary for an uploaded document.
    1. Validate the file.
    2. Check Qdrant for cached text by file hash.
    3. If uncached:
        - Save and extract text based on model type.
        - Generate summary.
        - Launch background thread to persist embedding to Qdrant.

    """
    # job_id = None
    try:
        # job_id = create_job("Generate File Summary")

        if not validate_file(file.filename):
            raise HTTPException(status_code=400, detail="Unsupported file type.")

        file_bytes = await file.read()
        allowed_size = config.get("allowed_file_size_limit", 10 * 1024 * 1024)
        if len(file_bytes) > allowed_size:
            raise HTTPException(
                status_code=400, detail="File size exceeds allowed limit."
            )

        file_hash = compute_file_hash(file_bytes)
        logger.debug("Computed SHA256 file hash: %s", file_hash)

        collection_name = config.get("qdrant", {}).get(
            "collection_name", "default_collection"
        )
        cached_text = get_extracted_text_from_qdrant(file_hash, collection_name)

        if cached_text:
            logger.info("Using cached extracted text for '%s'.", file.filename)
            extracted_text = cached_text
        else:
            unique_id = str(uuid.uuid4())
            processed_dir = config.get("processed_dir", "processed_dir")
            model_is_vision = config.get("model_type_is_vision", False)

            if model_is_vision:
                logger.info("Vision model in use — skipping OCR/text extraction.")
                extracted_text = file_bytes.decode("utf-8", errors="replace")
            else:
                temp_filename = f"{unique_id}_{file.filename}"
                file_path = save_file_to_disk(file_bytes, processed_dir, temp_filename)
                logger.info("Saved file for extraction: %s", file_path)

                extracted_text = extract_text_from_file(file_path)
                logger.debug("Extracted text preview:\n%s", extracted_text[:300])

        # Generate summary using chatbot
        model_is_vision = config.get("model_type_is_vision", False)
        if model_is_vision:
            summary = chatbot_instance.generate_summary_threadsafe(
                file_bytes, min_words, max_words
            )
        else:
            summary = chatbot_instance.generate_summary_threadsafe(
                extracted_text, min_words, max_words
            )

        # update_job(job_id, "Completed")
        logger.info("Generated summary for file '%s'.", file.filename)

        # Background persistence if new file
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
            logger.info(
                "Background thread launched to save to Qdrant for '%s'.", file.filename
            )
        return {"summary": summary}
        # return {"job_id": job_id, "summary": summary}

    except Exception as e:
        # if job_id:
        # update_job(job_id, "Aborted")
        logger.exception("Unhandled error in /gen_summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
