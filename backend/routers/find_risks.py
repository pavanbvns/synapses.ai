# backend/routers/find_risks.py

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


@router.post("/find_risks")
async def find_risks(file: UploadFile = File(...)):
    """
    Extract and list all risks from an uploaded document.

    Workflow:
      1. Validate the uploaded file.
      2. Compute the file hash and check Qdrant for cached extracted text.
      3. If not cached:
           a. Generate a UUID and save the file.
           b. Depending on configuration (vision vs. text model), either extract text using OCR (if enabled) or decode the raw bytes.
      4. Generate risks extraction by calling the chatbot with a prompt that instructs to output ONLY a JSON array of risks.
         Each JSON object must have the keys: 'Risk Summary', 'Risk Category', and 'Risk Severity'.
      5. In the background, compute the embedding and store file metadata in Qdrant for future reuse.
      6. Return the job ID and the risks extracted.
    """
    job_id = None
    try:
        job_id = create_job("Find Risks")

        if not validate_file(file.filename):
            raise HTTPException(status_code=400, detail="Unsupported file type.")

        file_bytes = await file.read()
        allowed_size = config.get("allowed_file_size_limit", 10 * 1024 * 1024)
        if len(file_bytes) > allowed_size:
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

        # Prepare prompt to extract risks from the document.
        risk_prompt = (
            f"Document text: {extracted_text}\n"
            "Identify and list all risks present in the document. A risk is a potential negative consequence or issue arising from the obligations or other aspects of the document.\n"
            "For each risk, output a JSON object with the following keys:\n"
            "  - Risk Summary: A concise summary of the risk.\n"
            "  - Risk Category: Choose one from Financial, Operational, Legal, Reputational, Strategic, or Other.\n"
            "  - Risk Severity: One of High, Medium, or Low.\n"
            "Output ONLY a JSON array of such objects without any additional commentary."
        )

        risks_answer = chatbot_instance.ask_question_threadsafe(
            extracted_text, risk_prompt, "specific"
        )

        update_job(job_id, "Completed")

        # Launch a background task to compute the embedding and store metadata if not already cached.
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
                        "Background: Inserted file '%s' into Qdrant (UUID=%s).",
                        file.filename,
                        unique_id,
                    )
                except Exception as be:
                    logger.exception(
                        "Background task error while saving file to Qdrant: %s", be
                    )

            threading.Thread(target=background_embedding_task, daemon=True).start()

        return {"job_id": job_id, "risks": risks_answer}
    except Exception as e:
        if job_id:
            update_job(job_id, "Aborted")
        logger.exception("Error in /find_risks endpoint: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
