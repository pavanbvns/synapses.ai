import os
import sys
import time
import json
import hashlib
import subprocess
import logging
import uuid
import requests
import uvicorn
import threading
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, APIRouter
from fastapi.responses import JSONResponse
from qdrant_client.http.models import Distance, VectorParams

# Third-party libraries for banner and progress bar
from pyfiglet import figlet_format
from tqdm import tqdm

# My modules
from utils.config import config
from utils.chatbot import ThreadSafeChatBot
from utils.vectors import (
    get_qdrant_client,
    create_collection,
    insert_embeddings,
    get_extracted_text_from_qdrant,
)
from models.db.job import SessionLocal, Job, create_job, update_job
from utils.document_parser import extract_text_from_file  # Ensure this module is implemented
from utils.utils import validate_file, save_file_to_disk, compute_file_hash

# ------------------------------------------------------------------------------
# Global Logger Setup
LOG_LEVEL_STR = config.get("logging_level", "DEBUG")
NUMERIC_LEVEL = getattr(logging, LOG_LEVEL_STR.upper(), logging.DEBUG)
logger = logging.getLogger("ot_synapses_app")
logger.setLevel(NUMERIC_LEVEL)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(ch)

# ------------------------------------------------------------------------------
# Global FastAPI App (so endpoints appear in Swagger docs)
app = FastAPI(
    title="Ot-Synapses AI API",
    description="API endpoints for document summarization, Q&A, and more."
)

# Global ChatBot Initialization – we use llama-server for inference
model_path = config.get("model_path")
chatbot = ThreadSafeChatBot(model_path=model_path)

# ------------------------------------------------------------------------------
# Display banner using pyfiglet
def display_banner():
    banner = figlet_format("ot-synapses.ai")
    logger.info("\n%s", banner)

# ------------------------------------------------------------------------------
# Function to launch llama-server and wait for its readiness
def run_llama_server(binary_path: str, model_path: str, llama_host: str, llama_port: int, timeout: int = 120) -> subprocess.Popen:
    try:
        command = [
            binary_path,
            "-m", model_path,
            "--host", llama_host,
            "--port", str(llama_port)
        ]
        logger.info("Starting llama-server with command: %s", " ".join(command))
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("Launched llama-server process (PID: %d). Waiting for service readiness...", process.pid)
        url = f"http://{llama_host}:{llama_port}/"
        elapsed = 0
        interval = 2  # seconds
        with tqdm(total=timeout, desc="Waiting for llama-server's readiness...", unit="s", leave=False) as pbar:
            while elapsed < timeout:
                try:
                    r = requests.get(url, timeout=5)
                    if r.status_code == 200 and "The model is loading" not in r.text:
                        logger.info("llama-server is ready at %s (PID: %d).", url, process.pid)
                        return process
                except requests.RequestException:
                    pass
                time.sleep(interval)
                elapsed += interval
                pbar.update(interval)
        process.terminate()
        logger.error("llama-server did not become ready within %d seconds.", timeout)
        raise TimeoutError("llama-server startup timed out.")
    except Exception as e:
        logger.exception("Failed to start llama-server: %s", e)
        raise

# ------------------------------------------------------------------------------
# Function to check Qdrant connectivity
def check_qdrant_connection():
    try:
        client = get_qdrant_client()
        collections = client.get_collections().collections
        logger.info("Qdrant connection successful. Collections: %s", collections)
    except Exception as e:
        logger.exception("Qdrant connection failed: %s", e)
        raise RuntimeError("Failed to connect to Qdrant.")

# ------------------------------------------------------------------------------
# Function to check (or create) Qdrant collection
def check_or_create_collection(collection_name: str, vector_size: int = 768):
    try:
        client = get_qdrant_client()
        if not client.collection_exists(collection_name):
            logger.info("Collection '%s' does not exist. Creating collection.", collection_name)
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )
            logger.info("Collection '%s' created successfully.", collection_name)
        else:
            logger.info("Collection '%s' already exists.", collection_name)
    except Exception as e:
        logger.exception("Error checking or creating collection '%s': %s", collection_name, e)
        raise

