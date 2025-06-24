import tkinter as tk
from gui import ScreenTranslatorApp
import atexit

def cleanup_app():
    if hasattr(cleanup_app, "app_instance"):
        cleanup_app.app_instance.cleanup()

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenTranslatorApp(root)
    cleanup_app.app_instance = app
    atexit.register(cleanup_app)
    def on_close():
        app.cleanup()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.cleanup()
    finally:
        app.cleanup()
