"""
Service for managing models and their availability.
"""

import requests
from typing import List, Dict, Any, Optional
from app.utils.logging import get_logger, log_function_call

# Initialize logger
logger = get_logger(__name__)

class ModelService:
    """Service for managing models and their availability."""
    
    def __init__(self, base_url="http://127.0.0.1:7860"):
        self.base_url = base_url
        self.lm_studio_api_url = f"{base_url}/api/v0"
        self.openai_compat_api_url = f"{base_url}/v1"
        logger.info(f"Initialized ModelService with base URL: {base_url}")
    
    @log_function_call
    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Fetch available models from LM Studio API.
        
        Returns:
            List of model information dictionaries
        """
        try:
            response = requests.get(f"{self.lm_studio_api_url}/models", timeout=5)
            response.raise_for_status()
            models = response.json().get("data", [])
            logger.info(f"Retrieved {len(models)} models from API")
            return models
        except Exception as e:
            logger.error(f"Error fetching models: {e}")
            return []
    
    @log_function_call
    def get_ocr_models(self) -> List[Dict[str, Any]]:
        """
        Get models suitable for OCR (vision models).
        
        Returns:
            List of OCR-capable model information dictionaries
        """
        models = self.get_available_models()
        # Filter for vision models (VLMs) or models with specific naming patterns
        ocr_models = [m for m in models if m.get("type") == "vlm" or "ocr" in m.get("id", "").lower()]
        
        # Add Tesseract as a special option
        tesseract_model = {
            "id": "tesseract",
            "object": "model",
            "type": "ocr",
            "publisher": "tesseract-ocr",
            "state": "available"
        }
        
        # Add Tesseract at the beginning of the list
        result = [tesseract_model] + ocr_models
        logger.info(f"Found {len(result)} OCR-capable models")
        return result
    
    @log_function_call
    def get_translation_models(self) -> List[Dict[str, Any]]:
        """
        Get models suitable for translation (text models).
        
        Returns:
            List of translation-capable model information dictionaries
        """
        models = self.get_available_models()
        # Filter for language models (LLMs)
        result = [m for m in models if m.get("type") in ["llm", "vlm"]]
        logger.info(f"Found {len(result)} translation-capable models")
        return result
