import subprocess
import threading
import uvicorn
from fastapi import FastAPI, APIRouter

def run_llama_server():
    # Adjust the command and path to your llama server executable and model
    command = ["./llama.cpp/bin/llama-server", "-m", "/mnt/c/Pavan/MyCodingWorld/ot-synapses.ai/ot-synapses.ai-project/models/LLM/Llama-3.2-3B-Instruct-Q8_0.gguf"]
    # Launch the llama server; use subprocess.run() if you want it to block,
    # or subprocess.Popen() to have more control.
    process = subprocess.Popen(command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    
    return process

def create_app():
    app = FastAPI(title="My Project API")
    router = APIRouter()

    @router.post("/infer")
    def infer(prompt: str):
        # Your endpoint that might call the llama server via HTTP.
        return {"response": f"Inference result for prompt: {prompt}"}

    app.include_router(router)
    return app

app = create_app()

if __name__ == "__main__":
    # Start the llama server in a separate thread without blocking.
    llama_thread = threading.Thread(target=run_llama_server, daemon=True)
    llama_thread.start()
    
    # Now run the FastAPI app with uvicorn.
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)