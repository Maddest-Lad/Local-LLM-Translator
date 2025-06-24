from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

class ThemeMode(str, Enum):
    LIGHT = "light"
    DARK = "dark"

# Request Models
class SettingsUpdateRequest(BaseModel):
    check_interval: Optional[int] = Field(None, ge=1, le=10, description="Check interval in seconds")
    similarity_threshold: Optional[float] = Field(None, ge=0.5, le=1.0, description="Similarity threshold for image comparison")
    timeout: Optional[int] = Field(None, ge=10, le=120, description="Processing timeout in seconds")

class WindowSelectionRequest(BaseModel):
    hwnd: Optional[int] = Field(None, description="Window handle, null for full screen")
    title: Optional[str] = Field(None, description="Window title for display")

class MonitorControlRequest(BaseModel):
    action: str = Field(..., pattern="^(start|pause|stop)$")

class TranslationRequest(BaseModel):
    force: bool = Field(False, description="Force translation even if task is running")

# Response Models
class WindowInfo(BaseModel):
    hwnd: int
    title: str
    is_visible: bool

class WindowListResponse(BaseModel):
    windows: List[WindowInfo]

class TranslationResult(BaseModel):
    id: str = Field(..., description="Unique identifier for this translation")
    translation: str
    timestamp: datetime
    processing_time: Optional[float] = Field(None, description="Time taken to process in seconds")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TaskState(BaseModel):
    is_running: bool
    elapsed_time: float = Field(0, description="Elapsed time in seconds")
    start_time: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class AppSettings(BaseModel):
    check_interval: int = Field(3, ge=1, le=10)
    similarity_threshold: float = Field(0.90, ge=0.5, le=1.0)
    timeout: int = Field(45, ge=10, le=120)
    theme: ThemeMode = ThemeMode.DARK

class AppStatus(BaseModel):
    status: TaskStatus
    monitoring_paused: bool
    selected_window: Optional[WindowInfo] = None
    task_state: TaskState
    settings: AppSettings
    translation_count: int = Field(0, description="Total number of translations")

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# WebSocket Message Models
class WSMessageType(str, Enum):
    TRANSLATION_RESULT = "translation_result"
    STATUS_UPDATE = "status_update"
    ERROR = "error"
    TASK_PROGRESS = "task_progress"

class WSMessage(BaseModel):
    type: WSMessageType
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TranslationResultMessage(WSMessage):
    type: WSMessageType = WSMessageType.TRANSLATION_RESULT
    data: TranslationResult

class StatusUpdateMessage(WSMessage):
    type: WSMessageType = WSMessageType.STATUS_UPDATE
    data: AppStatus

class ErrorMessage(WSMessage):
    type: WSMessageType = WSMessageType.ERROR
    data: ErrorResponse

class TaskProgressMessage(WSMessage):
    type: WSMessageType = WSMessageType.TASK_PROGRESS
    data: TaskState