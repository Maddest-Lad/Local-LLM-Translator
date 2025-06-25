"""
Service for capturing and translating screen content
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Optional, Callable, Dict, Any
from PIL import Image
import threading

from app.utils.logging import get_logger, log_function_call
from app.utils.window import screenshot_window, is_window_visible
from app.utils.image import encode_image, images_are_similar
from app.services.ocr_service import create_ocr_provider
from app.services.translator_service import translate_text
from app.models.responses import TranslationResult

# Initialize logger
logger = get_logger(__name__)

class ScreenTranslationService:
    """Service for capturing and translating screen content."""
    
    def __init__(self):
        self.last_image = None
        self.last_hwnd = None
        
    @log_function_call
    async def translate_screen(
        self,
        hwnd: int,
        timeout: int = 45,
        stream_callback: Optional[Callable[[TranslationResult], None]] = None,
        ocr_model_id: str = "nanonets-ocr-s",
        translation_model_id: str = "gemma-3-12b-it"
    ) -> TranslationResult:
        """
        Capture screen content and translate it.
        
        Args:
            hwnd: Window handle to capture
            timeout: API timeout in seconds
            stream_callback: Optional callback for streaming updates
            ocr_model_id: Model ID for OCR
            translation_model_id: Model ID for translation
            
        Returns:
            TranslationResult object with the translation
        """
        start_time = time.time()
        translation_id = str(uuid.uuid4())
        
        # Get the current event loop for callback scheduling
        main_loop = asyncio.get_running_loop()
        
        # Create initial result with empty translation
        result = TranslationResult(
            id=translation_id,
            translation="",
            timestamp=datetime.now(),
            processing_time=0,
            is_streaming=True,
            stage="capturing"
        )
        
        if stream_callback:
            stream_callback(result)
        
        try:
            # Take screenshot
            logger.info(f"Taking screenshot of window {hwnd}")
            loop = asyncio.get_event_loop()
            screenshot = await loop.run_in_executor(None, screenshot_window, hwnd)
            
            # Update result to OCR stage
            result = TranslationResult(
                id=translation_id,
                translation="",
                timestamp=datetime.now(),
                processing_time=time.time() - start_time,
                is_streaming=True,
                stage="ocr"
            )
            
            if stream_callback:
                stream_callback(result)
            
            # Encode image
            img_b64 = await loop.run_in_executor(None, encode_image, screenshot)
            
            # Extract text using OCR
            logger.info(f"Extracting text using OCR model {ocr_model_id}")
            ocr_provider = create_ocr_provider(ocr_model_id)
            
            # Create a safe callback wrapper for OCR progress updates
            def safe_ocr_progress_callback():
                def update_progress():
                    while not stop_event.is_set():
                        current_time = time.time()
                        total_elapsed = current_time - start_time
                        
                        # Create progress result
                        progress_result = TranslationResult(
                            id=translation_id,
                            translation="Running OCR...",
                            timestamp=datetime.now(),
                            processing_time=total_elapsed,
                            is_streaming=True,
                            stage="ocr"
                        )
                        
                        # Schedule callback in main thread
                        if stream_callback:
                            try:
                                main_loop.call_soon_threadsafe(lambda: stream_callback(progress_result))
                            except Exception as e:
                                logger.error(f"Error scheduling OCR progress callback: {e}")
                                break
                        
                        time.sleep(0.1)
                
                # Create stop event and start thread
                stop_event = threading.Event()
                progress_thread = threading.Thread(target=update_progress, daemon=True)
                progress_thread.start()
                
                return stop_event, progress_thread
            
            # Start OCR with progress updates
            stop_event, progress_thread = safe_ocr_progress_callback()
            
            try:
                # Run OCR
                extracted_text = await loop.run_in_executor(
                    None, 
                    ocr_provider.extract_text, 
                    img_b64, 
                    timeout
                )
            finally:
                # Stop progress updates
                stop_event.set()
                progress_thread.join(timeout=1.0)
            
            if not extracted_text:
                logger.warning("No text extracted from image")
                result = TranslationResult(
                    id=translation_id,
                    translation="No text detected in image",
                    timestamp=datetime.now(),
                    processing_time=time.time() - start_time,
                    is_streaming=False,
                    stage="error"
                )
                
                if stream_callback:
                    stream_callback(result)
                
                return result
            
            # Update result to translating stage
            result = TranslationResult(
                id=translation_id,
                translation="",
                timestamp=datetime.now(),
                processing_time=time.time() - start_time,
                is_streaming=True,
                stage="translating"
            )
            
            if stream_callback:
                stream_callback(result)
            
            # Create a safe translation callback wrapper
            def safe_translation_callback(partial_translation: str):
                current_time = time.time()
                processing_time = current_time - start_time
                
                # Update the result with the partial translation
                progress_result = TranslationResult(
                    id=translation_id,
                    translation=partial_translation,
                    timestamp=datetime.now(),
                    processing_time=processing_time,
                    is_streaming=True,
                    stage="translating"
                )
                
                # Schedule callback in main thread safely
                if stream_callback:
                    try:
                        main_loop.call_soon_threadsafe(lambda: stream_callback(progress_result))
                    except Exception as e:
                        logger.error(f"Error scheduling translation callback: {e}")
            
            # Run translation with streaming
            if stream_callback:
                # Execute translation in thread pool with safe callback
                final_translation = await loop.run_in_executor(
                    None,
                    lambda: translate_text(
                        extracted_text,
                        timeout,
                        safe_translation_callback,
                        translation_model_id
                    )
                )
            else:
                # Non-streaming translation
                final_translation = await loop.run_in_executor(
                    None,
                    lambda: translate_text(
                        extracted_text,
                        timeout,
                        None,
                        translation_model_id
                    )
                )
            
            processing_time = time.time() - start_time
            
            # Final update with completed translation
            result = TranslationResult(
                id=translation_id,
                translation=final_translation if final_translation else "Translation failed",
                timestamp=datetime.now(),
                processing_time=processing_time,
                is_streaming=False,
                stage="completed"
            )
            
            if stream_callback:
                stream_callback(result)
            
            # Cache the image and window handle
            self.last_image = screenshot
            self.last_hwnd = hwnd
            
            return result
            
        except Exception as e:
            logger.error(f"Screen translation error: {e}")
            
            # Return error result
            result = TranslationResult(
                id=translation_id,
                translation=f"Error: {str(e)}",
                timestamp=datetime.now(),
                processing_time=time.time() - start_time,
                is_streaming=False,
                stage="error"
            )
            
            if stream_callback:
                stream_callback(result)
            
            return result
    
    @log_function_call
    def should_process_new_image(self, hwnd: int, similarity_threshold: float = 0.90) -> bool:
        """
        Check if a new screenshot should be processed based on similarity to the last one.
        
        Args:
            hwnd: Window handle to check
            similarity_threshold: Threshold for image similarity
            
        Returns:
            True if the image should be processed, False otherwise
        """
        # If no previous image or different window, always process
        if self.last_image is None or self.last_hwnd != hwnd:
            logger.debug("No previous image or different window, processing new image")
            return True
        
        # If window is not visible, don't process
        if not is_window_visible(hwnd):
            logger.debug("Window is not visible, skipping processing")
            return False
        
        # Take a new screenshot
        try:
            new_screenshot = screenshot_window(hwnd)
            
            # Compare with previous image
            is_similar = images_are_similar(
                new_screenshot, self.last_image, similarity_threshold
            )
            
            if is_similar:
                logger.debug("New image is similar to previous, skipping processing")
                return False
            else:
                logger.debug("New image is different from previous, processing")
                return True
                
        except Exception as e:
            logger.error(f"Error checking image similarity: {e}")
            return True  # Process on error to be safe
    
    @log_function_call
    def reset_cache(self):
        """Reset the image cache."""
        self.last_image = None
        self.last_hwnd = None
        logger.info("Image cache reset")