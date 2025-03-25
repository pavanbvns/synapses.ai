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
from backend.utils.vectors import get_extracted_text_from_qdrant

# In-memory chat session storage (for demonstration; consider persisting in a database for production)
chat_sessions = {}

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat_with_docs")
async def chat_with_docs(
    new_message: str = Form(...),
    file: Optional[UploadFile] = File(None),
    session_id: Optional[str] = Form(None),
):
    """
    Chat with document content.

    Workflow:
      1. If a file is provided, validate and read its bytes, compute its hash, and check Qdrant for cached extracted text.
         If not cached, save the file and extract its text.
      2. Retrieve the conversation history using the provided session_id; if absent, create a new session.
      3. Append the new message to the conversation history and generate a response using the chatbot.
      4. Update the conversation history and return the job ID, session ID, and response.
    """
    job_id = None
    try:
        job_id = create_job("Chat with Documents")

        # Initialize extracted text as empty
        extracted_text = ""

        # Process the uploaded file if provided
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
                    "File '%s' already processed; using cached text.", file.filename
                )
                extracted_text = cached_text
            else:
                unique_id = str(uuid.uuid4())
                processed_dir = config.get("processed_dir", "processed_dir")
                temp_filename = f"{unique_id}_{file.filename}"
                file_path = save_file_to_disk(file_bytes, processed_dir, temp_filename)
                logger.info("Saved file as '%s' for text extraction.", file_path)
                extracted_text = extract_text_from_file(file_path, parse_images=True)
                logger.info(
                    "Extracted text (length=%d) from '%s'.",
                    len(extracted_text),
                    file_path,
                )
                # (Background task for computing embeddings and storing metadata may be launched here if desired)

        # Retrieve or initialize the conversation history for the session.
        if session_id and session_id in chat_sessions:
            conversation_history = chat_sessions[session_id]
        else:
            session_id = str(uuid.uuid4())
            conversation_history = []
            chat_sessions[session_id] = conversation_history

        # Append the new message to conversation history.
        conversation_history.append(new_message)

        # Prepare context text: if file text exists, include it; otherwise use only conversation history.
        context_text = extracted_text.strip() if extracted_text else ""
        prompt_input = context_text + "\n" + "\n".join(conversation_history)

        # Generate response using the chatbot.
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
