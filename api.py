from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import threading
import time
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
import pygetwindow as gw
import win32gui

from models import *
import translator

class TranslationService:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.task_state = TaskState(is_running=False)
        self.selected_hwnd: Optional[int] = None
        self.last_image = None
        self.last_hwnd = None
        self.translation_results: Dict[str, TranslationResult] = {}
        self.monitoring_paused = True
        self.pipeline_running = False
        self.stop_event = threading.Event()
        self.current_future = None
        
        # Settings
        self.settings = AppSettings()
        
        # WebSocket connections
        self.connections: List[WebSocket] = []
        
        # Background monitoring task
        self.monitor_task = None

    async def add_connection(self, websocket: WebSocket):
        self.connections.append(websocket)
        # Send current status to new connection
        await self.broadcast_status()

    async def remove_connection(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast_message(self, message: WSMessage):
        if not self.connections:
            return
        
        disconnected = []
        for connection in self.connections:
            try:
                await connection.send_text(message.json())
            except:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            await self.remove_connection(conn)

    async def broadcast_status(self):
        status = self.get_status()
        message = StatusUpdateMessage(data=status)
        await self.broadcast_message(message)

    async def broadcast_translation(self, result: TranslationResult):
        message = TranslationResultMessage(data=result)
        await self.broadcast_message(message)

    async def broadcast_error(self, error: str, detail: Optional[str] = None):
        error_response = ErrorResponse(error=error, detail=detail)
        message = ErrorMessage(data=error_response)
        await self.broadcast_message(message)

    def get_windows(self) -> List[WindowInfo]:
        windows = []
        try:
            for window in gw.getAllWindows():
                if window.title.strip():
                    windows.append(WindowInfo(
                        hwnd=window._hWnd,
                        title=window.title.strip(),
                        is_visible=translator.is_window_visible(window._hWnd)
                    ))
        except Exception as e:
            print(f"Error getting windows: {e}")
        return windows

    def select_window(self, hwnd: Optional[int], title: Optional[str] = None):
        if hwnd is None:
            # Full screen
            self.selected_hwnd = win32gui.GetDesktopWindow()
        else:
            self.selected_hwnd = hwnd
            
        # Reset cache when window changes
        if self.last_hwnd != self.selected_hwnd:
            self.last_image = None
            self.last_hwnd = self.selected_hwnd

    def get_selected_window_info(self) -> Optional[WindowInfo]:
        if not self.selected_hwnd:
            return None
            
        if self.selected_hwnd == win32gui.GetDesktopWindow():
            return WindowInfo(hwnd=self.selected_hwnd, title="Full Screen", is_visible=True)
        
        try:
            for window in gw.getAllWindows():
                if window._hWnd == self.selected_hwnd:
                    return WindowInfo(
                        hwnd=window._hWnd,
                        title=window.title.strip(),
                        is_visible=translator.is_window_visible(window._hWnd)
                    )
        except:
            pass
        return None

    def update_settings(self, updates: SettingsUpdateRequest):
        if updates.check_interval is not None:
            self.settings.check_interval = updates.check_interval
        if updates.similarity_threshold is not None:
            self.settings.similarity_threshold = updates.similarity_threshold
        if updates.timeout is not None:
            self.settings.timeout = updates.timeout

    def get_status(self) -> AppStatus:
        return AppStatus(
            status=TaskStatus.RUNNING if self.task_state.is_running else 
                   (TaskStatus.PAUSED if self.monitoring_paused else TaskStatus.IDLE),
            monitoring_paused=self.monitoring_paused,
            selected_window=self.get_selected_window_info(),
            task_state=self.task_state,
            settings=self.settings,
            translation_count=len(self.translation_results)
        )

    async def start_monitoring(self):
        if not self.selected_hwnd:
            raise HTTPException(status_code=400, detail="No window selected")
        
        self.monitoring_paused = False
        self.pipeline_running = True
        self.stop_event.clear()
        
        # Start monitoring loop in background
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        await self.broadcast_status()

    async def pause_monitoring(self):
        self.monitoring_paused = True
        self.pipeline_running = False
        self.stop_event.set()
        if self.monitor_task:
            self.monitor_task.cancel()
        await self.broadcast_status()

    async def stop_monitoring(self):
        await self.pause_monitoring()
        await self.stop_current_task()

    async def _monitor_loop(self):
        try:
            while self.pipeline_running and not self.stop_event.is_set():
                if not self.selected_hwnd or not translator.is_window_visible(self.selected_hwnd):
                    await asyncio.sleep(self.settings.check_interval)
                    continue
                
                # Run screenshot in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                screenshot = await loop.run_in_executor(
                    None, translator.screenshot_window, self.selected_hwnd
                )
                
                # Check similarity
                if (self.last_image is not None and 
                    self.last_hwnd == self.selected_hwnd):
                    is_similar = await loop.run_in_executor(
                        None, translator.images_are_similar, 
                        screenshot, self.last_image, self.settings.similarity_threshold
                    )
                    if is_similar:
                        await asyncio.sleep(self.settings.check_interval)
                        continue
                
                self.last_image = screenshot
                self.last_hwnd = self.selected_hwnd
                
                # Start translation if not already running
                if not self.task_state.is_running:
                    await self._start_translation_task(screenshot)
                
                await asyncio.sleep(self.settings.check_interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self.broadcast_error("Monitor loop error", str(e))

    async def _start_translation_task(self, screenshot):
        self.task_state = TaskState(
            is_running=True,
            start_time=datetime.now(),
            elapsed_time=0
        )
        
        try:
            loop = asyncio.get_event_loop()
            
            # Encode image
            img_b64 = await loop.run_in_executor(
                None, translator.encode_image, screenshot
            )
            
            start_time = time.time()
            
            # Translate
            translation = await loop.run_in_executor(
                None, translator.translate_screen, img_b64, self.settings.timeout
            )
            
            processing_time = time.time() - start_time
            
            if translation:
                result = TranslationResult(
                    id=str(uuid.uuid4()),
                    translation=translation,
                    timestamp=datetime.now(),
                    processing_time=processing_time
                )
                
                self.translation_results[result.id] = result
                await self.broadcast_translation(result)
                
                # Log translation
                await loop.run_in_executor(
                    None, translator.log_translation, "", translation
                )
            
        except Exception as e:
            await self.broadcast_error("Translation error", str(e))
        finally:
            self.task_state = TaskState(is_running=False)
            await self.broadcast_status()

    async def force_translation(self):
        if not self.selected_hwnd:
            raise HTTPException(status_code=400, detail="No window selected")
        
        # Stop current task if running
        if self.task_state.is_running:
            await self.stop_current_task()
            await asyncio.sleep(0.1)
        
        # Take screenshot and translate
        loop = asyncio.get_event_loop()
        screenshot = await loop.run_in_executor(
            None, translator.screenshot_window, self.selected_hwnd
        )
        
        self.last_image = screenshot
        self.last_hwnd = self.selected_hwnd
        
        await self._start_translation_task(screenshot)

    async def stop_current_task(self):
        if self.current_future and not self.current_future.done():
            self.current_future.cancel()
        self.task_state = TaskState(is_running=False)
        await self.broadcast_status()

    def clear_results(self):
        self.translation_results.clear()

    def delete_result(self, result_id: str):
        if result_id in self.translation_results:
            del self.translation_results[result_id]

    def reset_cache(self):
        self.last_image = None
        self.last_hwnd = None

# Initialize service
service = TranslationService()

# Create FastAPI app
app = FastAPI(title="Screen Translator API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (for the web UI)
app.mount("/static", StaticFiles(directory="static"), name="static")

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await service.add_connection(websocket)
    try:
        while True:
            # Keep connection alive and handle any incoming messages if needed
            await websocket.receive_text()
    except WebSocketDisconnect:
        await service.remove_connection(websocket)

# API Routes
@app.get("/", response_class=HTMLResponse)
async def get_homepage():
    """Serve the main web UI"""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Web UI not found. Please create static/index.html</h1>")
    except UnicodeDecodeError:
        return HTMLResponse(content="<h1>Error: Invalid encoding in index.html. Please ensure it's saved as UTF-8</h1>")

@app.get("/api/status", response_model=AppStatus)
async def get_status():
    """Get current application status"""
    return service.get_status()

@app.get("/api/windows", response_model=WindowListResponse)
async def get_windows():
    """Get list of available windows"""
    windows = service.get_windows()
    return WindowListResponse(windows=windows)

@app.post("/api/window/select")
async def select_window(request: WindowSelectionRequest):
    """Select a window to monitor"""
    service.select_window(request.hwnd, request.title)
    await service.broadcast_status()
    return {"success": True}

@app.get("/api/settings", response_model=AppSettings)
async def get_settings():
    """Get current settings"""
    return service.settings

@app.patch("/api/settings")
async def update_settings(updates: SettingsUpdateRequest):
    """Update application settings"""
    service.update_settings(updates)
    await service.broadcast_status()
    return {"success": True}

@app.post("/api/monitor/control")
async def control_monitoring(request: MonitorControlRequest):
    """Start, pause, or stop monitoring"""
    if request.action == "start":
        await service.start_monitoring()
    elif request.action == "pause":
        await service.pause_monitoring()
    elif request.action == "stop":
        await service.stop_monitoring()
    
    return {"success": True}

@app.post("/api/translate/force")
async def force_translation():
    """Force a translation of the current window"""
    await service.force_translation()
    return {"success": True}

@app.post("/api/task/stop")
async def stop_task():
    """Stop the current translation task"""
    await service.stop_current_task()
    return {"success": True}

@app.get("/api/results", response_model=List[TranslationResult])
async def get_results():
    """Get all translation results"""
    return list(service.translation_results.values())

@app.delete("/api/results")
async def clear_results():
    """Clear all translation results"""
    service.clear_results()
    await service.broadcast_status()
    return {"success": True}

@app.delete("/api/results/{result_id}")
async def delete_result(result_id: str):
    """Delete a specific translation result"""
    service.delete_result(result_id)
    await service.broadcast_status()
    return {"success": True}

@app.post("/api/cache/reset")
async def reset_cache():
    """Reset the image comparison cache"""
    service.reset_cache()
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)