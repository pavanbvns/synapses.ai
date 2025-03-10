# Use Ubuntu 24.04 as the base image.
FROM ubuntu:24.04
ENV PYTHONPATH=/app
# Set non-interactive mode and disable .pyc file creation.
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Update apt sources and install essential packages.
RUN apt-get update && apt-get install -y \
    software-properties-common \
    wget \
    build-essential \
    cmake \
    git \
 && rm -rf /var/lib/apt/lists/*

# Add deadsnakes PPA and install Python 3.12 and venv.
RUN add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
 && \
    wget https://bootstrap.pypa.io/get-pip.py && \
    python3.12 get-pip.py --break-system-packages && rm get-pip.py

# Copy requirements.txt and the installer_files folder into the container.
COPY requirements.txt .
COPY installer_files/ ./installer_files/

# In your requirements.txt, ensure any local wheel uses an absolute file URL,
# e.g.:
#   llama-cpp-python @ file:///app/installer_files/llama_cpp_python-0.3.7-cp312-cp312-linux_x86_64.whl
RUN python3.12 -m pip install --upgrade pip --break-system-packages && \
    python3.12 -m pip install --no-index --find-links=./installer_files -r requirements.txt --break-system-packages

# Copy the rest of your application code.
COPY . .

EXPOSE 8000

# Start the FastAPI application using uvicorn.
CMD ["python3.12", "-m", "uvicorn", "ot_synapses_ai_app:app", "--host", "0.0.0.0", "--port", "8000"]
