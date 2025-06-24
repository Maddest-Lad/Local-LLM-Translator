import tkinter as tk
from tkinter import ttk, messagebox
import threading, time, os
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
import pygetwindow as gw
import win32gui
import translator

DEFAULT_CHECK_INTERVAL = 3
DEFAULT_SIMILARITY_THRESHOLD = 0.90
DEFAULT_TIMEOUT = 45

class TranslationTaskState:
    """Manages the running translation task."""
    def __init__(self):
        self.is_running = False
        self.future = None
        self.lock = threading.Lock()
        self.start_time = 0

    def start(self, future):
        with self.lock:
            if self.is_running: return False
            self.is_running = True
            self.start_time = time.time()
            self.future = future
            return True

    def stop(self):
        with self.lock:
            if self.future and not self.future.done():
                self.future.cancel()
            self.is_running = False
            self.future = None
            self.start_time = 0

    def finish(self):
        with self.lock:
            self.is_running = False
            self.future = None
            self.start_time = 0

    def get_elapsed(self):
        return time.time() - self.start_time if self.is_running else 0

class TranslationResultBox(ttk.Frame):
    def __init__(self, parent, translation, timestamp, on_delete=None):
        super().__init__(parent, style="Card.TFrame", padding=5)
        self.on_delete = on_delete

        # Top bar (timestamp + delete)
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text=time.strftime("%H:%M:%S", time.localtime(timestamp)), font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Button(top, text="🗑️", width=3, command=self._delete).pack(side="right")

        # Label and copy
        label_row = ttk.Frame(self)
        label_row.pack(fill="x")
        ttk.Label(label_row, text="Translation:", font=("Segoe UI", 13, "bold")).pack(side="left", padx=(0,8))
        ttk.Button(label_row, text="📋", width=3, command=lambda: self._copy(translation)).pack(side="right")

        # Translation text
        self.trans_text_widget = tk.Text(
            self, height=1, wrap=tk.WORD, font=("Segoe UI", 16, "bold"),
            bg="#2d2d2d", fg="white", bd=0, highlightthickness=0, relief="flat"
        )
        self.trans_text_widget.insert("1.0", translation)
        self.trans_text_widget.config(state="disabled")
        self.trans_text_widget.pack(fill="x", expand=True, padx=5, pady=(2,8))
        self._autoresize()

        # Make sure the translation box itself fills the width
        self.pack(fill="x", expand=True, padx=5, pady=4)

    def _autoresize(self):
        self.trans_text_widget.update_idletasks()
        lines = int(self.trans_text_widget.index('end-1c').split('.')[0])
        self.trans_text_widget.config(height=min(16, lines + 1))

    def _copy(self, text):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception as e:
            print(f"Copy failed: {e}")

    def _delete(self):
        if self.on_delete:
            self.on_delete(self)
        self.destroy()

class ScreenTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Screen Translator")
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.task_state = TranslationTaskState()
        self.result_queue = Queue()
        self.error_queue = Queue()
        self.selected_hwnd = None
        self.last_image = None
        self.last_hwnd = None
        self.translation_boxes = []
        self.pipeline_running = False
        self.stop_event = threading.Event()
        self.monitoring_paused = True

        # Settings
        self.check_interval = DEFAULT_CHECK_INTERVAL
        self.similarity_threshold = DEFAULT_SIMILARITY_THRESHOLD
        self.timeout = DEFAULT_TIMEOUT

        self.is_dark_theme = True
        self._setup_theme()
        self._build_ui()
        self._ui_loop()

    def _setup_theme(self):
        try:
            cur = self.root.tk.call("ttk::style", "theme", "names")
            if "azure-dark" not in cur:
                tcl_path = os.path.join("Azure-ttk-theme", "azure.tcl")
                if os.path.exists(tcl_path):
                    self.root.tk.call("source", tcl_path)
            self.root.tk.call("set_theme", "dark")
        except Exception:
            pass

    def _build_ui(self):
        wrapper = ttk.Frame(self.root, padding=5)
        wrapper.pack(fill="both", expand=True)

        header = ttk.Frame(wrapper, style="Card.TFrame", padding=8)
        header.pack(fill="x")
        self.header_label = ttk.Label(header, text="Screen Translator", font=("Segoe UI", 14, "bold"))
        self.header_label.pack(side="left")
        ttk.Button(header, text="Settings", style="Accent.TButton", command=self._open_settings).pack(side="left", padx=6)
        ttk.Button(header, text="Select Program", command=self._program_menu).pack(side="left")
        ttk.Button(header, text="Reset Cache", command=self._reset_cache).pack(side="left", padx=(4, 0))
        ttk.Button(header, text="Clear Results", command=self._clear_results).pack(side="left", padx=(4, 0))
        ttk.Button(header, text="🌙", width=3, command=self._toggle_theme).pack(side="right", padx=(4, 0))

        # Results area
        main = ttk.Frame(wrapper, style="Card.TFrame", padding=8)
        main.pack(fill="both", expand=True, pady=5)

        ttk.Label(main, text="Results", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        rf = ttk.Frame(main)
        rf.pack(fill="both", expand=True, pady=(4, 8))

        self.canvas = tk.Canvas(rf, borderwidth=0)
        scrollbar = ttk.Scrollbar(rf, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.result_frame = ttk.Frame(self.canvas)
        self.result_frame_window = self.canvas.create_window(
            (0, 0), window=self.result_frame, anchor="nw"
        )

        def _on_canvas_resize(event):
            self.canvas.itemconfig(self.result_frame_window, width=event.width)
        self.canvas.bind("<Configure>", _on_canvas_resize)

        def _on_frame_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.result_frame.bind("<Configure>", _on_frame_configure)
        
        # Controls
        controls = ttk.Frame(main)
        controls.pack(fill="x", pady=(8, 0))
        self.status_label = ttk.Label(controls, text="Idle", font=("Segoe UI", 10))
        self.status_label.pack(side="left", padx=4)
        self.toggle_button = ttk.Button(controls, text="▶ Start", style="Accent.TButton", command=self._toggle_monitor)
        self.toggle_button.pack(side="left")
        ttk.Button(controls, text="Force Run", command=self._process_now).pack(side="left", padx=(4, 0))
        ttk.Button(controls, text="Force Stop", command=self._stop_task).pack(side="left", padx=(4, 0))

    # Program selection
    def _program_menu(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Full Screen", command=self._select_full_screen)
        menu.add_separator()
        for w in gw.getAllWindows():
            if w.title.strip():
                menu.add_command(label=w.title, command=lambda h=w._hWnd: self._select_hwnd(h))
        menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def _select_hwnd(self, hwnd):
        self.selected_hwnd = hwnd
        if self.last_hwnd != hwnd:
            self.last_image = None
            self.last_hwnd = hwnd
        title = next((w.title.strip() for w in gw.getAllWindows() if w._hWnd == hwnd), None)
        self.header_label.config(text=f"{title}" if title else "Screen Translator")

    def _select_full_screen(self):
        hwnd = win32gui.GetDesktopWindow()
        self.selected_hwnd = hwnd
        self.last_image = None
        self.last_hwnd = hwnd
        self.header_label.config(text="Monitoring: Full Screen")

    def _toggle_monitor(self):
        if self.monitoring_paused:
            # Start monitoring
            if not self.selected_hwnd:
                messagebox.showwarning("No Program Selected", "Select a program to monitor.")
                return
            self.monitoring_paused = False
            self.pipeline_running = True
            self.stop_event.clear()
            threading.Thread(target=self._monitor_loop, daemon=True).start()
            self.status_label.config(text="Monitoring...")
            self.toggle_button.config(text="⏸ Pause")
        else:
            # Pause monitoring
            self.monitoring_paused = True
            self.pipeline_running = False
            self.stop_event.set()
            self.status_label.config(text="Paused")
            self.toggle_button.config(text="▶ Start")

    def _monitor_loop(self):
        while self.pipeline_running and not self.stop_event.is_set():
            if not self.selected_hwnd or not translator.is_window_visible(self.selected_hwnd):
                time.sleep(self.check_interval)
                continue
            screenshot = translator.screenshot_window(self.selected_hwnd)
            if self.last_image is not None and self.last_hwnd == self.selected_hwnd:
                if translator.images_are_similar(screenshot, self.last_image, self.similarity_threshold):
                    time.sleep(self.check_interval)
                    continue
            self.last_image = screenshot
            self.last_hwnd = self.selected_hwnd
            if not self.task_state.is_running:
                self._start_translation_task(screenshot)
            time.sleep(self.check_interval)

    def _start_translation_task(self, screenshot):
        def task():
            img_b64 = translator.encode_image(screenshot)
            return translator.translate_screen(img_b64, timeout=self.timeout)
        future = self.executor.submit(task)
        if self.task_state.start(future):
            future.add_done_callback(self._on_task_done)

    def _on_task_done(self, future):
        try:
            if future.cancelled():
                self.task_state.finish()
                return
            translation = future.result()
            ts = time.time()
            self.task_state.finish()
            if translation:
                translator.log_translation("", translation)
                self.result_queue.put((translation, ts))
        except Exception as e:
            self.task_state.finish()
            self.error_queue.put(str(e))

    def _process_now(self):
        if not self.selected_hwnd:
            messagebox.showwarning("No Program Selected", "Select a program first.")
            return
        screenshot = translator.screenshot_window(self.selected_hwnd)
        self.last_image = screenshot
        self.last_hwnd = self.selected_hwnd
        if self.task_state.is_running:
            self._stop_task()
            time.sleep(0.1)
        self._start_translation_task(screenshot)

    def _stop_task(self):
        self.task_state.stop()

    def _reset_cache(self):
        self.last_image = None
        self.last_hwnd = None

    def _clear_results(self):
        for box in self.translation_boxes:
            box.destroy()
        self.translation_boxes.clear()

    def _open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.geometry("340x240")
        win.transient(self.root)
        frame = ttk.Frame(win, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Check Interval (sec):").pack(anchor="w")
        interval = tk.IntVar(value=self.check_interval)
        ttk.Scale(frame, from_=1, to=10, orient=tk.HORIZONTAL, variable=interval).pack(fill="x")
        ttk.Label(frame, textvariable=interval).pack(anchor="w")

        ttk.Label(frame, text="Similarity Threshold:").pack(anchor="w", pady=(10, 0))
        thresh = tk.DoubleVar(value=self.similarity_threshold)
        ttk.Scale(frame, from_=0.5, to=1.0, orient=tk.HORIZONTAL, variable=thresh).pack(fill="x")
        ttk.Label(frame, textvariable=thresh).pack(anchor="w")

        ttk.Label(frame, text="Processing Timeout (sec):").pack(anchor="w", pady=(10, 0))
        tout = tk.IntVar(value=self.timeout)
        ttk.Scale(frame, from_=10, to=120, orient=tk.HORIZONTAL, variable=tout).pack(fill="x")
        ttk.Label(frame, textvariable=tout).pack(anchor="w")

        def save():
            self.check_interval = interval.get()
            self.similarity_threshold = thresh.get()
            self.timeout = tout.get()
            win.destroy()
        ttk.Button(frame, text="Save", style="Accent.TButton", command=save).pack(side="right", pady=(16, 0))

    def _toggle_theme(self):
        try:
            cur = self.root.tk.call("ttk::style", "theme", "use")
            if cur == "azure-dark":
                self.root.tk.call("set_theme", "light")
                self.is_dark_theme = False
            else:
                self.root.tk.call("set_theme", "dark")
                self.is_dark_theme = True
        except Exception:
            pass

    def _ui_loop(self):
        try:
            while True:
                translation, ts = self.result_queue.get_nowait()
                self._add_result_box(translation, ts)
        except Empty:
            pass
        try:
            while True:
                print("Error:", self.error_queue.get_nowait())
        except Empty:
            pass
        self._update_status()
        self.root.after(200, self._ui_loop)

    def _add_result_box(self, translation, ts):
        box = TranslationResultBox(self.result_frame, translation, ts, on_delete=self._remove_result_box)
        self.translation_boxes.append(box)
        # Schedule scroll after Tkinter redraw
        self.root.after(50, lambda: self.canvas.yview_moveto(1.0))

    def _remove_result_box(self, box):
        if box in self.translation_boxes:
            self.translation_boxes.remove(box)

    def _update_status(self):
        if self.task_state.is_running:
            self.status_label.config(text=f"Processing... {self.task_state.get_elapsed():.1f}s")
        else:
            self.status_label.config(text="Idle")

    def cleanup(self):
        self.pipeline_running = False
        self.stop_event.set()
        self._stop_task()
        self.executor.shutdown(wait=False)
