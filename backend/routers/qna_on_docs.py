# backend/routers/qna_on_docs.py

import uuid
import threading
import logging
import json
from typing import List
from enum import Enum
from fastapi import Request, APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from backend.models.db.job import create_job, update_job
from backend.utils.config import config
from backend.utils.utils import (
    validate_file,
    compute_file_hash,
    save_file_to_disk,
)
from backend.utils.vectors import (
    get_extracted_text_from_qdrant,
    background_save_to_qdrant,
)
from backend.utils.document_parser import (
    extract_text_from_file,
    extract_text_from_image,
    cleanup_memory,
    convert_pdf_to_images,
)
from backend.utils.chatbot import chatbot_instance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qna_on_docs", tags=["QnA on Documents"])


class ResponseType(str, Enum):
    specific = "specific"
    elaborate = "elaborate"


# A Pydantic model for each Q&A request
class QAPair(BaseModel):
    question: str
    response_type: ResponseType


@router.post("/qna_on_docs")
async def qna_on_docs(
    request: Request,
    files: List[UploadFile] = File(...),
    qna_items_str: str = Form(...),
):
    """
    Perform Q&A on one or more documents.

    Workflow:
      1. For each uploaded file:
         - Validate file type and size.
         - Read its bytes and compute a file hash.
         - Check Qdrant for cached extracted text.
             • If found, use the cached text.
             • Otherwise, save the file with a UUID prefix, extract text (or decode bytes if using a vision model),
               and schedule a background task to compute its embedding and store metadata in Qdrant.
      2. Combine the extracted text from all files.
      3. For each Q&A pair (provided as a JSON array in the form field "qna_items_str"):
         - If the response type is "specific", modify the prompt to instruct a concise answer in a single line.
         - Call the chatbot to obtain the answer.
      4. Return the job ID and the list of Q&A pairs.
    """
    job_id = None
    try:
        # Create a job record for tracking
        job_id = create_job("Q&A on Documents")

        # Parse the JSON string into a list of QAPair objects.
        try:
            qna_dicts = json.loads(qna_items_str)
            qna_items = [QAPair(**item) for item in qna_dicts]
        except Exception as parse_err:
            raise HTTPException(
                status_code=400, detail=f"Invalid JSON for Q&A pairs: {str(parse_err)}"
            )

        file_texts = []  # Will hold extracted text from each file.
        background_tasks = []  # Tasks for saving to Qdrant later.

        # Process each uploaded file.
        for file in files:
            if not validate_file(file.filename):
                raise HTTPException(
                    status_code=400, detail=f"Unsupported file type: {file.filename}"
                )
            file_bytes = await file.read()
            allowed_file_size = config.get("allowed_file_size_limit", 10 * 1024 * 1024)
            if len(file_bytes) > allowed_file_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"File size exceeds allowed limit: {file.filename}",
                )
            file_hash = compute_file_hash(file_bytes)
            collection_name = config.get("qdrant", {}).get(
                "collection_name", "default_collection"
            )
            cached_text = get_extracted_text_from_qdrant(file_hash, collection_name)

            if cached_text:
                # File already processed; use the cached text.
                file_texts.append(cached_text)
            else:
                unique_id = str(uuid.uuid4())
                processed_dir = config.get("processed_dir", "processed_dir")
                temp_filename = f"{unique_id}_{file.filename}"
                file_path = save_file_to_disk(file_bytes, processed_dir, temp_filename)
                # Determine if using a vision model.
                model_is_vision = config.get("model_type_is_vision", False)
                if model_is_vision:
                    extracted_text = file_bytes.decode("utf-8", errors="replace")
                else:
                    extracted_text = extract_text_from_file(
                        file_path
                        # , parse_images=True
                    )
                file_texts.append(extracted_text)
                # Schedule background task to compute embedding and save file metadata to Qdrant.
                background_tasks.append(
                    (
                        file_bytes,
                        file_hash,
                        file.filename,
                        processed_dir,
                        unique_id,
                        extracted_text,
                    )
                )

        # Combine text from all files.
        combined_text = "\n".join(file_texts)

        # For each Q&A pair, generate an answer.
        qa_results = []

        for qa in qna_items:
            try:
                answer = chatbot_instance.ask_question_threadsafe(
                    combined_text,
                    qa.question.strip(),
                    qa.response_type.value,
                )
            except Exception as e:
                answer = f"Error generating answer: {str(e)}"
            qa_results.append(
                {
                    "question": qa.question,
                    "answer": answer,
                    "response_type": qa.response_type.value,
                }
            )

        update_job(job_id, "Completed")

        # Launch background tasks for each file that was not previously processed.
        llama_host = config.get("llama_server_host", "127.0.0.1")
        llama_port = int(config.get("llama_server_port", 8080))
        for task in background_tasks:
            (
                file_bytes,
                file_hash,
                filename,
                processed_dir,
                unique_id,
                extracted_text,
            ) = task
            thread = threading.Thread(
                target=background_save_to_qdrant,
                args=(
                    file_bytes,
                    file_hash,
                    filename,
                    processed_dir,
                    unique_id,
                    extracted_text,
                    llama_host,
                    llama_port,
                    collection_name,
                ),
                daemon=True,
            )
            thread.start()
            logger.info(
                "Launched background task for saving file '%s' to Qdrant.", filename
            )

        return {"job_id": job_id, "qa_pairs": qa_results}
    except Exception as e:
        if job_id is not None:
            update_job(job_id, "Aborted")
        logger.exception("Error in /qna_on_docs endpoint: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
