"""
Models package for the application.
"""

from app.models.base import (
    TaskStatus,
    TaskState,
    AppSettings,
    ModelSettings,
)

from app.models.requests import (
    SettingsUpdateRequest,
)

from app.models.responses import (
    TranslationResult,
    ErrorResponse,
    AppStatus,
    ModelInfo,
    ModelListResponse,
    WindowInfo,
    WindowListResponse,
    WindowSelectionRequest,
    MonitorControlRequest,
)

from app.models.websocket import (
    WSMessage,
    TypedWSMessage,
    TranslationResultMessage,
    StatusUpdateMessage,
    ErrorResponseMessage,
    TaskProgressMessage,
)

__all__ = [
    # Base models
    'TaskStatus',
    'TaskState',
    'AppSettings',
    'ModelSettings',
    'SettingsUpdateRequest',
    
    # Response models
    'TranslationResult',
    'ErrorResponse',
    'AppStatus',
    'ModelInfo',
    'ModelListResponse',
    'WindowInfo',
    'WindowListResponse',
    'WindowSelectionRequest',
    'MonitorControlRequest',
    
    # WebSocket models
    'WSMessage',
    'TypedWSMessage',
    'TranslationResultMessage',
    'StatusUpdateMessage',
    'ErrorResponseMessage',
    'TaskProgressMessage',
]
