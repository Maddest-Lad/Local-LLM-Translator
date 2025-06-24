"""
Base models for the application.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    """Task status enum."""
    
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"

class TaskState(BaseModel):
    """Task state model."""
    
    is_running: bool = Field(False, description="Whether the task is running")
    elapsed_time: float = Field(0, description="Elapsed time in seconds")
    start_time: Optional[datetime] = Field(None, description="Task start time")

class ModelSettings(BaseModel):
    """Model settings model."""
    
    ocr_model_id: str = Field("nanonets-ocr-s", description="OCR model ID")
    translation_model_id: str = Field("gemma-3-12b-it", description="Translation model ID")

class AppSettings(BaseModel):
    """Application settings model."""
    
    check_interval: int = Field(3, description="Check interval in seconds")
    similarity_threshold: float = Field(0.90, description="Image similarity threshold")
    timeout: int = Field(45, description="API timeout in seconds")
    models: ModelSettings = Field(default_factory=lambda: ModelSettings(), description="Model settings")
