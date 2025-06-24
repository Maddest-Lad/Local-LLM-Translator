"""
Routers package for the application.
"""

from app.routers.router import router as main_router, manager as websocket_manager
from app.routers.endpoints import (
    status_router,
    windows_router,
    translation_router,
    models_router,
)

# Include all endpoint routers in the main router
main_router.include_router(status_router, prefix="/api")
main_router.include_router(windows_router, prefix="/api")
main_router.include_router(translation_router, prefix="/api")
main_router.include_router(models_router, prefix="/api")

__all__ = [
    'main_router',
    'websocket_manager',
]
