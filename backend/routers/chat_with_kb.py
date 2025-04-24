# backend/routers/chat_kb.py

import logging
import threading
import time
from typing import List, Optional

from fastapi import APIRouter, Form, HTTPException, Request, Query
from fastapi.responses import StreamingResponse

from backend.utils.config import config
from backend.utils.vectors import search_embeddings
from backend.utils.chatbot import chatbot_instance
from backend.models.db.job import create_job, update_job
from backend.utils.utils import get_embedding

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat_with_kb", tags=["Chat with Knowledge Base"])


@router.post("/")
async def chat_with_kb(
    request: Request,
    user_query: str = Form(...),
    conversation_history: Optional[List[str]] = Form(None),
    top_k: int = Query(3, description="Number of top documents to retrieve"),
):
    """
    Initiate a conversation using the knowledge base.
    This endpoint performs embedding-based retrieval and uses LLM streaming response.
    """
    job_id = None

    try:
        job_id = create_job("Chat with Knowledge Base")

        llama_host = config.get("llama_server_host", "127.0.0.1")
        llama_port = int(config.get("llama_server_port", 8080))
        collection_name = config.get("qdrant", {}).get(
            "collection_name", "default_collection"
        )
        vector_size = config.get("qdrant", {}).get("vector_size", 4096)

        # Sanitize user query (optional but recommended)
        cleaned_query = " ".join(user_query.strip().split())

        # Compute query embedding with timeout buffer
        try:
            query_embedding = get_embedding(cleaned_query, llama_host, llama_port)
        except Exception as embed_err:
            logger.error("Failed to generate embedding: %s", embed_err)
            raise HTTPException(
                status_code=500, detail="Unable to generate embedding for query."
            )

        if not query_embedding:
            raise HTTPException(status_code=500, detail="Query embedding is empty.")

        # Search top K relevant context
        results = search_embeddings(collection_name, query_embedding, top_k=top_k)
        if not results:
            update_job(job_id, "Completed")
            return {
                "job_id": job_id,
                "answer": "I'm not sure about that. Please contact support.",
            }

        # Merge retrieved context from results
        retrieved_texts = [
            hit.payload.get("extracted_text", "")
            for hit in results
            if hit.payload.get("extracted_text")
        ]
        combined_context = "\n\n".join(retrieved_texts)

        # Enforce LLM max context safety
        max_context_chars = int(config.get("max_embedding_input_length", 1024)) * 4
        if len(combined_context) > max_context_chars:
            combined_context = combined_context[:max_context_chars]
            logger.warning("Context truncated to comply with LLM limits.")

        # Build prompt for context-grounded QA
        prompt = (
            f"Use only the following context to answer the question. If the context is insufficient, "
            f"respond with 'I'm not sure. Please contact support.'\n\n"
            f"Context:\n{combined_context}\n\n"
            f"Question: {cleaned_query}\n\nAnswer:"
        )

        # Stream LLM response
        def stream_generator():
            try:
                for chunk in chatbot_instance.stream_chat(
                    combined_context, cleaned_query
                ):
                    yield chunk
            except Exception as ex:
                logger.exception("Error during LLM streaming: %s", ex)
                yield "\n[ERROR generating response]\n"

        update_job(job_id, "Completed")
        return StreamingResponse(stream_generator(), media_type="text/plain")

    except Exception as e:
        if job_id:
            update_job(job_id, "Aborted")
        logger.exception("Exception in /chat_with_kb: %s", e)
        raise HTTPException(status_code=500, detail="Internal error during chat task.")
