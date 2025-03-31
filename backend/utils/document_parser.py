# backend/utils/document_parser.py

import os
import logging
import traceback
from typing import List
from unstructured.partition.pdf import partition_pdf
from unstructured.partition.docx import partition_docx
from unstructured.partition.doc import partition_doc
from pdf2image import convert_from_path
import PyPDF2
import docx2txt
from PIL import Image  # , ImageSequence
import pytesseract
import gc
import torch

from backend.utils.config import config
# from backend.utils.utils import validate_file, compute_file_hash

logger = logging.getLogger(__name__)
logging_level_str = config.get("logging_level", "DEBUG")
numeric_level = getattr(logging, logging_level_str.upper(), logging.DEBUG)
logger.setLevel(numeric_level)
if not logger.handlers:
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


def extract_text_from_file(file_path: str) -> str:
    """
    Extract text from a file (PDF, DOC, DOCX, JPG, PNG, TIFF, etc.) in the
    same sequence as elements appear. If a PDF or DOC/DOCX has embedded images,
    we run OCR on those images and append the recognized text in the correct
    sequence.

    Returns:
        A single combined string with text from:
          - textual paragraphs
          - table text
          - OCR text from images (if any)
        in the same order they appear in the document.
    """
    try:
        logging.info("Using unstructured.io")
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        # For final combined text
        combined_text = []

        if ext in [".pdf"]:
            # Use unstructured to partition PDF
            # This automatically extracts text, tables, and images in order
            elements = partition_pdf(
                filename=file_path,
                extract_images_in_pdf=True,
                infer_table_structure=True,
            )
            for el in elements:
                if hasattr(el, "text") and el.text:
                    combined_text.append(el.text)
                if hasattr(el, "image") and el.image:
                    # Convert the unstructured image to PIL and run OCR
                    try:
                        pil_img = Image.open(el.image).convert("RGB")
                        ocr_text = pytesseract.image_to_string(pil_img)
                        if ocr_text.strip():
                            combined_text.append(ocr_text)
                    except Exception as im_err:
                        logger.warning(f"Failed to OCR embedded image: {im_err}")

        elif ext in [".docx"]:
            # partition_docx for .docx
            elements = partition_docx(filename=file_path)
            for el in elements:
                if hasattr(el, "text") and el.text:
                    combined_text.append(el.text)
                if hasattr(el, "image") and el.image:
                    try:
                        pil_img = Image.open(el.image).convert("RGB")
                        ocr_text = pytesseract.image_to_string(pil_img)
                        if ocr_text.strip():
                            combined_text.append(ocr_text)
                    except Exception as im_err:
                        logger.warning(f"Failed to OCR embedded image: {im_err}")

        elif ext in [".doc"]:
            # partition_doc for .doc
            # (Unstructured can handle doc, though sometimes you need extra libs)
            elements = partition_doc(filename=file_path)
            for el in elements:
                if hasattr(el, "text") and el.text:
                    combined_text.append(el.text)
                if hasattr(el, "image") and el.image:
                    try:
                        pil_img = Image.open(el.image).convert("RGB")
                        ocr_text = pytesseract.image_to_string(pil_img)
                        if ocr_text.strip():
                            combined_text.append(ocr_text)
                    except Exception as im_err:
                        logger.warning(f"Failed to OCR embedded image: {im_err}")

        elif ext in [".jpg", ".jpeg", ".png", ".tiff"]:
            # It's a standalone image -> just do OCR
            try:
                pil_img = Image.open(file_path).convert("RGB")
                ocr_text = pytesseract.image_to_string(pil_img)
                if ocr_text.strip():
                    combined_text.append(ocr_text)
            except Exception as e:
                logger.exception(f"Error extracting text from image '{file_path}': {e}")
                raise

        else:
            raise NotImplementedError(f"Unsupported file extension: {ext}")

        final_text = "\n".join(
            chunk.strip() for chunk in combined_text if chunk.strip()
        )
        return final_text

    except Exception as e:
        logger.error(f"Error extracting text from file '{file_path}': {e}")
        traceback.print_exc()
        raise


def extract_text_from_image(file_path: str) -> str:
    """
    Extract text from an image file using OCR (pytesseract).
    Handles common image formats and multi-page TIFF files.
    """
    try:
        image = Image.open(file_path)
        # If multi-page tiff, you can iterate frames
        text_content = pytesseract.image_to_string(image)
        return text_content
    except Exception as e:
        logger.exception(f"Error extracting text from image '{file_path}': {e}")
        return ""


def convert_pdf_to_images(file_path: str, output_dir: str) -> List[str]:
    """
    Convert PDF pages to images using pdf2image.
    Returns a list of image file paths.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    image_files = []
    try:
        images = convert_from_path(file_path, fmt="jpeg", output_folder=output_dir)
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
    Helper function to free up GPU/CPU memory after big tasks.
    """
    try:
        torch.cuda.empty_cache()
    except Exception:
        pass
    gc.collect()


