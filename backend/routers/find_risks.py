# backend/routers/find_risks.py

import logging
import uuid
import threading
from fastapi import APIRouter, UploadFile, File, HTTPException
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
      3. If not cached, extract text using OCR or decode raw bytes based on model type.
      4. Generate risks using prompt-based extraction.
      5. Background: Compute embeddings and push metadata into Qdrant.
      6. Return the job ID and extracted risk results.
    """
    job_id = None
    try:
        job_id = create_job("Find Risks")

        if not validate_file(file.filename):
            raise HTTPException(status_code=400, detail="Unsupported file type.")

        file_bytes = await file.read()
        max_size = config.get("allowed_file_size_limit", 10 * 1024 * 1024)
        if len(file_bytes) > max_size:
            raise HTTPException(status_code=400, detail="File size exceeds limit.")

        file_hash = compute_file_hash(file_bytes)
        collection_name = config.get("qdrant", {}).get(
            "collection_name", "default_collection"
        )
        cached_text = get_extracted_text_from_qdrant(file_hash, collection_name)

        if cached_text:
            logger.info("Using cached extracted text for file '%s'.", file.filename)
            extracted_text = cached_text
            unique_id = None
        else:
            unique_id = str(uuid.uuid4())
            processed_dir = config.get("processed_dir", "processed_dir")
            model_is_vision = config.get("model_type_is_vision", False)
            if model_is_vision:
                logger.info("Vision model enabled. Skipping OCR.")
                extracted_text = file_bytes.decode("utf-8", errors="replace")
            else:
                temp_filename = f"{unique_id}_{file.filename}"
                file_path = save_file_to_disk(file_bytes, processed_dir, temp_filename)
                extracted_text = extract_text_from_file(file_path, parse_images=True)
                logger.info(
                    "Extracted %d characters of text from '%s'.",
                    len(extracted_text),
                    file.filename,
                )

        risk_prompt = f"""Document text: {extracted_text}
        Identify and list all risks present in the document. A risk is a potential negative consequence or issue arising from the obligations or other aspects of the document.
        For each risk, output a JSON object with the following keys:
        - Risk Summary: A concise summary of the risk.
        - Risk Category: Choose one from Financial, Operational, Legal, Reputational, Strategic, or Other.
        - Risk Severity: One of High, Medium, or Low.
        Output ONLY a JSON array of such objects without any additional commentary."""

        risks_answer = chatbot_instance.ask_question_threadsafe(
            extracted_text, risk_prompt, "specific"
        )
        update_job(job_id, "Completed")

        if not cached_text and unique_id:
            llama_host = config.get("llama_server_host", "127.0.0.1")
            llama_port = int(config.get("llama_server_port", 8080))

            def background_task():
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
                        "Background: Inserted embedding for '%s' (UUID=%s)",
                        file.filename,
                        unique_id,
                    )
                except Exception as be:
                    logger.exception(
                        "Background task failed for '%s': %s", file.filename, be
                    )

            threading.Thread(target=background_task, daemon=True).start()

        return {"job_id": job_id, "risks": risks_answer}

    except Exception as e:
        if job_id:
            update_job(job_id, "Aborted")
        logger.exception("Error in /find_risks: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
