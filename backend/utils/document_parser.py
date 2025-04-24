# backend/utils/document_parser.py

import os
import logging
import traceback
import gc
import torch
from typing import List
from unstructured.partition.pdf import partition_pdf
from unstructured.partition.docx import partition_docx
from unstructured.partition.doc import partition_doc
from pdf2image import convert_from_path
import PyPDF2
import docx2txt
from PIL import Image
import pytesseract

from backend.utils.config import config

# Initialize logging
logger = logging.getLogger(__name__)
logging_level_str = config.get("logging_level", "DEBUG")
numeric_level = getattr(logging, logging_level_str.upper(), logging.DEBUG)
logger.setLevel(numeric_level)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def extract_text_from_file(file_path: str) -> str:
    """
    Extract text and image OCR content from various supported file types using unstructured.io components.
    Uses `partition_pdf`, `partition_docx`, or `partition_doc` based on file type.
    Applies OCR on images and embedded content as needed.
    """
    try:
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        combined_text = []

        if ext == ".pdf":
            elements = partition_pdf(
                filename=file_path,
                extract_images_in_pdf=True,
                infer_table_structure=True,
                chunking_strategy="by_title",
                max_characters=4000,
                new_after_n_chars=3800,
                combine_text_under_n_chars=2000,
            )
        elif ext == ".docx":
            elements = partition_docx(filename=file_path)
        elif ext == ".doc":
            elements = partition_doc(filename=file_path)
        elif ext in [".jpg", ".jpeg", ".png", ".tiff"]:
            image = Image.open(file_path).convert("RGB")
            ocr_text = pytesseract.image_to_string(image)
            return ocr_text.strip()
        else:
            raise NotImplementedError(f"Unsupported file extension: {ext}")

        for el in elements:
            if hasattr(el, "text") and el.text:
                combined_text.append(el.text)
            if hasattr(el, "image") and el.image is not None:
                try:
                    pil_img = Image.open(el.image).convert("RGB")
                    ocr_text = pytesseract.image_to_string(pil_img)
                    if ocr_text.strip():
                        combined_text.append(ocr_text)
                except Exception as im_err:
                    logger.warning(f"Failed to OCR embedded image: {im_err}")

        return "\n".join(chunk.strip() for chunk in combined_text if chunk.strip())
    except Exception as e:
        logger.exception(f"Error extracting text from file '{file_path}': {e}")
        traceback.print_exc()
        raise


def extract_text_from_image(file_path: str) -> str:
    """
    OCR extraction from image files using Tesseract.
    """
    try:
        image = Image.open(file_path)
        return pytesseract.image_to_string(image)
    except Exception as e:
        logger.exception(f"Error extracting text from image '{file_path}': {e}")
        return ""


def convert_pdf_to_images(file_path: str, output_dir: str) -> List[str]:
    """
    Convert PDF pages to images for OCR fallback using pdf2image.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    image_files = []
    try:
        images = convert_from_path(
            file_path, fmt="jpeg", output_folder=output_dir, dpi=300
        )
        for i, img in enumerate(images):
            img_path = os.path.join(output_dir, f"page_{i}.jpeg")
            img.save(img_path, "JPEG")
            image_files.append(img_path)
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        traceback.print_exc()

    return image_files


def cleanup_memory():
    """
    Force garbage collection and clear GPU memory if available.
    """
    try:
        torch.cuda.empty_cache()
    except Exception:
        pass
    gc.collect()


def extract_text_from_pdf(file_path: str, parse_images: bool = True) -> str:
    """
    Legacy fallback: Extract text from PDF using PyPDF2 and OCR if required.
    """
    text_content = []
    try:
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page_number, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                if text:
                    text_content.append(text)
                elif parse_images:
                    try:
                        images = convert_from_path(
                            file_path,
                            first_page=page_number + 1,
                            last_page=page_number + 1,
                            dpi=300,
                        )
                        if images:
                            ocr_text = pytesseract.image_to_string(images[0])
                            if ocr_text.strip():
                                text_content.append(ocr_text)
                    except Exception as ocr_e:
                        logger.warning(f"OCR failed on page {page_number}: {ocr_e}")
        return "\n".join(text_content)
    except Exception as e:
        logger.exception(f"Error extracting text from PDF '{file_path}': {e}")
        raise


def extract_text_from_docx(file_path: str, parse_images: bool = False) -> str:
    """
    Legacy fallback: Extract text from DOCX using docx2txt.
    """
    try:
        text = docx2txt.process(file_path)
        if not text:
            logger.debug(f"DOCX '{file_path}' returned empty text.")
        return text if text else ""
    except Exception as e:
        logger.exception(f"Error extracting text from DOCX '{file_path}': {e}")
        raise