# --------------------------------------------------------------------------------------------------------------------
def extract_text_from_pdf(file_path: str, parse_images: bool = True) -> str:
    """
    Extract text from a PDF file using PyPDF2.
    If a page lacks extractable text and parse_images is True, convert that page to an image
    with pdf2image and apply OCR via pytesseract.

    Prerequisites:
      - pdf2image and pytesseract must be installed.
      - Tesseract OCR must be installed on the system (e.g., on Ubuntu: sudo apt-get install tesseract-ocr).
    """
    text_content = []
    try:
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            num_pages = len(pdf_reader.pages)
            logger.debug("PDF '%s' has %d pages.", file_path, num_pages)
            for page_number in range(num_pages):
                page = pdf_reader.pages[page_number]
                text = page.extract_text()
                if text:
                    logger.debug("Extracted text from page %d.", page_number)
                    text_content.append(text)
                else:
                    logger.debug(
                        "No extractable text on page %d of '%s'.",
                        page_number,
                        file_path,
                    )
                    if parse_images:
                        logger.debug(
                            "OCR enabled. Converting page %d to image.", page_number
                        )
                        try:
                            # Convert only the current page to an image.
                            images = convert_from_path(
                                file_path,
                                first_page=page_number + 1,
                                last_page=page_number + 1,
                            )
                            if images:
                                ocr_text = pytesseract.image_to_string(images[0])
                                if ocr_text.strip():
                                    logger.debug(
                                        "OCR extracted text from page %d.", page_number
                                    )
                                    text_content.append(ocr_text)
                                else:
                                    logger.warning(
                                        "OCR did not extract any text from page %d.",
                                        page_number,
                                    )
                            else:
                                logger.warning(
                                    "No image returned for page %d.", page_number
                                )
                        except Exception as ocr_e:
                            logger.exception(
                                "Error during OCR on page %d of '%s': %s",
                                page_number,
                                file_path,
                                ocr_e,
                            )
                    else:
                        logger.debug(
                            "OCR disabled; skipping OCR for page %d.", page_number
                        )
        combined_text = "\n".join(text_content)
        logger.info(
            "Extracted text from PDF '%s' (%d characters).",
            file_path,
            len(combined_text),
        )
        return combined_text
    except PyPDF2.errors.PdfReadError as e:
        logger.exception("PyPDF2 failed to read PDF '%s': %s", file_path, e)
        raise
    except Exception as e:
        logger.exception("Error extracting text from PDF '%s': %s", file_path, e)
        raise


def extract_text_from_docx(file_path: str, parse_images: bool = False) -> str:
    """
    Extract text from a DOCX file using docx2txt.
    If parse_images is True, additional OCR for embedded images could be integrated.
    """
    try:
        text = docx2txt.process(file_path)
        if not text:
            logger.debug(
                "DOCX '%s' returned empty text. Possibly image-based content.",
                file_path,
            )
            if parse_images:
                logger.debug("parse_images=True, but OCR for DOCX is not implemented.")
        logger.info(
            "Extracted text from DOCX '%s' (%d characters).", file_path, len(text)
        )
        return text if text else ""
    except Exception as e:
        logger.exception("Error extracting text from DOCX '%s': %s", file_path, e)
        raise


# def extract_text_from_image(file_path: str) -> str:
#     """
#     Extract text from an image file using OCR (pytesseract).
#     Handles common image formats and multi-page TIFF files.
#     """
#     try:
#         image = Image.open(file_path)
#         text_content = []
#         # For multi-page images (e.g. TIFF), iterate over all frames.
#         for frame in ImageSequence.Iterator(image):
#             frame_text = pytesseract.image_to_string(frame)
#             text_content.append(frame_text)
#         combined_text = "\n".join(text_content)
#         logger.info(
#             "Extracted OCR text from image '%s' (%d characters).",
#             file_path,
#             len(combined_text),
#         )
#         return combined_text
#     except Exception as e:
#         logger.exception("Error extracting text from image '%s': %s", file_path, e)
#         raise


# def extract_text_from_file(file_path: str, parse_images: bool = False) -> str:
#     """
#     Extract text from a file based on its extension.

#     Supported formats:
#       - PDF: Uses PyPDF2 (with optional OCR).
#       - DOCX: Uses docx2txt.
#       - DOC: Not implemented (suggest conversion to DOCX).
#       - Images (JPG, JPEG, PNG, TIFF): Uses OCR via pytesseract.

#     Args:
#         file_path (str): Path to the file.
#         parse_images (bool): If True, attempt OCR on PDF/DOCX pages without extractable text.

#     Returns:
#         str: The extracted text.
#     """
#     try:
#         _, ext = os.path.splitext(file_path)
#         ext = ext.lower()
#         if ext == ".pdf":
#             return extract_text_from_pdf(file_path, parse_images=parse_images)
#         elif ext == ".docx":
#             return extract_text_from_docx(file_path, parse_images=parse_images)
#         elif ext == ".doc":
#             logger.warning("Parsing .doc files is not implemented. Convert to .docx.")
#             raise NotImplementedError("Parsing .doc files is not implemented.")
#         elif ext in [".jpg", ".jpeg", ".png", ".tiff"]:
#             return extract_text_from_image(file_path)
#         else:
#             logger.warning("Unsupported extension '%s' for file '%s'.", ext, file_path)
#             raise NotImplementedError(f"Unsupported extension: {ext}")
#     except Exception as e:
#         logger.exception("Error extracting text from file '%s': %s", file_path, e)
#         raise
