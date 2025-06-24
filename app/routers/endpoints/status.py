"""
Status and settings endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any

from app.models import (
    AppStatus, 
    TaskStatus, 
    TaskState, 
    AppSettings, 
    SettingsUpdateRequest,
    WindowInfo
)
from app.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)

# Create router
router = APIRouter(tags=["status"])

# In-memory app state (would be replaced with a proper state manager in a larger app)
app_state = {
    "status": TaskStatus.IDLE,
    "monitoring_paused": True,
    "selected_window": None,
    "task_state": TaskState(is_running=False, elapsed_time=0, start_time=None),
    "settings": AppSettings(
        check_interval=3,
        similarity_threshold=0.90,
        timeout=45
    ),
    "translation_count": 0,
    "results": []
}

@router.get("/status", response_model=AppStatus)
async def get_status():
    """Get the current application status."""
    logger.debug("Status requested")
    # Convert AppSettings object to dictionary for AppStatus model
    settings_dict = app_state["settings"].model_dump()
    
    # Convert WindowInfo object to dictionary if it exists
    selected_window = None
    if app_state["selected_window"] is not None:
        selected_window = app_state["selected_window"].model_dump()
    
    return AppStatus(
        status=app_state["status"],
        monitoring_paused=app_state["monitoring_paused"],
        selected_window=selected_window,
        task_state=app_state["task_state"],
        settings=settings_dict,
        translation_count=app_state["translation_count"]
    )

@router.get("/settings", response_model=AppSettings)
async def get_settings():
    """Get the current application settings."""
    logger.debug("Settings requested")
    return app_state["settings"]

@router.patch("/settings", response_model=AppSettings)
async def update_settings(settings: SettingsUpdateRequest):
    """Update application settings."""
    logger.info(f"Updating settings: {settings.model_dump(exclude_unset=True)}")
    
    # Update only the fields that are provided
    settings_dict = settings.model_dump(exclude_unset=True)
    
    # Update the settings
    for key, value in settings_dict.items():
        if hasattr(app_state["settings"], key):
            setattr(app_state["settings"], key, value)
    
    return app_state["settings"]

@router.get("/models/settings", response_model=Dict[str, str])
async def get_model_settings():
    """Get the current model settings."""
    logger.debug("Model settings requested")
    return {
        "ocr_model_id": app_state["settings"].models.ocr_model_id,
        "translation_model_id": app_state["settings"].models.translation_model_id
    }

@router.patch("/models/settings", response_model=Dict[str, str])
async def update_model_settings(settings: Dict[str, str]):
    """Update model settings."""
    logger.info(f"Updating model settings: {settings}")
    
    if "ocr_model_id" in settings:
        app_state["settings"].models.ocr_model_id = settings["ocr_model_id"]
    
    if "translation_model_id" in settings:
        app_state["settings"].models.translation_model_id = settings["translation_model_id"]
    
    return {
        "ocr_model_id": app_state["settings"].models.ocr_model_id,
        "translation_model_id": app_state["settings"].models.translation_model_id
    }
