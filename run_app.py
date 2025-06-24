#!/usr/bin/env python3
"""
Screen Translator Application Launcher

This script provides multiple ways to run the application:
1. Desktop app with PyWebView (default)
2. Web server only (for development/browser access)
3. API server only (for external integrations)
"""

import argparse
import sys
import os

def run_desktop_app():
    """Run the desktop application with PyWebView"""
    try:
        from desktop_app import main
        main()
    except ImportError as e:
        print(f"Error importing desktop app: {e}")
        print("Make sure all dependencies are installed: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error running desktop app: {e}")
        sys.exit(1)

def run_web_server():
    """Run just the web server (accessible via browser)"""
    try:
        import uvicorn
        from api import app
        print("Starting web server...")
        print("Access the application at: http://127.0.0.1:8000")
        print("Press Ctrl+C to stop the server")
        uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
    except ImportError as e:
        print(f"Error importing web server: {e}")
        print("Make sure FastAPI and Uvicorn are installed: pip install fastapi uvicorn")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error running web server: {e}")
        sys.exit(1)

def run_api_only():
    """Run just the API server (no web UI)"""
    try:
        import uvicorn
        from api import app
        print("Starting API server...")
        print("API available at: http://127.0.0.1:8000/docs")
        print("Press Ctrl+C to stop the server")
        uvicorn.run(app, host="127.0.0.1", port=8000)
    except ImportError as e:
        print(f"Error importing API server: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAPI server stopped by user")
    except Exception as e:
        print(f"Error running API server: {e}")
        sys.exit(1)

def check_dependencies():
    """Check if required files and dependencies exist"""
    required_files = [
        "models.py",
        "api.py", 
        "translator.py",
        "static/index.html"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("Missing required files:")
        for file in missing_files:
            print(f"  - {file}")
        print("\nPlease ensure all files are in the correct location.")
        return False
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Screen Translator Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_app.py                 # Run desktop app (default)
  python run_app.py --mode web      # Run web server for browser access
  python run_app.py --mode api      # Run API server only
  python run_app.py --check         # Check dependencies and files
        """
    )
    
    parser.add_argument(
        "--mode", 
        choices=["desktop", "web", "api"],
        default="desktop",
        help="Application mode (default: desktop)"
    )
    
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check dependencies and required files"
    )
    
    args = parser.parse_args()
    
    if args.check:
        print("Checking dependencies and files...")
        if check_dependencies():
            print("✓ All required files found")
        else:
            sys.exit(1)
        
        # Try importing key dependencies
        try:
            import fastapi
            import uvicorn
            import pydantic
            print("✓ Core web dependencies available")
        except ImportError as e:
            print(f"✗ Missing web dependencies: {e}")
        
        try:
            import webview
            print("✓ PyWebView available for desktop mode")
        except ImportError:
            print("✗ PyWebView not available (desktop mode disabled)")
        
        try:
            import translator
            print("✓ Translation module available")
        except ImportError as e:
            print(f"✗ Translation module error: {e}")
        
        return
    
    # Check required files before starting
    if not check_dependencies():
        sys.exit(1)
    
    # Run the application based on mode
    if args.mode == "desktop":
        print("Starting Screen Translator Desktop App...")
        run_desktop_app()
    elif args.mode == "web":
        print("Starting Screen Translator Web Server...")
        run_web_server()
    elif args.mode == "api":
        print("Starting Screen Translator API Server...")
        run_api_only()

if __name__ == "__main__":
    main()