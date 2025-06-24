"""
Response models for the API.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.base import TaskStatus, TaskState

class TranslationResult(BaseModel):
    """Translation result model."""
    
    id: str = Field(..., description="Unique identifier for the translation")
    translation: str = Field(..., description="Translated text")
    timestamp: datetime = Field(..., description="Timestamp of the translation")
    processing_time: float = Field(..., description="Processing time in seconds")
    is_streaming: bool = Field(False, description="Whether the translation is streaming")
    stage: str = Field("completed", description="Current stage of the translation process")

class ErrorResponse(BaseModel):
    """Error response model."""
    
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")

class AppStatus(BaseModel):
    """Application status model."""
    
    status: TaskStatus = Field(..., description="Current application status")
    monitoring_paused: bool = Field(..., description="Whether monitoring is paused")
    selected_window: Optional[Dict[str, Any]] = Field(None, description="Currently selected window")
    task_state: TaskState = Field(..., description="Current task state")
    settings: Dict[str, Any] = Field(..., description="Application settings")
    translation_count: int = Field(0, description="Number of translations performed")

class ModelInfo(BaseModel):
    """Model information model."""
    
    id: str = Field(..., description="Model identifier")
    object: str = Field("model", description="Object type")
    type: str = Field(..., description="Model type (e.g., llm, vlm, ocr)")
    publisher: Optional[str] = Field(None, description="Model publisher")
    state: str = Field("available", description="Model state")

class ModelListResponse(BaseModel):
    """Model list response model."""
    
    models: List[Dict[str, Any]] = Field(..., description="List of models")

class WindowInfo(BaseModel):
    """Window information model."""
    
    hwnd: int = Field(..., description="Window handle")
    title: str = Field(..., description="Window title")
    is_visible: bool = Field(True, description="Whether the window is visible")

class WindowListResponse(BaseModel):
    """Window list response model."""
    
    windows: List[WindowInfo] = Field(..., description="List of windows")

class WindowSelectionRequest(BaseModel):
    """Window selection request model."""
    
    hwnd: Optional[int] = Field(None, description="Window handle")
    title: Optional[str] = Field(None, description="Window title")

class MonitorControlRequest(BaseModel):
    """Monitor control request model."""
    
    action: str = Field(..., description="Control action (start, pause, stop)")
