"""
Model management endpoints.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from app.models import ModelInfo, ModelListResponse
from app.utils.logging import get_logger
from app.services.model_service import ModelService

# Initialize logger
logger = get_logger(__name__)

# Create router
router = APIRouter(tags=["models"])

# Create model service
model_service = ModelService()

@router.get("/models", response_model=ModelListResponse)
async def get_models():
    """Get a list of all available models."""
    logger.debug("Models list requested")
    
    # Get models from service
    models = model_service.get_available_models()
    
    return ModelListResponse(models=models)

@router.get("/models/ocr", response_model=ModelListResponse)
async def get_ocr_models():
    """Get a list of OCR-capable models."""
    logger.debug("OCR models list requested")
    
    # Get OCR models from service
    models = model_service.get_ocr_models()
    
    return ModelListResponse(models=models)

@router.get("/models/translation", response_model=ModelListResponse)
async def get_translation_models():
    """Get a list of translation-capable models."""
    logger.debug("Translation models list requested")
    
    # Get translation models from service
    models = model_service.get_translation_models()
    
    return ModelListResponse(models=models)
