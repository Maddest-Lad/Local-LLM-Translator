"""
OCR service for extracting text from images.
"""

from abc import ABC, abstractmethod
import requests
import base64
from app.utils.logging import get_logger, log_function_call

# Initialize logger
logger = get_logger(__name__)

class OCRProvider(ABC):
    """Abstract base class for OCR providers"""
    
    @abstractmethod
    def extract_text(self, image_b64: str, timeout: int = 45) -> str:
        """Extract text from base64 encoded image"""
        pass

class LLMBasedOCR(OCRProvider):
    """OCR provider that uses LLM/VLM models"""
    
    def __init__(self, model_id: str, api_url: str = "http://127.0.0.1:7860/v1/chat/completions"):
        self.model_id = model_id
        self.api_url = api_url
        logger.info(f"Initialized LLMBasedOCR with model {model_id}")
    
    @log_function_call
    def extract_text(self, image_b64: str, timeout: int = 45) -> str:
        prompt = (
            "Extract all visible text from the image. Include all text in the original language."
            "\n\n"
            "Respond ONLY with the extracted text, no explanations or formatting."
        )
        payload = {
            "model": self.model_id,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                    {"type": "text", "text": prompt},
                ]
            }],
            "temperature": 0.1,
            "max_tokens": 6000,
        }
        try:
            logger.debug(f"Sending OCR request to {self.api_url} with model {self.model_id}")
            resp = requests.post(self.api_url, json=payload, timeout=timeout)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            logger.debug(f"OCR successful, extracted {len(content)} characters")
            return content
        except Exception as e:
            logger.error(f"OCR API error: {e}")
            return ""

class TesseractOCR(OCRProvider):
    """OCR provider that uses Tesseract"""
    
    @log_function_call
    def extract_text(self, image_b64: str, timeout: int = 45) -> str:
        # Placeholder for future implementation
        # Would use pytesseract to extract text
        logger.warning("Tesseract OCR not implemented yet")
        return "Tesseract OCR not implemented yet"

@log_function_call
def create_ocr_provider(model_id: str) -> OCRProvider:
    """
    Factory function to create appropriate OCR provider.
    
    Args:
        model_id: The model ID to use for OCR
        
    Returns:
        An OCR provider instance
    """
    # Special case for Tesseract
    if model_id.lower() == "tesseract":
        logger.info("Creating Tesseract OCR provider")
        return TesseractOCR()
    else:
        # All other models are assumed to be LLM-based
        logger.info(f"Creating LLM-based OCR provider with model {model_id}")
        return LLMBasedOCR(model_id)
