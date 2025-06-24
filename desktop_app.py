import webview
import threading
import time
import sys
import os
import uvicorn
from api import app as fastapi_app

class DesktopApp:
    def __init__(self):
        self.server = None
        self.server_thread = None
        self.port = 8000
        
    def start_server(self):
        """Start the FastAPI server in a separate thread"""
        config = uvicorn.Config(
            fastapi_app, 
            host="127.0.0.1", 
            port=self.port,
            log_level="info"
        )
        self.server = uvicorn.Server(config)
        
        def run_server():
            try:
                self.server.run()
            except Exception as e:
                print(f"Server error: {e}")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Wait for server to start
        max_attempts = 30
        for i in range(max_attempts):
            try:
                import requests
                response = requests.get(f"http://127.0.0.1:{self.port}/api/status", timeout=1)
                if response.status_code == 200:
                    print("Server started successfully")
                    return True
            except:
                time.sleep(0.1)
        
        print("Failed to start server")
        return False
    
    def stop_server(self):
        """Stop the FastAPI server"""
        if self.server:
            self.server.should_exit = True
    
    def on_window_closed(self):
        """Called when the webview window is closed"""
        print("Window closed, shutting down server...")
        self.stop_server()
    
    def create_window(self):
        """Create and configure the webview window"""
        return webview.create_window(
            title="Screen Translator",
            url=f"http://127.0.0.1:{self.port}",
            width=1200,
            height=800,
            min_size=(800, 600),
            resizable=True,
            on_top=False,
            maximized=False,
            minimized=False,
            fullscreen=False
        )

def main():
    """Main entry point for the desktop application"""
    
    # Check if required directories exist
    static_dir = "static"
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
        print(f"Created {static_dir} directory")
    
    # Check if index.html exists
    index_path = os.path.join(static_dir, "index.html")
    if not os.path.exists(index_path):
        print(f"Warning: {index_path} not found!")
        print("Please make sure the web frontend files are in the static/ directory")
    
    # Create and start the desktop app
    desktop_app = DesktopApp()
    
    print("Starting FastAPI server...")
    if not desktop_app.start_server():
        print("Failed to start server. Exiting.")
        sys.exit(1)
    
    print("Creating webview window...")
    window = desktop_app.create_window()
    
    # Set up window event handlers
    def on_closed():
        desktop_app.on_window_closed()
    
    # Start the webview
    try:
        webview.start(
            debug=False,  # Set to True for development
            http_server=False,  # We're using our own server
            user_agent="Screen Translator Desktop App"
        )
    except KeyboardInterrupt:
        print("Application interrupted by user")
    except Exception as e:
        print(f"Application error: {e}")
    finally:
        desktop_app.stop_server()
        print("Application closed")

if __name__ == "__main__":
    main()