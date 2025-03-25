# backend/main.py

import os
import sys
import time
import subprocess
import logging
import signal

# import threading
import uvicorn
from pyfiglet import figlet_format
from tqdm import tqdm
import requests

# Import configuration, database, and utility modules
from backend.utils.config import config
from backend.models.db.job import Base, engine

# from backend.utils.chatbot import ThreadSafeChatBot
from backend.utils.vectors import get_qdrant_client, check_or_create_collection

# Import routers for API endpoints
from backend.routers import gen_summary, qna_on_docs, find_obligations, find_risks
from fastapi import FastAPI

# Initialize logger
logger = logging.getLogger("backend.main")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(ch)

# Global variable to hold the llama‑server process
llama_process = None


def display_banner():
    """Display the project banner using pyfiglet."""
    banner = figlet_format("ot-synapses.ai")
    logger.info("\n%s", banner)


def run_llama_server(
    binary_path: str,
    model_path: str,
    llama_host: str,
    llama_port: int,
    timeout: int = 240,
) -> subprocess.Popen:
    """
    Launch llama-server in the background and wait until it is fully ready.
    A progress bar is shown during the wait.

    Returns:
        The subprocess.Popen object for the llama-server.
    """
    try:
        # Construct the command
        command = [
            binary_path,
            "-m",
            model_path,
            "--host",
            llama_host,
            "--port",
            str(llama_port),
        ]
        logger.info("Starting llama-server with command: %s", " ".join(command))
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        logger.info(
            "Launched llama-server process (PID: %d). Waiting for service readiness...",
            process.pid,
        )
        url = f"http://{llama_host}:{llama_port}/"
        elapsed = 0
        interval = 2  # seconds
        with tqdm(
            total=timeout,
            desc="Waiting for llama-server readiness...",
            unit="s",
            leave=False,
        ) as pbar:
            while elapsed < timeout:
                try:
                    r = requests.get(url, timeout=5)
                    # Consider the server ready if it returns 200 and does not contain the "The model is loading" message.
                    if r.status_code == 200 and "The model is loading" not in r.text:
                        logger.info(
                            "llama-server is ready at %s (PID: %d).", url, process.pid
                        )
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


def check_qdrant_connection():
    """Ensure Qdrant is reachable by listing collections."""
    try:
        client = get_qdrant_client()
        collections = client.get_collections().collections
        logger.info("Qdrant connection successful. Collections: %s", collections)
    except Exception as e:
        logger.exception("Qdrant connection failed: %s", e)
        raise RuntimeError("Failed to connect to Qdrant.")


def create_app() -> FastAPI:
    """Create the FastAPI application and include routers."""
    app = FastAPI(
        title="Ot-Synapses AI API",
        description="API endpoints for document summarization, Q&A, obligations, risks, and conversational chat.",
    )
    # Include API endpoint routers
    app.include_router(gen_summary.router)
    app.include_router(qna_on_docs.router)
    app.include_router(find_obligations.router)
    app.include_router(find_risks.router)
    return app


def shutdown_handler(signum, frame):
    """Signal handler to terminate the llama-server on shutdown."""
    logger.info("Received signal %s. Shutting down gracefully.", signum)
    global llama_process
    if llama_process and llama_process.poll() is None:
        logger.info("Terminating llama-server (PID: %d).", llama_process.pid)
        llama_process.terminate()
        try:
            llama_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("llama-server did not exit promptly; killing it.")
            llama_process.kill()
    sys.exit(0)


def main():
    global llama_process
    try:
        display_banner()
        logger.info("Starting Ot-Synapses AI Application...")
        # Initialize database tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized.")

        # Read configuration values
        llama_server_binary = config.get(
            "llama_server_binary_path", "./llama.cpp/bin/llama-server"
        )
        model_path = config.get("model_path")
        llama_host = config.get("llama_server_host", "127.0.0.1")
        llama_port = int(config.get("llama_server_port", 8080))
        uvicorn_host = config.get("uvicorn_host", "0.0.0.0")
        uvicorn_port = int(config.get("uvicorn_port", 8000))

        if not model_path or not os.path.exists(model_path):
            logger.error("Model path '%s' does not exist.", model_path)
            sys.exit(1)

        # Start llama-server and wait for its readiness
        llama_process = run_llama_server(
            llama_server_binary, model_path, llama_host, llama_port
        )
        # Check Qdrant connectivity
        check_qdrant_connection()
        # Ensure the default Qdrant collection exists
        default_collection = config.get("qdrant", {}).get(
            "collection_name", "default_collection"
        )
        check_or_create_collection(collection_name=default_collection)

        # Create FastAPI app and start Uvicorn server
        app = create_app()
        logger.info("Starting Uvicorn server on %s:%d...", uvicorn_host, uvicorn_port)
        uvicorn.run(app, host=uvicorn_host, port=uvicorn_port)
    except Exception as e:
        logger.exception("Application startup failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    main()
