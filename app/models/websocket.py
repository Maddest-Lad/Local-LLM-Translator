"""
WebSocket message models.
"""

from typing import Dict, Any, TypeVar, Generic
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel

from app.models.responses import TranslationResult, AppStatus, ErrorResponse
from app.models.base import TaskState

class WSMessage(BaseModel):
    """Base WebSocket message model."""
    
    type: str = Field(..., description="Message type")
    data: Dict[str, Any] = Field({}, description="Message data")

# Define a generic type for typed WebSocket messages
T = TypeVar('T')

class TypedWSMessage(GenericModel, Generic[T]):
    """Typed WebSocket message model."""
    
    type: str = Field(..., description="Message type")
    data: T = Field(..., description="Message data")

class TranslationResultMessage(TypedWSMessage[TranslationResult]):
    """Translation result WebSocket message."""
    
    type: str = "translation_result"

class StatusUpdateMessage(TypedWSMessage[AppStatus]):
    """Status update WebSocket message."""
    
    type: str = "status_update"

class ErrorResponseMessage(TypedWSMessage[ErrorResponse]):
    """Error response WebSocket message."""
    
    type: str = "error"

class TaskProgressMessage(TypedWSMessage[TaskState]):
    """Task progress WebSocket message."""
    
    type: str = "task_progress"
