import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from queue import Queue, Empty
import pygetwindow as gw
import win32gui

# Import your existing modules
import ocr
import translation

CHECK_INTERVAL = 3
SIMILARITY_THRESHOLD = 0.90
OCR_TIMEOUT = 30
TRANSLATION_TIMEOUT = 15

class TranslationBox(tk.Frame):
    def __init__(self, parent, ocr_text, translation_text, created_time, on_delete=None):
        super().__init__(parent, bg="#282d31", bd=1, relief="solid")
        self.on_delete = on_delete
        self.pack(fill="x", padx=5, pady=2)

        # Delete button
        del_btn = tk.Button(self, text="🗑️", font=("Segoe UI", 8), bg="#8B4513", fg="white",
                           bd=0, padx=5, pady=2, command=self.delete_box)
        del_btn.pack(anchor="ne", padx=5, pady=2)

        # OCR text
        ocr_label = tk.Label(self, text="OCR:", font=("Segoe UI", 9, "bold"), 
                            fg="#6cf", bg="#282d31", anchor="w")
        ocr_label.pack(fill="x", padx=5, pady=(0, 2))
        
        ocr_text_label = tk.Label(self, text=ocr_text, fg="#bdf", bg="#282d31", 
                                 anchor="w", wraplength=400, justify="left")
        ocr_text_label.pack(fill="x", padx=5, pady=(0, 5))

        # Translation text
        trans_label = tk.Label(self, text="Translation:", font=("Segoe UI", 9, "bold"), 
                              fg="#6f6", bg="#282d31", anchor="w")
        trans_label.pack(fill="x", padx=5, pady=(0, 2))
        
        trans_text_label = tk.Label(self, text=translation_text, fg="#fff", bg="#282d31", 
                                   anchor="w", wraplength=400, justify="left", 
                                   font=("Consolas", 11, "bold"))
        trans_text_label.pack(fill="x", padx=5, pady=(0, 5))

        # Timestamp
        time_str = time.strftime("%H:%M:%S", time.localtime(created_time))
        time_label = tk.Label(self, text=f"🕒 {time_str}", fg="#aaa", bg="#282d31", 
                             font=("Segoe UI", 8))
        time_label.pack(anchor="se", padx=5, pady=2)

    def delete_box(self):
        if self.on_delete:
            self.on_delete(self)
        self.destroy()


class OCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OCR + Translation UI")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        self.root.configure(bg="#202124")

        # State variables
        self.selected_hwnd = None
        self.last_image = None
        self.running = False
        self.ocr_visible = True
        self.translation_visible = True

        # Threading
        self.ocr_thread = None
        self.translation_thread = None
        self.stop_ocr_event = threading.Event()
        self.stop_translation_event = threading.Event()
        self.ocr_queue = Queue()
        self.translation_queue = Queue()
        
        # Timers
        self.ocr_time = 0
        self.translation_time = 0
        self.ocr_timer_active = False
        self.translation_timer_active = False

        # Settings
        self.check_interval = CHECK_INTERVAL
        self.similarity_threshold = SIMILARITY_THRESHOLD
        self.ocr_timeout = OCR_TIMEOUT
        self.translation_timeout = TRANSLATION_TIMEOUT

        self.translation_boxes = []
        
        self.create_ui()
        self.poll_queues()
        self.update_timers()

    def create_ui(self):
        # Header
        self.create_header()
        
        # Main content area
        main_frame = tk.Frame(self.root, bg="#202124")
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create paned window
        self.paned_window = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL, 
                                          bg="#202124", sashwidth=5, sashrelief="raised")
        self.paned_window.pack(fill="both", expand=True)
        
        # Create panels
        self.create_ocr_panel()
        self.create_translation_panel()
        
        # Control buttons
        self.create_controls(main_frame)

    def create_header(self):
        header = tk.Frame(self.root, bg="#333333", height=50)
        header.pack(fill="x", padx=10, pady=5)
        header.pack_propagate(False)

        self.header_label = tk.Label(header, text="OCR + Translation UI", 
                                    font=("Segoe UI", 14, "bold"), fg="white", bg="#333333")
        self.header_label.pack(side="left", padx=10, pady=10)

        # Settings button
        settings_btn = tk.Button(header, text="Settings", bg="#5A8F7B", fg="white", 
                                bd=0, padx=10, pady=5, command=self.open_settings)
        settings_btn.pack(side="left", padx=5, pady=10)

        # Program selection
        program_btn = tk.Button(header, text="Select Program", bg="#6B8CAE", fg="white", 
                               bd=0, padx=10, pady=5, command=self.show_program_menu)
        program_btn.pack(side="left", padx=5, pady=10)

        # View toggles
        view_frame = tk.Frame(header, bg="#333333")
        view_frame.pack(side="left", padx=10, pady=10)
        
        tk.Button(view_frame, text="Toggle OCR", bg="#A67C5A", fg="white", bd=0, 
                 padx=8, pady=5, command=self.toggle_ocr).pack(side="left", padx=2)
        tk.Button(view_frame, text="Toggle Translation", bg="#A67C5A", fg="white", bd=0, 
                 padx=8, pady=5, command=self.toggle_translation).pack(side="left", padx=2)

        # Theme toggle
        self.theme_btn = tk.Button(header, text="🌙", bg="#7B68A8", fg="white", 
                                  bd=0, padx=10, pady=5, command=self.toggle_theme)
        self.theme_btn.pack(side="right", padx=10, pady=10)

    def create_ocr_panel(self):
        self.ocr_frame = tk.Frame(self.paned_window, bg="#2d2d2d", width=400)
        
        # OCR text area
        text_frame = tk.Frame(self.ocr_frame, bg="#2d2d2d")
        text_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.ocr_text = tk.Text(text_frame, bg="#1e1e1e", fg="#ffffff", 
                               font=("Consolas", 11), wrap=tk.WORD, bd=1, relief="solid")
        ocr_scrollbar = tk.Scrollbar(text_frame, orient="vertical", command=self.ocr_text.yview)
        self.ocr_text.configure(yscrollcommand=ocr_scrollbar.set)
        
        self.ocr_text.pack(side="left", fill="both", expand=True)
        ocr_scrollbar.pack(side="right", fill="y")

        # OCR controls
        ocr_controls = tk.Frame(self.ocr_frame, bg="#2d2d2d")
        ocr_controls.pack(fill="x", padx=5, pady=5)

        self.ocr_timer_label = tk.Label(ocr_controls, text="Idle", fg="white", bg="#2d2d2d")
        self.ocr_timer_label.pack(side="left", padx=5)

        tk.Button(ocr_controls, text="Stop OCR", bg="#B85450", fg="white", bd=0, 
                 padx=10, pady=5, command=self.stop_ocr).pack(side="left", padx=5)
        
        tk.Button(ocr_controls, text="Clear", bg="#607D8B", fg="white", bd=0, 
                 padx=10, pady=5, command=self.clear_ocr).pack(side="right", padx=5)

        self.paned_window.add(self.ocr_frame)

    def create_translation_panel(self):
        self.translation_frame = tk.Frame(self.paned_window, bg="#2d2d2d", width=500)
        
        # Translation log area with scrollbar
        log_frame = tk.Frame(self.translation_frame, bg="#2d2d2d")
        log_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Canvas for scrollable content
        self.trans_canvas = tk.Canvas(log_frame, bg="#1e1e1e", bd=1, relief="solid")
        trans_scrollbar = tk.Scrollbar(log_frame, orient="vertical", command=self.trans_canvas.yview)
        self.trans_canvas.configure(yscrollcommand=trans_scrollbar.set)
        
        # Scrollable frame
        self.trans_scrollable_frame = tk.Frame(self.trans_canvas, bg="#1e1e1e")
        self.trans_canvas.create_window((0, 0), window=self.trans_scrollable_frame, anchor="nw")
        
        self.trans_canvas.pack(side="left", fill="both", expand=True)
        trans_scrollbar.pack(side="right", fill="y")
        
        # Update scroll region when frame changes
        self.trans_scrollable_frame.bind("<Configure>", self.on_trans_frame_configure)
        self.trans_canvas.bind("<Configure>", self.on_trans_canvas_configure)

        # Translation controls
        trans_controls = tk.Frame(self.translation_frame, bg="#2d2d2d")
        trans_controls.pack(fill="x", padx=5, pady=5)

        self.translation_timer_label = tk.Label(trans_controls, text="Idle", fg="white", bg="#2d2d2d")
        self.translation_timer_label.pack(side="left", padx=5)

        tk.Button(trans_controls, text="Stop Translation", bg="#B85450", fg="white", bd=0, 
                 padx=10, pady=5, command=self.stop_translation).pack(side="left", padx=5)
        
        tk.Button(trans_controls, text="Clear", bg="#607D8B", fg="white", bd=0, 
                 padx=10, pady=5, command=self.clear_translation_log).pack(side="right", padx=5)

        self.paned_window.add(self.translation_frame)

    def create_controls(self, parent):
        controls = tk.Frame(parent, bg="#202124")
        controls.pack(fill="x", pady=5)

        self.toggle_button = tk.Button(controls, text="▶ Start", bg="#5A8F7B", fg="white", 
                                      font=("Segoe UI", 12, "bold"), bd=0, padx=20, pady=10, 
                                      command=self.toggle_pipeline)
        self.toggle_button.pack(side="right", padx=10, pady=10)

    def on_trans_frame_configure(self, event):
        self.trans_canvas.configure(scrollregion=self.trans_canvas.bbox("all"))

    def on_trans_canvas_configure(self, event):
        canvas_width = event.width
        self.trans_canvas.itemconfig(self.trans_canvas.find_all()[0], width=canvas_width)

    # UI Event Handlers
    def clear_ocr(self):
        self.ocr_text.delete("1.0", tk.END)

    def toggle_ocr(self):
        if self.ocr_visible:
            self.paned_window.forget(self.ocr_frame)
            self.ocr_visible = False
        else:
            if self.translation_visible:
                self.paned_window.add(self.ocr_frame, before=self.translation_frame)
            else:
                self.paned_window.add(self.ocr_frame)
            self.ocr_visible = True

    def toggle_translation(self):
        if self.translation_visible:
            self.paned_window.forget(self.translation_frame)
            self.translation_visible = False
        else:
            self.paned_window.add(self.translation_frame)
            self.translation_visible = True

    def show_program_menu(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Full Screen", command=self.select_full_screen)
        menu.add_separator()
        
        for w in gw.getAllWindows():
            if w.title.strip():
                menu.add_command(label=w.title, command=lambda h=w._hWnd: self.select_hwnd(h))
        
        # Show menu at cursor
        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()

    def select_hwnd(self, hwnd):
        self.selected_hwnd = hwnd
        title = None
        for w in gw.getAllWindows():
            if w._hWnd == hwnd:
                title = w.title.strip()
                break
        if title:
            self.header_label.config(text=f"OCR: {title}")
        else:
            self.header_label.config(text="OCR + Translation UI")

    def select_full_screen(self):
        self.selected_hwnd = win32gui.GetDesktopWindow()
        self.header_label.config(text="OCR: Full Screen")

    def open_settings(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Settings")
        settings_win.geometry("400x300")
        settings_win.configure(bg="#2d2d2d")
        settings_win.transient(self.root)

        # Settings form
        form_frame = tk.Frame(settings_win, bg="#2d2d2d")
        form_frame.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(form_frame, text="Check Interval (sec):", fg="white", bg="#2d2d2d").pack(anchor="w", pady=5)
        interval_var = tk.IntVar(value=self.check_interval)
        tk.Scale(form_frame, from_=1, to=10, orient=tk.HORIZONTAL, variable=interval_var,
                bg="#2d2d2d", fg="white", highlightthickness=0).pack(fill="x", pady=5)

        tk.Label(form_frame, text="Similarity Threshold:", fg="white", bg="#2d2d2d").pack(anchor="w", pady=5)
        threshold_var = tk.DoubleVar(value=self.similarity_threshold)
        tk.Scale(form_frame, from_=0.5, to=1.0, resolution=0.01, orient=tk.HORIZONTAL, 
                variable=threshold_var, bg="#2d2d2d", fg="white", highlightthickness=0).pack(fill="x", pady=5)

        tk.Label(form_frame, text="OCR Timeout (sec):", fg="white", bg="#2d2d2d").pack(anchor="w", pady=5)
        ocr_timeout_var = tk.IntVar(value=self.ocr_timeout)
        tk.Scale(form_frame, from_=5, to=120, orient=tk.HORIZONTAL, variable=ocr_timeout_var,
                bg="#2d2d2d", fg="white", highlightthickness=0).pack(fill="x", pady=5)

        tk.Label(form_frame, text="Translation Timeout (sec):", fg="white", bg="#2d2d2d").pack(anchor="w", pady=5)
        translation_timeout_var = tk.IntVar(value=self.translation_timeout)
        tk.Scale(form_frame, from_=3, to=60, orient=tk.HORIZONTAL, variable=translation_timeout_var,
                bg="#2d2d2d", fg="white", highlightthickness=0).pack(fill="x", pady=5)

        def save_settings():
            self.check_interval = interval_var.get()
            self.similarity_threshold = threshold_var.get()
            self.ocr_timeout = ocr_timeout_var.get()
            self.translation_timeout = translation_timeout_var.get()
            settings_win.destroy()

        tk.Button(form_frame, text="Save Settings", bg="#5A8F7B", fg="white", bd=0, 
                 padx=20, pady=10, command=save_settings).pack(pady=20)

    def toggle_theme(self):
        # Simple theme toggle - you can expand this
        current_bg = self.root.cget("bg")
        if current_bg == "#202124":
            # Light theme
            self.root.configure(bg="#f0f0f0")
            self.theme_btn.config(text="🌞")
        else:
            # Dark theme
            self.root.configure(bg="#202124")
            self.theme_btn.config(text="🌙")

    def toggle_pipeline(self):
        if self.running:
            self.stop_ocr()
            self.stop_translation()
            self.toggle_button.config(text="▶ Start", bg="#5A8F7B")
            self.running = False
        else:
            if not self.selected_hwnd:
                messagebox.showwarning("No Program Selected", "Please select a program to monitor first.")
                return
            
            self.stop_ocr_event.clear()
            self.stop_translation_event.clear()
            self.ocr_thread = threading.Thread(target=self.ocr_loop, daemon=True)
            self.ocr_thread.start()
            self.toggle_button.config(text="⏸ Stop", bg="#B85450")
            self.running = True

    # Core OCR/Translation Logic (simplified from original)
    def ocr_loop(self):
        while not self.stop_ocr_event.is_set():
            if not self.selected_hwnd or not ocr.is_visible(self.selected_hwnd):
                time.sleep(self.check_interval)
                continue

            try:
                screenshot = ocr.screenshot_window(self.selected_hwnd)
                
                if self.last_image and ocr.images_are_similar(screenshot, self.last_image, self.similarity_threshold):
                    time.sleep(self.check_interval)
                    continue

                self.last_image = screenshot
                img_b64 = ocr.encode_image(screenshot)
                
                self.ocr_timer_active = True
                self.ocr_time = 0
                
                ocr_result = ocr.ocr_image_with_vllm(img_b64, timeout=self.ocr_timeout)
                self.ocr_timer_active = False
                
                if ocr_result:
                    self.ocr_queue.put(ocr_result)
                    # Start translation
                    self.translation_thread = threading.Thread(target=self.translate_text, args=(ocr_result,), daemon=True)
                    self.translation_thread.start()
                    
            except Exception as e:
                self.ocr_timer_active = False
                messagebox.showerror("OCR Error", str(e))
                
            time.sleep(self.check_interval)

    def translate_text(self, ocr_text):
        try:
            self.translation_timer_active = True
            self.translation_time = 0
            
            translation_result = translation.translate_text(ocr_text, timeout=self.translation_timeout)
            self.translation_timer_active = False
            
            if translation_result:
                translation.log_to_file(ocr_text, translation_result)
                self.translation_queue.put((ocr_text, translation_result, time.time()))
                
        except Exception as e:
            self.translation_timer_active = False
            messagebox.showerror("Translation Error", str(e))

    def stop_ocr(self):
        self.stop_ocr_event.set()
        self.ocr_timer_active = False

    def stop_translation(self):
        self.stop_translation_event.set()
        self.translation_timer_active = False

    def poll_queues(self):
        # Process OCR results
        try:
            while True:
                ocr_text = self.ocr_queue.get_nowait()
                self.ocr_text.delete("1.0", tk.END)
                self.ocr_text.insert(tk.END, ocr_text)
        except Empty:
            pass

        # Process translation results
        try:
            while True:
                ocr_text, translation_text, timestamp = self.translation_queue.get_nowait()
                self.add_translation_box(ocr_text, translation_text, timestamp)
        except Empty:
            pass

        self.root.after(200, self.poll_queues)

    def add_translation_box(self, ocr_text, translation_text, timestamp):
        box = TranslationBox(self.trans_scrollable_frame, ocr_text, translation_text, 
                           timestamp, on_delete=self.remove_translation_box)
        self.translation_boxes.append(box)
        
        # Auto-scroll to bottom
        self.root.after(10, lambda: self.trans_canvas.yview_moveto(1.0))

    def remove_translation_box(self, box):
        if box in self.translation_boxes:
            self.translation_boxes.remove(box)

    def clear_translation_log(self):
        for box in self.translation_boxes:
            box.destroy()
        self.translation_boxes.clear()

    def update_timers(self):
        if self.ocr_timer_active:
            self.ocr_time += 0.2
            self.ocr_timer_label.config(text=f"⏱️ {self.ocr_time:.1f}s")
        else:
            self.ocr_timer_label.config(text="Idle")

        if self.translation_timer_active:
            self.translation_time += 0.2
            self.translation_timer_label.config(text=f"⏱️ {self.translation_time:.1f}s")
        else:
            self.translation_timer_label.config(text="Idle")
            
        self.root.after(200, self.update_timers)