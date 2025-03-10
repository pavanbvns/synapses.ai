import os
import logging
from typing import Optional
from pdf2image import convert_from_path
import PyPDF2
import docx2txt
from PIL import Image, ImageSequence
import pytesseract

from utils.config import config

logger = logging.getLogger(__name__)
logging_level_str = config.get("logging_level", "DEBUG")
numeric_level = getattr(logging, logging_level_str.upper(), logging.DEBUG)
logger.setLevel(numeric_level)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def extract_text_from_pdf(file_path: str, parse_images: bool = True) -> str:
    """
    Extract text from a PDF file using PyPDF2.
    If parse_images is True and a page has no extractable text, convert that page to an image
    using pdf2image and then apply OCR with pytesseract.
    
    Prerequisites:
      - Install pdf2image and pytesseract.
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
                    logger.debug("No extractable text on page %d of '%s'.", page_number, file_path)
                    if parse_images:
                        logger.debug("OCR enabled. Converting page %d to image.", page_number)
                        try:
                            # Convert only the current page to an image.
                            images = convert_from_path(file_path, first_page=page_number+1, last_page=page_number+1)
                            if images:
                                ocr_text = pytesseract.image_to_string(images[0])
                                if ocr_text.strip():
                                    logger.debug("OCR extracted text from page %d.", page_number)
                                    text_content.append(ocr_text)
                                else:
                                    logger.warning("OCR did not extract any text from page %d.", page_number)
                            else:
                                logger.warning("No image returned for page %d.", page_number)
                        except Exception as ocr_e:
                            logger.exception("Error during OCR on page %d of '%s': %s", page_number, file_path, ocr_e)
                    else:
                        logger.debug("OCR disabled; skipping OCR for page %d.", page_number)
        combined_text = "\n".join(text_content)
        logger.info("Extracted text from PDF '%s' (%d characters).", file_path, len(combined_text))
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
    If parse_images is True, you could add OCR for embedded images (not implemented here).
    """
    try:
        text = docx2txt.process(file_path)
        if not text:
            logger.debug("DOCX '%s' returned empty text. Possibly image-based content.", file_path)
            if parse_images:
                logger.debug("parse_images=True, but OCR for DOCX is not implemented.")
        logger.info("Extracted text from DOCX '%s' (%d characters).", file_path, len(text))
        return text if text else ""
    except Exception as e:
        logger.exception("Error extracting text from DOCX '%s': %s", file_path, e)
        raise

def extract_text_from_image(file_path: str) -> str:
    """
    Extract text from an image file using OCR (pytesseract).
    This function handles standard image formats (jpg, jpeg, png) and multi-page TIFF files.
    """
    try:
        image = Image.open(file_path)
        text_content = []
        # If the image is multi-page (like TIFF), iterate over all frames.
        for frame in ImageSequence.Iterator(image):
            frame_text = pytesseract.image_to_string(frame)
            text_content.append(frame_text)
        combined_text = "\n".join(text_content)
        logger.info("Extracted OCR text from image '%s' (%d characters).", file_path, len(combined_text))
        return combined_text
    except Exception as e:
        logger.exception("Error extracting text from image '%s': %s", file_path, e)
        raise

def extract_text_from_file(file_path: str, parse_images: bool = False) -> str:
    """
    Extract text from a file based on its extension.
    
    Supported formats:
      - PDF: Extract text using PyPDF2 (with optional OCR support).
      - DOCX: Extract text using docx2txt.
      - DOC: Not implemented; suggest converting to DOCX.
      - Images (JPG, JPEG, PNG, TIFF): Extract text via OCR.
    
    Args:
        file_path (str): Path to the file.
        parse_images (bool): For PDF/DOCX files, if True, attempt OCR on pages without extractable text.
                              For images, OCR is always applied.
    
    Returns:
        str: The extracted text.
    """
    try:
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        if ext == ".pdf":
            return extract_text_from_pdf(file_path, parse_images=parse_images)
        elif ext in [".docx"]:
            return extract_text_from_docx(file_path, parse_images=parse_images)
        elif ext == ".doc":
            logger.warning("Support for .doc is not implemented. Please convert to .docx.")
            raise NotImplementedError("Parsing .doc files is not implemented.")
        elif ext in [".jpg", ".jpeg", ".png", ".tiff"]:
            return extract_text_from_image(file_path)
        else:
            logger.warning("Unsupported extension '%s' for file '%s'.", ext, file_path)
            raise NotImplementedError(f"Unsupported extension: {ext}")
    except Exception as e:
        logger.exception("Error extracting text from file '%s': %s", file_path, e)
        raise
