# ----- Stage 1: Build Backend -----
    FROM ubuntu:24.04 as backend-build

    # Set non-interactive mode
    ENV DEBIAN_FRONTEND=noninteractive
    # Set LD_LIBRARY_PATH to include llama-server binaries (relative to container /app folder)
    ENV LD_LIBRARY_PATH=/app/external/llama.cpp/bin:$LD_LIBRARY_PATH
    
    # Install system packages, including Tesseract OCR and build tools
    RUN apt-get update && apt-get install -y \
        python3.12 \
        python3.12-venv \
        build-essential \
        cmake \
        git \
        wget \
        tesseract-ocr \
        libtesseract-dev \
        && rm -rf /var/lib/apt/lists/*
    
    WORKDIR /app
    
    # Copy the backend source code and external dependencies
    COPY backend/ ./backend/
    COPY external/llama.cpp/ ./external/llama.cpp/
    COPY config.yml .
    COPY requirements.txt .
    
    # Set up a virtual environment and install Python dependencies
    RUN python3.12 -m venv venv && \
        . venv/bin/activate && \
        pip install --upgrade pip && \
        pip install --no-cache-dir -r requirements.txt
    
    # ----- Stage 2: Build Frontend -----
    FROM node:18 as frontend-build
    
    WORKDIR /app/frontend
    
    # Copy frontend package files and install dependencies
    COPY frontend/package.json frontend/package-lock.json ./
    RUN npm install
    
    # Copy the rest of the frontend code and build the app.
    COPY frontend/ ./
    RUN npm run build
    
    # ----- Stage 3: Final Image -----
    FROM ubuntu:24.04
    
    # Set non-interactive mode and required environment variables
    ENV DEBIAN_FRONTEND=noninteractive
    ENV PYTHONUNBUFFERED=1
    ENV LD_LIBRARY_PATH=/app/external/llama.cpp/bin:$LD_LIBRARY_PATH
    
    RUN apt-get update && apt-get install -y \
        python3.12 \
        python3.12-venv \
        build-essential \
        cmake \
        git \
        wget \
        tesseract-ocr \
        libtesseract-dev \
        && rm -rf /var/lib/apt/lists/*
    
    WORKDIR /app
    
    # Copy backend files from the backend-build stage
    COPY --from=backend-build /app /app
    
    # Copy the built frontend from the frontend-build stage
    COPY --from=frontend-build /app/frontend/build ./frontend/build
    
    # Expose ports: 8000 for backend, 3000 for frontend static server
    EXPOSE 8000
    EXPOSE 3000
    
    # Start both backend and frontend.
    # To launch Uvicorn in the background and serve the frontend using 'npx serve' ????.
    # TBD for production !!!! Using a process manager (like supervisord) or separate containers ????? Yet to explore
    CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port 8000 & npx serve -s frontend/build -l 3000"
    