"""
Window management endpoints.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import win32gui
import asyncio

from app.models import WindowInfo, WindowListResponse, WindowSelectionRequest
from app.utils.logging import get_logger
from app.utils.window import is_window_visible, get_window_title, get_desktop_window
from app.routers.endpoints.status import app_state

# Initialize logger
logger = get_logger(__name__)

# Create router
router = APIRouter(tags=["windows"])

def enum_windows_callback(hwnd, windows):
    """Callback for EnumWindows."""
    if is_window_visible(hwnd):
        title = get_window_title(hwnd)
        if title:  # Only include windows with titles
            windows.append(WindowInfo(
                hwnd=hwnd,
                title=title,
                is_visible=True
            ))

@router.get("/windows", response_model=WindowListResponse)
async def get_windows():
    """Get a list of visible windows."""
    logger.debug("Windows list requested")
    
    # Run the window enumeration in a thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    windows = await loop.run_in_executor(None, _get_windows_sync)
    
    # Sort windows by title
    windows.sort(key=lambda w: w.title.lower())
    
    return WindowListResponse(windows=windows)

def _get_windows_sync():
    """Synchronous function to get windows list."""
    windows = []
    win32gui.EnumWindows(enum_windows_callback, windows)
    return windows

@router.post("/window/select")
async def select_window(request: WindowSelectionRequest):
    """Select a window for monitoring."""
    if request.hwnd is None:
        # Full screen mode (desktop)
        hwnd = get_desktop_window()
        title = "Full Screen"
    else:
        hwnd = request.hwnd
        title = request.title or get_window_title(hwnd)
    
    logger.info(f"Selected window: {title} (hwnd: {hwnd})")
    
    # Update app state
    app_state["selected_window"] = WindowInfo(
        hwnd=hwnd,
        title=title,
        is_visible=True
    )
    
    return {"status": "success", "window": {"hwnd": hwnd, "title": title}}
