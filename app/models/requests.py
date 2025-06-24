"""
Request models for the API.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class SettingsUpdateRequest(BaseModel):
    """Settings update request model."""
    
    check_interval: Optional[int] = Field(None, description="Check interval in seconds")
    similarity_threshold: Optional[float] = Field(None, description="Image similarity threshold")
    timeout: Optional[int] = Field(None, description="API timeout in seconds")
    models: Optional[Dict[str, Any]] = Field(None, description="Model settings")
