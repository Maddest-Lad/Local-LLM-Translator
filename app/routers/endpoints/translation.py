"""
Translation endpoints
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
import asyncio
import uuid
from datetime import datetime
import time
import threading

from app.models import TranslationResult, MonitorControlRequest, TaskStatus
from app.utils.logging import get_logger
from app.services.screen_service import ScreenTranslationService
from app.routers.endpoints.status import app_state
from app.routers.router import manager
from app.models.websocket import TranslationResultMessage, StatusUpdateMessage, TaskProgressMessage

# Initialize logger
logger = get_logger(__name__)

# Create router
router = APIRouter(tags=["translation"])

# Create screen translation service
screen_service = ScreenTranslationService()

# Background task flag
translation_task_running = False
translation_task_cancel = False

# Use asyncio queue instead of threading queue
ws_message_queue = None
message_processor_task = None

# Lock for message processor management
message_processor_lock = asyncio.Lock()

async def ensure_message_processor():
    """Ensure the message processor is running."""
    global message_processor_task, ws_message_queue
    
    async with message_processor_lock:
        if message_processor_task is None or message_processor_task.done():
            # Create new queue if needed
            if ws_message_queue is None:
                ws_message_queue = asyncio.Queue()
            
            # Start new message processor task
            message_processor_task = asyncio.create_task(process_ws_messages())
            logger.info("Message processor started")

@router.get("/results", response_model=List[TranslationResult])
async def get_results():
    """Get all translation results."""
    logger.debug("Translation results requested")
    return app_state["results"]

@router.delete("/results")
async def clear_results():
    """Clear all translation results."""
    logger.info("Clearing all translation results")
    app_state["results"] = []
    app_state["translation_count"] = 0
    return {"status": "success", "message": "All translation results cleared"}

@router.delete("/results/{result_id}")
async def delete_result(result_id: str):
    """Delete a specific translation result."""
    logger.info(f"Deleting translation result {result_id}")
    
    # Find and remove the result
    for i, result in enumerate(app_state["results"]):
        if result.id == result_id:
            app_state["results"].pop(i)
            app_state["translation_count"] = len(app_state["results"])
            return {"status": "success", "message": f"Translation result {result_id} deleted"}
    
    raise HTTPException(status_code=404, detail=f"Translation result {result_id} not found")

@router.post("/monitor/control")
async def control_monitoring(request: MonitorControlRequest, background_tasks: BackgroundTasks):
    """Control the monitoring process (start, pause, stop)."""
    logger.info(f"Monitor control: {request.action}")
    
    # Ensure message processor is running FIRST
    await ensure_message_processor()
    
    if request.action == "start":
        app_state["monitoring_paused"] = False
        app_state["status"] = TaskStatus.RUNNING
        
        # Start the monitoring task if not already running
        global translation_task_running, translation_task_cancel
        if not translation_task_running:
            translation_task_cancel = False
            background_tasks.add_task(monitoring_task)
            
    elif request.action == "pause":
        app_state["monitoring_paused"] = True
        app_state["status"] = TaskStatus.PAUSED
        
    elif request.action == "stop":
        app_state["monitoring_paused"] = True
        app_state["status"] = TaskStatus.IDLE
        translation_task_cancel = True
    
    # Broadcast status update
    await broadcast_status()
    
    return {"status": "success", "action": request.action}

@router.post("/translate/force")
async def force_translation(background_tasks: BackgroundTasks):
    """Force a translation of the current window."""
    logger.info("Forcing translation")
    
    if app_state["selected_window"] is None:
        raise HTTPException(status_code=400, detail="No window selected")
    
    # Ensure message processor is running FIRST
    await ensure_message_processor()
    
    # Start a one-time translation task
    background_tasks.add_task(one_time_translation_task)
    
    return {"status": "success", "message": "Translation started"}

@router.post("/task/stop")
async def stop_task():
    """Stop the current translation task."""
    logger.info("Stopping translation task")
    
    global translation_task_cancel
    translation_task_cancel = True
    
    # Update task state
    app_state["task_state"] = app_state["task_state"].copy(update={"is_running": False})
    
    # Broadcast status update
    await broadcast_status()
    
    return {"status": "success", "message": "Translation task stopped"}

@router.post("/cache/reset")
async def reset_cache():
    """Reset the image cache."""
    logger.info("Resetting image cache")
    screen_service.reset_cache()
    return {"status": "success", "message": "Image cache reset"}

async def one_time_translation_task():
    """Run a one-time translation task."""
    if app_state["selected_window"] is None:
        logger.warning("No window selected for one-time translation")
        return
    
    # Ensure message processor is running
    await ensure_message_processor()
    
    # Store the main loop reference for callbacks
    await _ensure_loop_reference()
    
    # Update task state
    start_time = time.time()
    app_state["task_state"] = app_state["task_state"].copy(update={
        "is_running": True,
        "elapsed_time": 0,
        "start_time": datetime.now()
    })
    
    # Start a timer task to update progress continuously
    timer_task = asyncio.create_task(update_task_timer())
    
    # Broadcast task progress immediately
    await broadcast_task_progress()
    
    try:
        # Run translation
        result = await screen_service.translate_screen(
            hwnd=app_state["selected_window"].hwnd,
            timeout=app_state["settings"].timeout,
            stream_callback=stream_translation_callback,
            ocr_model_id=app_state["settings"].models.ocr_model_id,
            translation_model_id=app_state["settings"].models.translation_model_id
        )
        
        # Add result to results list (at the beginning)
        app_state["results"].insert(0, result)
        app_state["translation_count"] = len(app_state["results"])
        
    except Exception as e:
        logger.error(f"Translation error: {e}")
    finally:
        # Cancel the timer task
        timer_task.cancel()
        
        # Update task state
        app_state["task_state"] = app_state["task_state"].copy(update={"is_running": False})
        
        # Broadcast status update
        await broadcast_status()

async def monitoring_task():
    """Background task for continuous monitoring."""
    global translation_task_running, translation_task_cancel
    
    translation_task_running = True
    try:
        logger.info("Starting monitoring task")
        
        # Ensure message processor is running
        await ensure_message_processor()
        
        # Store the main loop reference for callbacks
        await _ensure_loop_reference()
        
        while not translation_task_cancel:
            # Check if monitoring is paused
            if app_state["monitoring_paused"]:
                await asyncio.sleep(1)
                continue
            
            # Check if a window is selected
            if app_state["selected_window"] is None:
                logger.warning("No window selected for monitoring")
                await asyncio.sleep(1)
                continue
            
            # Check if we should process a new image
            if screen_service.should_process_new_image(
                app_state["selected_window"].hwnd,
                app_state["settings"].similarity_threshold
            ):
                # Run one-time translation
                await one_time_translation_task()
            
            # Wait for the next check interval
            await asyncio.sleep(app_state["settings"].check_interval)
    
    except Exception as e:
        logger.error(f"Monitoring task error: {e}")
    finally:
        translation_task_running = False
        logger.info("Monitoring task stopped")

def stream_translation_callback(result: TranslationResult):
    """Callback for streaming translation updates."""
    # Update task state with elapsed time
    if app_state["task_state"].start_time:
        elapsed = (datetime.now() - app_state["task_state"].start_time).total_seconds()
        app_state["task_state"] = app_state["task_state"].copy(update={"elapsed_time": elapsed})
    
    # Get the event loop safely - this might be called from any thread
    try:
        # Try to get the running loop if we're in an async context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # We're not in an async context, try to get the main thread's loop
            # We need to store the main loop reference when the app starts
            loop = getattr(stream_translation_callback, '_main_loop', None)
            if loop is None:
                logger.error("No event loop available for WebSocket callback")
                return
        
        # Schedule the queue operations to run in the event loop
        if ws_message_queue is not None:
            # Use call_soon_threadsafe to safely schedule from any thread
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(queue_translation_result(result))
            )
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(queue_task_progress())
            )
    except Exception as e:
        logger.error(f"Error in stream_translation_callback: {e}")

# Store the main event loop reference when the module is loaded
def _store_main_loop():
    """Store reference to the main event loop for use in callbacks."""
    try:
        loop = asyncio.get_running_loop()
        stream_translation_callback._main_loop = loop
        logger.debug("Stored main event loop reference")
    except RuntimeError:
        logger.warning("No running event loop to store")

# Call this when starting async operations
async def _ensure_loop_reference():
    """Ensure we have a reference to the main event loop."""
    if not hasattr(stream_translation_callback, '_main_loop'):
        try:
            loop = asyncio.get_running_loop()
            stream_translation_callback._main_loop = loop
            logger.debug("Stored main event loop reference")
        except RuntimeError:
            logger.warning("No running event loop to store")

async def queue_translation_result(result: TranslationResult):
    """Queue a translation result for WebSocket broadcast."""
    global ws_message_queue
    if ws_message_queue is not None:
        try:
            await ws_message_queue.put(("translation_result", result))
        except Exception as e:
            logger.error(f"Error queueing translation result: {e}")

async def queue_task_progress():
    """Queue a task progress update for WebSocket broadcast."""
    global ws_message_queue
    if ws_message_queue is not None:
        try:
            await ws_message_queue.put(("task_progress", app_state["task_state"]))
        except Exception as e:
            logger.error(f"Error queueing task progress: {e}")

async def process_ws_messages():
    """Process WebSocket messages from the queue."""
    global ws_message_queue
    
    logger.info("Starting WebSocket message processor")
    
    try:
        while True:
            try:
                # Wait for a message with a reasonable timeout
                try:
                    message_type, data = await asyncio.wait_for(
                        ws_message_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # No message in queue, continue
                    continue
                
                # Process the message based on its type
                if message_type == "translation_result":
                    await broadcast_translation_result(data)
                elif message_type == "task_progress":
                    await broadcast_task_progress()
                elif message_type == "status":
                    await broadcast_status()
                
                # Mark the task as done
                ws_message_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                await asyncio.sleep(0.5)  # Sleep briefly before retrying
                
    except asyncio.CancelledError:
        logger.info("WebSocket message processor cancelled")
        raise
    except Exception as e:
        logger.error(f"WebSocket message processor error: {e}")
    finally:
        logger.info("WebSocket message processor stopped")

async def broadcast_translation_result(result: TranslationResult):
    """Broadcast a translation result."""
    try:
        # Check if we have active connections
        if not manager.active_connections:
            logger.debug("No active WebSocket connections for translation result")
            return
            
        message = TranslationResultMessage(data=result)
        await manager.broadcast(message.model_dump(mode="json"))
        logger.debug(f"Broadcasted translation result to {len(manager.active_connections)} connections")
    except Exception as e:
        logger.error(f"Error broadcasting translation result: {e}")

async def broadcast_status():
    """Broadcast the current application status."""
    try:
        # Check if we have active connections
        if not manager.active_connections:
            logger.debug("No active WebSocket connections for status")
            return
            
        status = await get_status_for_broadcast()
        message = StatusUpdateMessage(data=status)
        await manager.broadcast(message.model_dump(mode="json"))
        logger.debug(f"Broadcasted status to {len(manager.active_connections)} connections")
    except Exception as e:
        logger.error(f"Error broadcasting status: {e}")

async def get_status_for_broadcast():
    """Get the current status for broadcasting."""
    from app.routers.endpoints.status import get_status
    return await get_status()

async def broadcast_task_progress():
    """Broadcast the current task progress."""
    try:
        # Check if we have active connections
        if not manager.active_connections:
            logger.debug("No active WebSocket connections for task progress")
            return
            
        message = TaskProgressMessage(data=app_state["task_state"])
        await manager.broadcast(message.model_dump(mode="json"))
        logger.debug(f"Broadcasted task progress to {len(manager.active_connections)} connections")
    except Exception as e:
        logger.error(f"Error broadcasting task progress: {e}")

async def update_task_timer():
    """Periodically update the task timer and broadcast progress."""
    global ws_message_queue
    
    try:
        while app_state["task_state"].is_running:
            # Update elapsed time if task is running
            if app_state["task_state"].start_time:
                elapsed = (datetime.now() - app_state["task_state"].start_time).total_seconds()
                app_state["task_state"] = app_state["task_state"].copy(update={"elapsed_time": elapsed})
                
                # Queue task progress message
                if ws_message_queue is not None:
                    try:
                        await ws_message_queue.put(("task_progress", app_state["task_state"]))
                    except Exception as e:
                        logger.error(f"Error queueing timer update: {e}")
            
            # Update every 0.1 seconds for smooth timer display
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        # Task was cancelled, which is expected
        pass
    except Exception as e:
        logger.error(f"Error in update_task_timer: {e}")