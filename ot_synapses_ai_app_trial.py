import os
import uuid
import datetime
import logging
import time
import subprocess
import threading
import socket
from functools import wraps
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, APIRouter
from fastapi.responses import JSONResponse

from utils.config import config
from utils.chatbot import ThreadSafeChatBot
from utils.utils import (
    save_uploaded_file,
    load_file_bytes,
    validate_file,
    validate_file_size,
)
from utils.vectors import create_collection, insert_embeddings, search_embeddings
from models.db.job import SessionLocal, Job
from utils.document_parser import extract_text_from_file

# Configure global logger
logger = logging.getLogger("ot-synapses_app")
logging_level_str = config.get("logging_level", "DEBUG")
numeric_level = getattr(logging, logging_level_str.upper(), None)
if not isinstance(numeric_level, int):
    numeric_level = logging.DEBUG
logger.setLevel(numeric_level)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Global in-memory store for chat sessions
chat_sessions = {}

# Read the model path from config
model_path = config.get("model_path")
if not model_path:
    logger.critical("Model path not specified in configuration.")
    raise ValueError("Model path must be specified in config.yml.")

# Initialize ChatBot for conversational tasks.
try:
    chatbot = ThreadSafeChatBot(model_path=model_path)
    logger.info("ChatBot initialized with model: %s", model_path)
except Exception as e:
    logger.critical("Failed to initialize ChatBot: %s", e)
    raise

