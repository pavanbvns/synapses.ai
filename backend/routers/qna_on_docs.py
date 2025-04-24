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
from backend.utils.document_parser import extract_text_from_file
from backend.utils.chatbot import chatbot_instance

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/qna_on_docs", tags=["QnA on Documents"])


class ResponseType(str, Enum):
    specific = "specific"
    elaborate = "elaborate"


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
    """
    job_id = None
    try:
        job_id = create_job("Q&A on Documents")

        try:
            qna_dicts = json.loads(qna_items_str)
            qna_items = [QAPair(**item) for item in qna_dicts if item.get("question")]
            if not qna_items:
                raise ValueError("No valid Q&A pairs provided.")
        except Exception as parse_err:
            raise HTTPException(
                status_code=400, detail=f"Invalid Q&A JSON input: {str(parse_err)}"
            )

        collection_name = config.get("qdrant", {}).get(
            "collection_name", "default_collection"
        )
        processed_dir = config.get("processed_dir", "processed_dir")
        model_is_vision = config.get("model_type_is_vision", False)

        file_texts = []
        background_tasks = []

        for file in files:
            if not validate_file(file.filename):
                raise HTTPException(
                    status_code=400, detail=f"Unsupported file type: {file.filename}"
                )
            file_bytes = await file.read()
            if len(file_bytes) > config.get(
                "allowed_file_size_limit", 10 * 1024 * 1024
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"File size exceeds limit for: {file.filename}",
                )

            file_hash = compute_file_hash(file_bytes)
            cached_text = get_extracted_text_from_qdrant(file_hash, collection_name)

            if cached_text:
                file_texts.append(cached_text)
            else:
                unique_id = str(uuid.uuid4())
                file_path = save_file_to_disk(
                    file_bytes, processed_dir, f"{unique_id}_{file.filename}"
                )
                extracted_text = (
                    file_bytes.decode("utf-8", errors="replace")
                    if model_is_vision
                    else extract_text_from_file(file_path)
                )
                file_texts.append(extracted_text)
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

        combined_text = "\n".join(file_texts)
        qa_results = []

        for qa in qna_items:
            try:
                answer = chatbot_instance.ask_question_threadsafe(
                    combined_text, qa.question.strip(), qa.response_type.value
                )
            except Exception as e:
                logger.error("QA generation failed for question: %s", qa.question)
                answer = f"Error generating answer: {str(e)}"

            qa_results.append(
                {
                    "question": qa.question,
                    "answer": answer,
                    "response_type": qa.response_type.value,
                }
            )

        update_job(job_id, "Completed")

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
            threading.Thread(
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
            ).start()

        return {"job_id": job_id, "qa_pairs": qa_results}

    except Exception as e:
        if job_id:
            update_job(job_id, "Aborted")
        logger.exception("Error in /qna_on_docs endpoint: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