# ------------------------------------------------------------------------------
# Helper function to obtain an embedding vector via llama-server
def get_embedding(text: str, llama_host: str, llama_port: int, 
                  n_predict: int = 128, temperature: float = 0.0,
                  max_chunk_size: int = int(config.get("max_embedding_input_length", 1024))
                 ) -> list:
    url = f"http://{llama_host}:{llama_port}/embedding"
    
    def request_embedding(chunk: str) -> list:
        payload = {
            "input": chunk,
            "n_predict": n_predict,
            "temperature": temperature,
            "pooling": "mean"  # Request mean pooling to get a fixed-size vector.
        }
        logger.debug("Requesting embedding for chunk of length %d.", len(chunk))
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code != 200:
            logger.error("Error obtaining embedding for chunk: %s", response.text)
            raise Exception(f"Error obtaining embedding for chunk: {response.text}")
        data = response.json()
        logger.debug("Embedding response: %s", data)
        if isinstance(data, list):
            if data and "embedding" in data[0]:
                embedding = data[0]["embedding"]
            else:
                raise Exception("Embedding not found in response for chunk. Raw response: " + str(data))
        elif isinstance(data, dict):
            if "embedding" in data:
                embedding = data["embedding"]
            elif "vector" in data:
                embedding = data["vector"]
            else:
                raise Exception("Embedding not found in response for chunk. Raw response: " + str(data))
        else:
            raise Exception("Unexpected embedding response type: " + str(type(data)))
        # If the embedding is nested (e.g., list of lists), flatten it.
        if embedding and isinstance(embedding[0], list):
            flattened = []
            for sub in embedding:
                flattened.extend(sub)
            embedding = flattened
        return embedding

    if len(text) <= max_chunk_size:
        logger.debug("Input text length (%d) is within allowed limit (%d).", len(text), max_chunk_size)
        return request_embedding(text)
    else:
        logger.debug("Input text length (%d) exceeds limit (%d). Splitting text into chunks.", len(text), max_chunk_size)
        chunks = [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size)]
        embeddings = []
        for idx, chunk in enumerate(chunks):
            logger.debug("Processing chunk %d/%d...", idx + 1, len(chunks))
            emb = request_embedding(chunk)
            embeddings.append(emb)
            time.sleep(0.1)
        
        # Verify that all embeddings have the same length
        vector_lengths = [len(emb) for emb in embeddings]
        if not all(length == vector_lengths[0] for length in vector_lengths):
            logger.error("Mismatch in embedding lengths among chunks: %s", vector_lengths)
            raise Exception("Mismatch in embedding lengths among chunks.")
        
        vector_length = vector_lengths[0]
        aggregated_embedding = [0.0] * vector_length
        for emb in embeddings:
            for i in range(vector_length):
                aggregated_embedding[i] += emb[i]
        aggregated_embedding = [val / len(embeddings) for val in aggregated_embedding]
        logger.debug("Aggregated embedding computed from %d chunks.", len(embeddings))
        return aggregated_embedding



# ------------------------------------------------------------------------------
# Background function to save file metadata and embedding to Qdrant
def background_save_to_qdrant(file_bytes: bytes, file_hash: str, file_name: str, processed_dir: str, unique_id: str, extracted_text: str, llama_host: str, llama_port: int, collection_name: str):
    try:
        # Save file to disk
        new_filename = f"{unique_id}_{file_name}"
        file_path = save_file_to_disk(file_bytes, processed_dir, new_filename)
        logger.info("Background task: saved file as %s", file_path)
        # Get embedding from llama-server using the extracted text
        embedding = get_embedding(extracted_text, llama_host, llama_port)
        logger.info("Background task: obtained embedding vector of length %d.", len(embedding))
        # Ensure the collection exists
        check_or_create_collection(collection_name, vector_size=len(embedding))
        point = {
            "id": unique_id,
            "vector": embedding,
            "payload": {
                "file_hash": file_hash,
                "extracted_text": extracted_text,
                "filename": file_name
            }
        }
        insert_embeddings(collection_name, [point])
        logger.info("Background task: stored processed file in Qdrant with UUID: %s", unique_id)
    except Exception as e:
        logger.exception("Background task: error saving file to Qdrant: %s", e)

