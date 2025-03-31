# Synapses.ai

Synapses.ai is a proof‑of‑concept AI platform that leverages local large language models (LLMs) via a fully open‑source stack. It is designed to work entirely on local CPU hardware using llama‑server (via llama.cpp), enabling privacy‑preserving, cost‑optimized AI for document processing, process data analytics, and conversational support.

---

## Table of Contents

- [Overview](#overview)
- [Key Features and Value Proposition](#key-features-and-value-proposition)
- [Tech Stack](#tech-stack)
- [Llama‑server & LLM Support](#llama-server--llm-support)
- [Developer Setup (WSL on Windows 10/11)](#developer-setup-wsl-on-windows-1011)
- [Building & Running the Project](#building--running-the-project)
- [Extending the Framework](#extending-the-framework)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Synapses.ai demonstrates the capability to run large language models locally on a CPU. The platform is built entirely with open‑source Python libraries and supports multiple types of document and process-based tasks including:

- Document summarization and question‑answering (Q&A)
- Process data analysis and reporting
- Conversational chat with retrieval‑augmented generation (RAG)

The solution integrates a vector database (Qdrant) for multimodal retrieval, a llama‑server for LLM inference, and a FastAPI backend with a pluggable React/Next.js chat UI.

---

## Key Features and Value Proposition

- **Cost‑Effective & Accessible:**  
  Run advanced language models on CPU hardware, eliminating the need for expensive GPUs.

- **Privacy‑Preserving:**  
  Local inference ensures that sensitive data remains on‑premises.

- **Modular & Extensible:**  
  A micro‑services architecture with clear separation between document ingestion, embedding generation, and conversational AI allows for easy extension and customization.

- **Open‑Source Stack:**  
  Leverage well‑supported open‑source libraries (FastAPI, llama.cpp, Qdrant, Unstructured.io) without vendor lock‑in.

- **Flexible Use Cases:**  
  Suitable for document processing, IT support, internal knowledge management, customer support, and more.

---

## Tech Stack

- **Backend:**  
  - **FastAPI:** For RESTful API development.
  - **SQLAlchemy & SQLite:** For job tracking and logging.
  - **llama.cpp (llama‑server):** For LLM inference on CPU.
  - **Qdrant:** Vector database for storing embeddings.
  - **Unstructured.io & Tesseract:** For document text, table, and image extraction.

- **Frontend:**  
  - **React/Next.js:** For building a pluggable chat interface.
  - **Streaming API:** To provide a real‑time conversational experience.

- **Containerization:**  
  - **Docker:** For building, packaging, and deploying the complete solution.

---

## Llama‑server & LLM Support

The core inference engine is built on llama‑server, compiled from the llama.cpp project. Key points include:

- **Compilation & Deployment:**  
  The llama‑server is compiled with optimizations for CPU inference (8‑bit quantized models) and can be configured to run in GPU‑accelerated mode if needed.

- **Multiple LLM Support:**  
  While our current implementation uses the llama‑server with a specific model (e.g., llama 3.2 3B), the architecture is flexible. The same inference engine can be used to serve various LLMs (by switching models or configurations) for different use cases.

- **Usage Across Multiple Purposes:**  
  The system supports:
  - Document summarization and Q&A.
  - Process data analytics.
  - Conversational AI via a chat interface.
  
  This versatility is achieved by coupling retrieval‑augmented generation (using Qdrant) with robust LLM inference.

---

## Developer Setup (WSL on Windows 10/11)

Follow these steps to set up your development environment on a Windows 10/11 laptop using WSL (Windows Subsystem for Linux).

### Prerequisites

- Windows 10 (version 2004+) or Windows 11.
- Administrator rights.
- Visual Studio Code (with the Remote - WSL extension) is recommended.
- Internet access for initial installation.

### Step 1: Enable WSL

1. Open PowerShell as Administrator and run:
   ```powershell
   wsl --install
   This command installs WSL 2 and the default Linux distribution (usually Ubuntu).
2. Restart your computer when prompted.
3. Verify installation by running:
   ```powershell
    wsl --list --verbose

### Step 2: Set Up Your Linux Distribution (Ubuntu)

1. Launch Ubuntu from the Start Menu.

2. Create a UNIX username and password.

3. Update your system:
    ```bash
    sudo apt update && sudo apt upgrade -y

4. Install essential packages:
    ```bash
    sudo apt install -y git curl build-essential cmake wget python3 python3-venv python3-pip tesseract-ocr libtesseract-dev

### Step 3: Configure Environment Variables

1.Open your shell profile (e.g., ~/.bashrc):
    ```bash
    touch ~/.bashrc

2. Append the following line to set LD_LIBRARY_PATH for llama‑server:
    ```bash
    export LD_LIBRARY_PATH=./external/llama.cpp/bin:$LD_LIBRARY_PATH

3. Save and reload:
    ```bash
    source ~/.bashrc

### Step 4: Clone the Project Repository

1. Clone the repository:
    ```bash
    git clone https://your.repo.url/synapses.ai.git

2. Navigate to the project directory:
    ```bash
    cd synapses.ai

### Step 5: Set Up the Backend

1. Create and activate a virtual environment:
    ```bash
    python3 -m venv venvsource venv/bin/activate

2. Install dependencies:
    ```bash
    pip install --upgrade pip

    pip install -r requirements.txt

3. Start the backend server:
    ```bash
    uvicorn backend.main:app --host 0.0.0.0 --port 8000

4. Verify it is accessible at http://127.0.0.1:8000.

### Step 6: Set Up the Frontend

1. Navigate to the frontend folder:
    ```bash
    cd frontend

2. Install Node.js dependencies (install Node.js on WSL via nvm if not installed):
    ```bash
    npm install

3. Start the frontend dev server:
    ```bash
    npm run dev # For Next.js or npm start for Create React App.

4. The UI should be accessible on http://localhost:3000.

### Step 7: Use VS Code with WSL

1.  Visual Studio Code on Windows.

2. Install the Remote - WSL extension.

3. Open your project folder in VS Code by selecting "Remote-WSL: New Window" from the Command Palette.

4. Building & Running the Project with Docker

5. A sample Dockerfile is provided in the project root for building a containerized version of the system. 
    **Key highlights include:**

    Installation of Tesseract OCR and necessary build tools.

    Setting LD_LIBRARY_PATH for llama‑server.

    Multi‑stage build for backend (Python/FastAPI) and frontend (React/Next.js).

    Launching both backend and frontend in the final container.

    **To build and run:**
    ```bash
    docker build -t synapses-ai .

    docker run -p 8000:8000 -p 3000:3000 synapses-ai

    The backend will be available at http://localhost:8000 and the frontend at http://localhost:3000.

## Extending the Framework

### Agentic/Autonomous Workflows

The current architecture can be extended into an autonomous system that:

**Orchestrates multi‑step reasoning:** Breaks down complex queries into subtasks using frameworks like LangChain.

**Maintains persistent memory:** Uses Qdrant to store context over time, enabling long‑term conversation and continuous learning.

**Integrates external actions:** Automatically triggers support tickets, notifications, or integrations with enterprise systems when needed.

**Self‑monitors output:** Evaluates the quality of generated responses and iterates if necessary.

### Potential Use Cases

**Autonomous IT Support Agent:**
Handles routine IT queries and escalates only when necessary.

**Customer Support Assistant:**
Provides product information, troubleshooting steps, and can automatically route complex issues.

**Internal Knowledge Base Querying:**
Helps employees access internal documentation quickly and efficiently.

## Conclusion

Synapses.ai represents an innovative, cost‑effective approach to deploying advanced LLMs on local hardware. By leveraging a fully open‑source stack, containerization, and a flexible API architecture, it offers a scalable and privacy‑preserving solution with significant business value.

## Contributing

Contributions are welcome! Please see CONTRIBUTING.md for details on our code of conduct, and the process for submitting pull requests.

## License

This project is licensed under the MIT License.



