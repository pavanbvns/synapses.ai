# frontend/utils/render_utils.py

import streamlit as st
import base64
from typing import Union
from io import BytesIO


def render_file_preview(
    file: Union[BytesIO, bytes, str], file_type: str = "txt", filename: str = ""
):
    """
    Display a preview of a file in the Streamlit UI based on its type.
    Supports text, image, and limited document types.
    """
    st.markdown(f"#### 📄 Preview: {filename or 'Document'}")

    if isinstance(file, BytesIO):
        file.seek(0)
        file_bytes = file.read()
    elif isinstance(file, bytes):
        file_bytes = file
    else:
        file_bytes = file.encode("utf-8")

    if file_type.lower() in ["txt", "text", "md"]:
        try:
            text = file_bytes.decode("utf-8")
            st.text_area("Text Preview", value=text, height=300)
        except UnicodeDecodeError:
            st.warning("Unable to decode text for preview.")

    elif file_type.lower() in ["jpg", "jpeg", "png", "tiff"]:
        st.image(file_bytes, use_column_width=True)

    elif file_type.lower() in ["pdf"]:
        base64_pdf = base64.b64encode(file_bytes).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)

    else:
        st.warning("Preview not supported for this file type.")


def render_response_content(response: str):
    """
    Safely renders the response content from LLM or backend.
    """
    if not response:
        st.info("No response received.")
        return

    st.markdown("#### 🤖 AI Response")
    st.markdown(response, unsafe_allow_html=True)
