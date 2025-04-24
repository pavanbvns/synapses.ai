# frontend/pages/help.py

import streamlit as st


def render_help_docs():
    """
    Render help documentation for both business and technical users.
    """
    st.title("📘 Help Documentation")
    st.markdown("---")

    st.header("🔹 Getting Started")
    st.markdown("""
    - **Welcome to Synapses.AI** – a platform for AI-powered document processing and analytics.
    - You can **upload documents**, **ask questions**, **generate summaries**, or **extract risks and obligations**.
    - Simply click the ➕ icon in the top right to start a new task.
    """)

    st.header("🔹 Supported File Formats")
    st.markdown("""
    - **Document Types**: PDF, DOC, DOCX
    - **Image Types**: JPG, JPEG, PNG, TIFF
    - **Max File Size**: 10 MB per file
    """)

    st.header("🔹 AI Task Types")
    st.markdown("""
    1. **Generate Summary**: Upload a document and get a concise, logical summary.
    2. **Q&A on Documents**: Ask one or more questions on uploaded files and get precise answers.
    3. **Chat with Documents**: Conversational AI experience with uploaded documents.
    4. **Find Obligations / Find Risks**: Extract structured risk or obligation details using LLMs.
    5. **Ingest to Knowledge Base**: Feed your documents to the vector database for future retrieval or chat-based queries.
    """)

    st.header("🔹 Job Lifecycle")
    st.markdown("""
    - When you trigger a task, it creates a **Job** entry.
    - You can view **Job Status**, **Results**, **Uploaded Files**, and **Parameters**.
    - Jobs can be **Aborted**, **Re-created**, or simply **Closed**.
    """)

    st.header("🔹 UI Tips")
    st.markdown("""
    - Click the **API Docs** icon to see available backend endpoints.
    - Click the **llama-server UI** icon to interact with your deployed model directly.
    - Job progress and outputs are displayed in real time with elegant loading indicators and preview panes.
    """)

    st.header("🔹 For Technical Users")
    st.markdown("""
    - **Backend**: FastAPI framework, supports streaming responses and threaded job execution.
    - **LLM Integration**: Uses `llama.cpp`-compatible models like MiniCPM, LLaMA, and Qwen.
    - **Embeddings + RAG**: Powered by Qdrant with dynamic vector upserts and context assembly.
    - **Vision Models**: Fully supported, including image and OCR processing with Unstructured.io and pytesseract.
    - **Logging & Error Handling**: Centralized logging, comprehensive try/except, and job recovery mechanics.
    """)

    st.info(
        "Need more help? Reach out to your technical team or check the project’s README for deployment instructions."
    )
