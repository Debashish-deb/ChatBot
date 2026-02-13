import os
import base64
from typing import Optional, List
from PIL import Image
import io
import PyPDF2
from app.logging_config import logger

class MediaService:
    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from a PDF file"""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            return f"Error: {str(e)}"

    def get_image_format(self, data_base64: str) -> str:
        """Get image format from base64 data"""
        try:
            # Simple check for common formats
            if data_base64.startswith("data:image/jpeg"): return "jpeg"
            if data_base64.startswith("data:image/png"): return "png"
            if data_base64.startswith("data:image/gif"): return "gif"
            if data_base64.startswith("data:image/webp"): return "webp"
            return "jpeg" # Default
        except:
            return "jpeg"

    def process_image(self, data_base64: str) -> str:
        """
        Placeholder for advanced image processing.
        In a real app, this might perform local OCR or resizing.
        For now, we return a summary or keep it as is for the LLM.
        """
        return "Image processed for analysis."

media_service = MediaService()
