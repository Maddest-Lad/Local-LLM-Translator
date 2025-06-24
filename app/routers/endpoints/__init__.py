"""
API endpoints package.
"""

from app.routers.endpoints.status import router as status_router
from app.routers.endpoints.windows import router as windows_router
from app.routers.endpoints.translation import router as translation_router
from app.routers.endpoints.models import router as models_router

__all__ = [
    'status_router',
    'windows_router',
    'translation_router',
    'models_router',
]