def measure_time(func):
    """
    Decorator to measure execution time of an endpoint.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        elapsed = time.time() - start
        logger.info("Endpoint '%s' completed in %.3f seconds", func.__name__, elapsed)
        return result
    return wrapper

def wait_for_server(host: str, port: int, timeout: int = 60) -> None:
    """
    Wait until a TCP connection can be made to the specified host and port.
    Raises a TimeoutError if the server is not available within the timeout.
    """
    start_time = time.time()
    while True:
        try:
            with socket.create_connection((host, port), timeout=2):
                logger.info("llama-server is now reachable at %s:%s", host, port)
                return
        except OSError:
            if time.time() - start_time > timeout:
                msg = f"Server at {host}:{port} did not become available within {timeout} seconds."
                logger.error(msg)
                raise TimeoutError(msg)
            logger.debug("Waiting for llama-server at %s:%s...", host, port)
            time.sleep(2)

def run_llama_server():
    """
    Start the llama-server process as a background process and wait until it is reachable.
    """
    try:
        binary_path = config.get("llama_server_binary_path", "./llama.cpp/bin/llama-server")
        model_path = config.get("model_path", "models/LLM/Llama-3.2-3B-Instruct-Q8_0.gguf")
        llama_host = config.get("llama_server_host", "127.0.0.1")
        llama_port = config.get("llama_server_port", 8080)

        # Ensure that the binary exists and is executable.
        if not os.path.exists(binary_path):
            logger.error("llama-server binary not found at '%s'.", binary_path)
            raise FileNotFoundError(f"llama-server binary not found at '{binary_path}'.")

        # Construct the command.
        command = [
            binary_path,
            "-m", model_path,
            "--host", str(llama_host),
            "--port", str(llama_port)
        ]
        logger.info("Starting llama-server with command: %s", " ".join(command))

        # Optionally, set the current working directory so relative paths resolve correctly.
        cwd = os.getcwd()

        # Start the server as a subprocess (non-blocking)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd  # Ensure we're in the correct directory.
        )

        # Wait briefly and poll the process to see if it exited prematurely.
        time.sleep(3)
        retcode = process.poll()
        if retcode is not None:
            stderr_output = process.stderr.read().decode("utf-8")
            logger.error("llama-server terminated unexpectedly with return code %s. Error: %s", retcode, stderr_output)
            raise Exception("llama-server terminated unexpectedly.")

        # Wait for the server to become reachable.
        wait_for_server(llama_host, int(llama_port), timeout=90)
        logger.info("llama-server started successfully (PID: %s)", process.pid)
        return process
    except Exception as e:
        logger.exception("Failed to start llama-server: %s", e)
        raise

# --- Document Processing Helper Functions ---

def generate_summary(file_bytes: bytes, min_words: int, max_words: int) -> str:
    """
    Generate a summary from the provided document bytes.
    """
    try:
        summary = chatbot.generate_summary_threadsafe(file_bytes, min_words, max_words)
        logger.info("Document summary generated.")
        return summary
    except Exception as e:
        logger.exception("Error generating summary: %s", e)
        raise

def answer_questions(file_bytes: bytes, questions: List[str], response_mode: str) -> List[str]:
    """
    Answer a list of questions based on the provided document bytes.
    """
    answers = []
    for question in questions:
        try:
            ans = chatbot.ask_question_threadsafe(file_bytes, question, response_mode)
            answers.append(ans)
        except Exception as e:
            logger.exception("Error answering question '%s': %s", question, e)
            answers.append("Error processing question.")
    return answers

def chat_with_document(file_bytes: bytes, conversation_history: list, new_message: str) -> str:
    """
    Engage in a conversational chat using the provided document bytes.
    """
    try:
        response = chatbot.chat_threadsafe(file_bytes, conversation_history, new_message)
        logger.info("Chat response generated.")
        return response
    except Exception as e:
        logger.exception("Error during document chat: %s", e)
        raise

# --- Job Management Functions ---

def create_job(job_name: str) -> int:
    """
    Create a new job entry in the database and return its unique ID.
    """
    session = SessionLocal()
    try:
        job = Job(job_name=job_name, status="Started")
        session.add(job)
        session.commit()
        session.refresh(job)
        logger.info("Job %d (%s) started.", job.id, job_name)
        return job.id
    except Exception as e:
        session.rollback()
        logger.exception("Error creating job: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create job.")
    finally:
        session.close()

def update_job(job_id: int, status: str):
    """
    Update the status and end time of a job in the database.
    """
    session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = status
            if status in ["Completed", "Aborted"]:
                # Use timezone-aware UTC datetime.
                job.end_time = datetime.datetime.now(datetime.timezone.utc)
            session.commit()
            logger.info("Job %d updated to status: %s", job_id, status)
        else:
            logger.warning("Job ID %d not found for update.", job_id)
    except Exception as e:
        session.rollback()
        logger.exception("Error updating job %d: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Failed to update job.")
    finally:
        session.close()

# --- FastAPI Application Setup ---

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application with all endpoints.
    """
    app = FastAPI(title="ot-synapses API")
    router = APIRouter()

    @router.post("/gen_summary")
    @measure_time
    async def generate_document_summary(
        file: UploadFile = File(...),
        min_words: int = Form(50),
        max_words: int = Form(150)
        ):
        """
        Generate a summary for an uploaded document.
        """
        job_id = create_job("Generate Document Summary")
        try:
            if not validate_file(file.filename):
                raise HTTPException(status_code=400, detail="Unsupported file type.")
            
            processed_dir = config.get("processed_dir", "processed_dir")
            
            file_path = await save_uploaded_file(file, processed_dir, file.filename)
            
            if not validate_file_size(file_path):
                raise HTTPException(status_code=400, detail="File size exceeds allowed limit.")
            
            text = extract_text_from_file(file_path, parse_images=True)
            
            summary = generate_summary(text.encode("utf-8"), min_words, max_words)
            update_job(job_id, "Completed")
            return {"job_id": job_id, "summary": summary}
        except Exception as e:
            update_job(job_id, "Aborted")
            logger.exception("Error in /gen_summary: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/qna_on_docs")
    @measure_time
    async def qa_on_documents(
        files: List[UploadFile] = File(...),
        questions: List[str] = Form(...),
        response_mode: str = Form("specific")
        ):
        """
        Answer questions based on one or more uploaded documents.
        """
        job_id = create_job("Q&A on Documents")
        try:
            combined_bytes = b""
            processed_dir = config.get("processed_dir", "processed_dir")
            for file in files:
                if not validate_file(file.filename):
                    raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")
                file_path = await save_uploaded_file(file, processed_dir, file.filename)
                if not validate_file_size(file_path):
                    raise HTTPException(status_code=400, detail=f"File size exceeds allowed limit: {file.filename}")
                combined_bytes += load_file_bytes(file_path)
            answers = answer_questions(combined_bytes, questions, response_mode)
            update_job(job_id, "Completed")
            return {"job_id": job_id, "answers": answers}
        except Exception as e:
            update_job(job_id, "Aborted")
            logger.exception("Error in /qna_on_docs: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/chat_with_docs")
    @measure_time
    async def chat_with_documents(
        file: UploadFile = File(...),
        new_message: str = Form(...),
        session_id: Optional[str] = Form(None)
        ):
        """
        Engage in a conversational chat about an uploaded document.
        """
        job_id = create_job("Chat with Documents")
        try:
            file_bytes = b""
            processed_dir = config.get("processed_dir", "processed_dir")
            if file:
                if not validate_file(file.filename):
                    raise HTTPException(status_code=400, detail="Unsupported file type.")
                file_path = await save_uploaded_file(file, processed_dir, file.filename)
                if not validate_file_size(file_path):
                    raise HTTPException(status_code=400, detail="File size exceeds allowed limit.")
                file_bytes = load_file_bytes(file_path)
            if not session_id or session_id not in chat_sessions:
                session_id = str(uuid.uuid4())
                chat_sessions[session_id] = []
                logger.info("New chat session created with ID: %s", session_id)
            conversation_history = chat_sessions[session_id]
            response = chat_with_document(file_bytes, conversation_history, new_message)
            update_job(job_id, "Completed")
            return {"job_id": job_id, "session_id": session_id, "response": response}
        except Exception as e:
            update_job(job_id, "Aborted")
            logger.exception("Error in /chat_with_docs: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/create_embeddings")
    @measure_time
    async def create_embeddings(file: UploadFile = File(...)):
        """
        Create embeddings from an uploaded file and store them in Qdrant.
        """
        job_id = create_job("Create Embeddings")
        try:
            if not validate_file(file.filename):
                raise HTTPException(status_code=400, detail="Unsupported file type.")
            processed_dir = config.get("processed_dir", "processed_dir")
            file_path = await save_uploaded_file(file, processed_dir, file.filename)
            if not validate_file_size(file_path):
                raise HTTPException(status_code=400, detail="File size exceeds allowed limit.")
            file_bytes = load_file_bytes(file_path)
            vector_size = config.get("qdrant", {}).get("vector_size", 768)
            dummy_vector = [0.1] * vector_size  # Replace with real embedding extraction.
            point = {
                "id": str(uuid.uuid4()),
                "vector": dummy_vector,
                "payload": {"filename": file.filename}
            }
            collection_name = config.get("qdrant", {}).get("collection_name", "default_collection")
            create_collection(collection_name=collection_name, vector_size=vector_size)
            insert_embeddings(collection_name, [point])
            update_job(job_id, "Completed")
            return {"job_id": job_id, "message": "Embeddings created and stored successfully."}
        except Exception as e:
            update_job(job_id, "Aborted")
            logger.exception("Error in /create_embeddings: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/vector_chat")
    @measure_time
    async def vector_chat(query: str = Form(...), top_k: int = Form(5)):
        """
        Perform a vector-based search and return an answer using stored embeddings.
        """
        job_id = create_job("Vector Chat")
        try:
            vector_size = config.get("qdrant", {}).get("vector_size", 768)
            query_vector = [0.1] * vector_size  # Replace with real embedding extraction.
            collection_name = config.get("qdrant", {}).get("collection_name", "default_collection")
            results = search_embeddings(collection_name, query_vector, top_k)
            answer = chatbot.ask_question_threadsafe(
                b"", f"Based on these results, answer: {query}", "elaborate"
            )
            update_job(job_id, "Completed")
            return {"job_id": job_id, "results": results, "answer": answer}
        except Exception as e:
            update_job(job_id, "Aborted")
            logger.exception("Error in /vector_chat: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/jobs")
    async def get_jobs():
        """
        Retrieve the history of all jobs.
        """
        session = SessionLocal()
        try:
            jobs_db = session.query(Job).all()
            jobs_list = [{
                "id": job.id,
                "job_name": job.job_name,
                "status": job.status,
                "start_time": job.start_time.isoformat(),
                "end_time": job.end_time.isoformat() if job.end_time else None
            } for job in jobs_db]
            return JSONResponse(content={"jobs": jobs_list})
        except Exception as e:
            logger.exception("Error retrieving jobs: %s", e)
            raise HTTPException(status_code=500, detail="Failed to retrieve jobs.")
        finally:
            session.close()

    app.include_router(router)
    return app

def main():
    """
    Main entry point.
    
    1. Launch the llama server in a background thread.
    2. Create the FastAPI application.
    3. Start the uvicorn server.
    """
    try:
        # Launch llama server as a background thread.
        llama_thread = threading.Thread(target=run_llama_server, daemon=True)
        llama_thread.start()
        logger.info("Launched llama server thread.")
    except Exception as e:
        logger.error("Failed to launch llama server: %s", e)
        raise

    # Create and run the FastAPI application.
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