# ------------------------------------------------------------------------------
# FastAPI Endpoint: /gen_summary
@app.post("/gen_summary")
async def generate_file_summary(
    file: UploadFile = File(...),
    min_words: int = Form(50),
    max_words: int = Form(150)
):
    """
    Generate a summary for an uploaded document.
    Workflow:
      1. Validate file type and size.
      2. Compute file hash and check Qdrant for cached extracted text.
      3. If not cached:
            a. Tag file with a UUID.
            b. Depending on config, either extract text (if text model) or skip extraction (if vision model).
            c. Immediately generate a summary by calling llama-server’s completion endpoint.
            d. In the background, compute embedding and save file metadata to Qdrant.
      4. Return the generated summary.
    """
    job_id = None
    try:
        job_id = create_job("Generate File Summary")
        # Validate file type and size
        if not validate_file(file.filename):
            raise HTTPException(status_code=400, detail="Unsupported file type.")
        file_bytes = await file.read()
        allowed_file_size = config.get("allowed_file_size_limit", 10 * 1024 * 1024)
        if len(file_bytes) > allowed_file_size:
            raise HTTPException(status_code=400, detail="File size exceeds allowed limit.")
        
        # Compute file hash to avoid reprocessing
        file_hash = compute_file_hash(file_bytes)
        logger.debug("Computed file hash: %s", file_hash)

        # Determine Qdrant collection name
        collection_name = config.get("qdrant", {}).get("collection_name", "default_collection")
        
        # Check if file was previously processed
        cached_text = get_extracted_text_from_qdrant(file_hash, collection_name)
        if cached_text:
            logger.info("File already processed; using cached extracted text.")
            extracted_text = cached_text
        else:
            # Not processed yet – generate a UUID tag
            unique_id = str(uuid.uuid4())
            processed_dir = config.get("processed_dir", "processed_dir")
            # Immediately extract text for summary generation
            model_is_vision = config.get("model_type_is_vision", False)
            if model_is_vision:
                logger.info("Configured to use vision model; skipping text extraction.")
                extracted_text = file_bytes.decode("utf-8", errors="replace")
            else:
                # Save file to disk temporarily for text extraction
                temp_filename = f"{unique_id}_{file.filename}"
                file_path = save_file_to_disk(file_bytes, processed_dir, temp_filename)
                logger.info("Saved file as %s for text extraction.", file_path)
                extracted_text = extract_text_from_file(file_path, parse_images=True)
                logger.info("Extracted text of length %d from '%s'.", len(extracted_text), file_path)
            # Now generate summary immediately (without waiting for embedding)
        # Generate summary using the appropriate input:
        model_is_vision = config.get("model_type_is_vision", False)
        if model_is_vision:
            summary = chatbot.generate_summary_threadsafe(file_bytes, min_words, max_words)
        else:
            summary = chatbot.generate_summary_threadsafe(extracted_text.encode("utf-8"), min_words, max_words)
        logger.info("Generated summary for file '%s'.", file.filename)
        update_job(job_id, "Completed")
        
        # Now, if the file was not cached, start a background thread to compute embedding and save to Qdrant
        if not cached_text:
            llama_host = config.get("llama_server_host", "127.0.0.1")
            llama_port = int(config.get("llama_server_port", 8080))
            background_thread = threading.Thread(
                target=background_save_to_qdrant,
                args=(file_bytes, file_hash, file.filename, processed_dir, unique_id, extracted_text, llama_host, llama_port, collection_name),
                daemon=True
            )
            background_thread.start()
            logger.info("Launched background task for saving file to Qdrant.")
        
        return {"job_id": job_id, "summary": summary}
    except Exception as e:
        if job_id is not None:
            update_job(job_id, "Aborted")
        logger.exception("Error in /gen_summary endpoint: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------------------------------------
# Main function to start the application and servers
def main():
    try:
        display_banner()
        logger.info("Starting Ot-Synapses AI Application...")

        # Read configuration values
        llama_server_binary = config.get("llama_server_binary_path", "./llama.cpp/bin/llama-server")
        model_path = config.get("model_path")
        llama_host = config.get("llama_server_host", "127.0.0.1")
        llama_port = int(config.get("llama_server_port", 8080))
        uvicorn_host = config.get("uvicorn_host", "0.0.0.0")
        uvicorn_port = int(config.get("uvicorn_port", 8000))

        if not model_path or not os.path.exists(model_path):
            logger.error("Model path '%s' does not exist.", model_path)
            sys.exit(1)

        # Start llama-server and wait until it is fully ready
        llama_process = run_llama_server(llama_server_binary, model_path, llama_host, llama_port)
        # Check Qdrant connectivity
        check_qdrant_connection()
        # Check or create Qdrant collection
        check_or_create_collection(collection_name=collection_name if (collection_name := config.get("qdrant", {}).get("collection_name", "default_collection")) else "default_collection")
        # Start Uvicorn server (this call blocks)
        logger.info("Starting Uvicorn server on %s:%d...", uvicorn_host, uvicorn_port)
        uvicorn.run(app, host=uvicorn_host, port=uvicorn_port)
    except Exception as e:
        logger.exception("Application startup failed: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
