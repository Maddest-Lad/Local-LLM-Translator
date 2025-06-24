"""
Window management utilities.
"""

import win32gui
import win32ui
import win32con
from PIL import Image
import numpy as np
from typing import Tuple, Optional
import ctypes
from ctypes import wintypes

from app.utils.logging import get_logger, log_function_call

# Initialize logger
logger = get_logger(__name__)

@log_function_call
def get_window_title(hwnd: int) -> str:
    """
    Get the title of a window.
    
    Args:
        hwnd: Window handle
        
    Returns:
        Window title
    """
    try:
        return win32gui.GetWindowText(hwnd)
    except Exception as e:
        logger.error(f"Error getting window title: {e}")
        return ""

@log_function_call
def is_window_visible(hwnd: int) -> bool:
    """
    Check if a window is visible.
    
    Args:
        hwnd: Window handle
        
    Returns:
        True if the window is visible, False otherwise
    """
    try:
        return bool(win32gui.IsWindowVisible(hwnd))
    except Exception as e:
        logger.error(f"Error checking window visibility: {e}")
        return False

@log_function_call
def get_desktop_window() -> int:
    """
    Get the desktop window handle.
    
    Returns:
        Desktop window handle
    """
    return win32gui.GetDesktopWindow()

@log_function_call
def get_window_rect(hwnd: int) -> Tuple[int, int, int, int]:
    """
    Get the rectangle of a window.
    
    Args:
        hwnd: Window handle
        
    Returns:
        Tuple of (left, top, right, bottom)
    """
    try:
        return win32gui.GetWindowRect(hwnd)
    except Exception as e:
        logger.error(f"Error getting window rect: {e}")
        return (0, 0, 0, 0)

@log_function_call
def screenshot_window(hwnd: int) -> Image.Image:
    """
    Take a screenshot of a window.
    
    Args:
        hwnd: Window handle
        
    Returns:
        PIL Image of the window
    """
    try:
        # Get window dimensions
        left, top, right, bottom = get_window_rect(hwnd)
        width = right - left
        height = bottom - top
        
        # Check if it's the desktop window
        if hwnd == get_desktop_window():
            # For desktop, use a different approach
            return screenshot_desktop()
        
        # Create device context
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        
        # Create bitmap
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bitmap)
        
        # Copy window contents to bitmap
        result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
        if not result:
            logger.warning("PrintWindow failed, falling back to BitBlt")
            save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)
        
        # Convert to PIL Image
        bmpinfo = save_bitmap.GetInfo()
        bmpstr = save_bitmap.GetBitmapBits(True)
        img = Image.frombuffer(
            'RGB',
            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
            bmpstr, 'raw', 'BGRX', 0, 1
        )
        
        # Clean up
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        win32gui.DeleteObject(save_bitmap.GetHandle())
        
        return img
    except Exception as e:
        logger.error(f"Error taking screenshot: {e}")
        # Return a blank image
        return Image.new('RGB', (800, 600), color='white')

@log_function_call
def screenshot_desktop() -> Image.Image:
    """
    Take a screenshot of the desktop.
    
    Returns:
        PIL Image of the desktop
    """
    try:
        # Get screen dimensions
        user32 = ctypes.windll.user32
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        
        # Create device context
        hwnd_dc = win32gui.GetWindowDC(get_desktop_window())
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        
        # Create bitmap
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, screen_width, screen_height)
        save_dc.SelectObject(save_bitmap)
        
        # Copy screen contents to bitmap
        save_dc.BitBlt((0, 0), (screen_width, screen_height), mfc_dc, (0, 0), win32con.SRCCOPY)
        
        # Convert to PIL Image
        bmpinfo = save_bitmap.GetInfo()
        bmpstr = save_bitmap.GetBitmapBits(True)
        img = Image.frombuffer(
            'RGB',
            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
            bmpstr, 'raw', 'BGRX', 0, 1
        )
        
        # Clean up
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(get_desktop_window(), hwnd_dc)
        win32gui.DeleteObject(save_bitmap.GetHandle())
        
        return img
    except Exception as e:
        logger.error(f"Error taking desktop screenshot: {e}")
        # Return a blank image
        return Image.new('RGB', (800, 600), color='white')
