# backend/routers/chat.py

import logging
import uuid
import threading
from typing import Optional, List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from backend.utils.config import config
from backend.utils.document_parser import extract_text_from_file
from backend.utils.utils import validate_file, save_file_to_disk, compute_file_hash
from backend.models.db.job import create_job, update_job
from backend.utils.chatbot import chatbot_instance
from backend.utils.vectors import (
    get_extracted_text_from_qdrant,
    background_save_to_qdrant,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory chat session storage
chat_sessions = {}


@router.post("/chat_with_docs")
async def chat_with_docs(
    new_message: str = Form(...),
    file: Optional[UploadFile] = File(None),
    session_id: Optional[str] = Form(None),
):
    """
    Chat with document content.

    Workflow:
      1. If a file is uploaded, validate it, extract its text, and check Qdrant for cached data.
         If the document is new, launch a background thread to store embeddings.
      2. Retrieve the conversation session or create a new one.
      3. Generate a response using chatbot inference on combined context.
      4. Return session and job metadata.
    """
    job_id = None
    try:
        job_id = create_job("Chat with Documents")
        extracted_text = ""

        if file:
            if not validate_file(file.filename):
                raise HTTPException(status_code=400, detail="Unsupported file type.")
            file_bytes = await file.read()
            allowed_size = config.get("allowed_file_size_limit", 10 * 1024 * 1024)
            if len(file_bytes) > allowed_size:
                raise HTTPException(
                    status_code=400, detail="File size exceeds allowed limit."
                )

            file_hash = compute_file_hash(file_bytes)
            collection_name = config.get("qdrant", {}).get(
                "collection_name", "default_collection"
            )
            cached_text = get_extracted_text_from_qdrant(file_hash, collection_name)

            if cached_text:
                logger.info(
                    "File '%s' already processed; using cached content.", file.filename
                )
                extracted_text = cached_text
            else:
                unique_id = str(uuid.uuid4())
                processed_dir = config.get("processed_dir", "processed_dir")
                temp_filename = f"{unique_id}_{file.filename}"
                file_path = save_file_to_disk(file_bytes, processed_dir, temp_filename)
                logger.info("Saved file to '%s' for content extraction.", file_path)

                extracted_text = extract_text_from_file(file_path, parse_images=True)
                logger.info(
                    "Extracted %d characters from '%s'.", len(extracted_text), file_path
                )

                # Launch background ingestion thread
                llama_host = config.get("llama_server_host", "127.0.0.1")
                llama_port = int(config.get("llama_server_port", 8080))
                threading.Thread(
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
                ).start()
                logger.info("Background ingestion thread launched.")

        # Initialize or retrieve session history
        if session_id and session_id in chat_sessions:
            conversation_history = chat_sessions[session_id]
        else:
            session_id = str(uuid.uuid4())
            conversation_history = []
            chat_sessions[session_id] = conversation_history

        conversation_history.append(new_message)
        context_text = extracted_text.strip() if extracted_text else ""
        prompt_input = context_text + "\n" + "\n".join(conversation_history)

        response = chatbot_instance.chat_threadsafe(
            prompt_input.encode("utf-8"), conversation_history, new_message
        )
        conversation_history.append(response)

        update_job(job_id, "Completed")
        return {"job_id": job_id, "session_id": session_id, "response": response}

    except Exception as e:
        if job_id:
            update_job(job_id, "Aborted")
        logger.exception("Error in /chat_with_docs endpoint: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
