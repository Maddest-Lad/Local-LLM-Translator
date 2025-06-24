"""
Translation endpoints.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
import asyncio
import uuid
from datetime import datetime
import time
import queue
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

# Create a queue for WebSocket messages
ws_message_queue = queue.Queue()

# Flag to indicate if the message processor is running
message_processor_running = False

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
    
    if request.action == "start":
        app_state["monitoring_paused"] = False
        app_state["status"] = TaskStatus.RUNNING
        
        # Start the monitoring task if not already running
        global translation_task_running, translation_task_cancel, message_processor_running
        if not translation_task_running:
            translation_task_cancel = False
            background_tasks.add_task(monitoring_task)
        
        # Start the message processor task if not already running
        if not message_processor_running:
            message_processor_running = True
            background_tasks.add_task(process_ws_messages)
            
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
    
    # Start the message processor task if not already running
    global message_processor_running
    if not message_processor_running:
        message_processor_running = True
        background_tasks.add_task(process_ws_messages)
    
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
    
    # Update task state
    start_time = time.time()
    app_state["task_state"] = app_state["task_state"].copy(update={
        "is_running": True,
        "elapsed_time": 0,
        "start_time": datetime.now()
    })
    
    # Start the message processor task if not already running
    global message_processor_running
    if not message_processor_running:
        message_processor_running = True
        asyncio.create_task(process_ws_messages())
    
    # Start a timer task to update progress continuously
    timer_task = asyncio.create_task(update_task_timer())
    
    # Broadcast task progress
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
    
    # Instead of trying to run async functions directly, add messages to the queue
    # for processing by the message processor task
    try:
        # Add translation result message to queue
        ws_message_queue.put(("translation_result", result))
        
        # Add task progress message to queue
        ws_message_queue.put(("task_progress", app_state["task_state"]))
    except Exception as e:
        logger.error(f"Error in stream_translation_callback: {e}")

async def process_ws_messages():
    """Process WebSocket messages from the queue."""
    global message_processor_running
    try:
        logger.info("Starting WebSocket message processor")
        
        while True:
            try:
                # Try to get a message from the queue with a timeout
                try:
                    message_type, data = ws_message_queue.get(timeout=0.1)
                except queue.Empty:
                    # No message in queue, sleep briefly and continue
                    await asyncio.sleep(0.1)
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
    except Exception as e:
        logger.error(f"WebSocket message processor error: {e}")
    finally:
        message_processor_running = False
        logger.info("WebSocket message processor stopped")

async def broadcast_translation_result(result: TranslationResult):
    """Broadcast a translation result."""
    message = TranslationResultMessage(data=result)
    await manager.broadcast(message.model_dump(mode="json"))

async def broadcast_status():
    """Broadcast the current application status."""
    status = await get_status_for_broadcast()
    message = StatusUpdateMessage(data=status)
    await manager.broadcast(message.model_dump(mode="json"))

async def get_status_for_broadcast():
    """Get the current status for broadcasting."""
    from app.routers.endpoints.status import get_status
    return await get_status()

async def broadcast_task_progress():
    """Broadcast the current task progress."""
    message = TaskProgressMessage(data=app_state["task_state"])
    await manager.broadcast(message.model_dump(mode="json"))

async def update_task_timer():
    """Periodically update the task timer and broadcast progress."""
    try:
        while app_state["task_state"].is_running:
            # Update elapsed time if task is running
            if app_state["task_state"].start_time:
                elapsed = (datetime.now() - app_state["task_state"].start_time).total_seconds()
                app_state["task_state"] = app_state["task_state"].copy(update={"elapsed_time": elapsed})
                
                # Add task progress message to queue
                ws_message_queue.put(("task_progress", app_state["task_state"]))
            
            # Update every 0.2 seconds for smooth timer display
            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        # Task was cancelled, which is expected
        pass
    except Exception as e:
        logger.error(f"Error in update_task_timer: {e}")
