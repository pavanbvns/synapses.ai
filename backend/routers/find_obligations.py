# backend/routers/find_obligations.py

import logging
import uuid
import threading
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from backend.utils.config import config
from backend.utils.document_parser import extract_text_from_file
from backend.utils.utils import validate_file, save_file_to_disk, compute_file_hash
from backend.utils.vectors import (
    get_extracted_text_from_qdrant,
    insert_embeddings,
    create_collection as ensure_collection,
)
from backend.utils.chatbot import chatbot_instance
from backend.models.db.job import create_job, update_job

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/find_obligations")
async def find_obligations(file: UploadFile = File(...)):
    """
    Extract all obligations from an uploaded document.

    Workflow:
      1. Validate the uploaded file.
      2. Compute the file hash and check Qdrant for cached extracted text.
      3. If not cached:
           a. Generate a UUID tag and save the file.
           b. Depending on configuration (vision vs. text model), either extract text using OCR and text extraction or decode the file bytes.
      4. Immediately generate obligations extraction by calling the chatbot’s ask_question_threadsafe method with a prompt that instructs to output ONLY a JSON array of obligations.
      5. In the background, compute the embedding and store file metadata in Qdrant if the file was not already cached.
      6. Return the job ID and the obligations extracted.
    """
    job_id = None
    try:
        job_id = create_job("Find Obligations")

        if not validate_file(file.filename):
            raise HTTPException(status_code=400, detail="Unsupported file type.")
        file_bytes = await file.read()
        size_limit = config.get("allowed_file_size_limit", 10 * 1024 * 1024)
        if len(file_bytes) > size_limit:
            raise HTTPException(
                status_code=400, detail="File size exceeds allowed limit."
            )

        file_hash = compute_file_hash(file_bytes)
        logger.debug("Computed file hash for '%s': %s", file.filename, file_hash)

        collection_name = config.get("qdrant", {}).get(
            "collection_name", "default_collection"
        )
        cached_text = get_extracted_text_from_qdrant(file_hash, collection_name)

        if cached_text:
            logger.info(
                "File '%s' already processed; using cached extracted text.",
                file.filename,
            )
            extracted_text = cached_text
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
                logger.info("Saved file as '%s' for text extraction.", file_path)
                extracted_text = extract_text_from_file(file_path, parse_images=True)
                logger.info(
                    "Extracted text (length=%d) from '%s'.",
                    len(extracted_text),
                    file_path,
                )

        # Prepare the prompt to extract obligations
        obligations_prompt = (
            f"Document text: {extracted_text}\n"
            "Identify and extract all obligations from the provided document. For each obligation, extract the following attributes:\n"
            "- Obligation Summary\n"
            "- Obligation Type (choose from: Payment, Delivery, Service, Warranty/Guarantee, Intellectual Property, Termination, Other)\n"
            "- Obligation Start Date (if specified, otherwise 'NOT SPECIFIED')\n"
            "- Obligation End Date (if specified, otherwise 'NOT SPECIFIED')\n"
            "- Obligation Recurrence (Yes/No)\n"
            "- Obligation Recurrence Frequency (if recurring, e.g., monthly, weekly, daily; otherwise 'NOT APPLICABLE')\n"
            "- Obligation Associated Risk Factor (High, Medium, Low, or No Risk)\n"
            "Output ONLY a JSON array where each element is a JSON object with the keys: "
            "'Obligation Summary', 'Obligation Type', 'Obligation Start Date', 'Obligation End Date', "
            "'Obligation Recurrence', 'Obligation Recurrence Frequency', 'Obligation Associated Risk Factor'."
        )

        obligations_answer = chatbot_instance.ask_question_threadsafe(
            extracted_text, obligations_prompt, "specific"
        )

        update_job(job_id, "Completed")

        # If file was not cached, schedule a background task to compute embedding and save metadata
        if not cached_text:
            llama_host = config.get("llama_server_host", "127.0.0.1")
            llama_port = int(config.get("llama_server_port", 8080))

            def background_embedding_task():
                from backend.utils.vectors import get_embedding

                try:
                    embedding = get_embedding(extracted_text, llama_host, llama_port)
                    ensure_collection(collection_name, vector_size=len(embedding))
                    doc_point = {
                        "id": unique_id,
                        "vector": embedding,
                        "payload": {
                            "file_hash": file_hash,
                            "extracted_text": extracted_text,
                            "filename": file.filename,
                        },
                    }
                    insert_embeddings(collection_name, [doc_point])
                    logger.info(
                        "Background: Inserted file '%s' in Qdrant (UUID=%s).",
                        file.filename,
                        unique_id,
                    )
                except Exception as be:
                    logger.exception(
                        "Background task error in saving file to Qdrant: %s", be
                    )

            threading.Thread(target=background_embedding_task, daemon=True).start()

        return {"job_id": job_id, "obligations": obligations_answer}
    except Exception as e:
        if job_id:
            update_job(job_id, "Aborted")
        logger.exception("Error in /find_obligations endpoint: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
