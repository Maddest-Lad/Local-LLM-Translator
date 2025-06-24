"""
Utilities package for the application.
"""

from app.utils.logging import (
    setup_logging,
    get_logger,
    log_function_call,
    log_execution_time,
)

from app.utils.window import (
    get_window_title,
    is_window_visible,
    get_desktop_window,
    get_window_rect,
    screenshot_window,
    screenshot_desktop,
)

from app.utils.image import (
    encode_image,
    decode_image,
    pil_to_cv2,
    cv2_to_pil,
    images_are_similar,
)

__all__ = [
    # Logging utilities
    'setup_logging',
    'get_logger',
    'log_function_call',
    'log_execution_time',
    
    # Window utilities
    'get_window_title',
    'is_window_visible',
    'get_desktop_window',
    'get_window_rect',
    'screenshot_window',
    'screenshot_desktop',
    
    # Image utilities
    'encode_image',
    'decode_image',
    'pil_to_cv2',
    'cv2_to_pil',
    'images_are_similar',
]
