import tkinter as tk
from tkinter import ttk
import threading
import time
from queue import Queue
import pygetwindow as gw
import win32gui

import ocr
import translation

CHECK_INTERVAL = 3
SIMILARITY_THRESHOLD = 0.90

class OCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OCR + Translation UI")
        self.root.geometry("1100x760")
        self.root.minsize(900, 600)
        self.root.configure(bg="#202124")

        self.header = ttk.Frame(root, padding=(12, 8), style="Card.TFrame")
        self.header.pack(side="top", fill="x", padx=16, pady=(14, 6))
        self.setup_header()

        self.main_card = ttk.Frame(root, style="Card.TFrame", padding=18)
        self.main_card.pack(fill="both", expand=True, padx=22, pady=(0, 14))

        self.create_main_pane()
        self.create_controls()

        self.selected_hwnd = None
        self.last_image = None
        self.running = False
        self.ocr_queue = Queue()
        self.stop_thread = False
        self.llm_request_in_progress = False

        self.poll_queue()

    def setup_header(self):
        self.header_label = ttk.Label(self.header, text="OCR + Translation UI", font=("Segoe UI", 16, "bold"))
        self.header_label.pack(side="left", padx=(0, 20))
        self.settings_btn = ttk.Button(self.header, text="Settings", style="Accent.TButton", command=self.open_settings)
        self.settings_btn.pack(side="left", padx=6)
        self.program_btn = ttk.Menubutton(self.header, text="Select Program", style="Accent.TButton")
        self.program_menu = tk.Menu(self.program_btn, tearoff=0)
        self.populate_program_menu()
        self.program_btn["menu"] = self.program_menu
        self.program_btn.pack(side="left", padx=6)
        self.view_btn = ttk.Menubutton(self.header, text="View", style="Accent.TButton")
        self.view_menu = tk.Menu(self.view_btn, tearoff=0)
        self.view_menu.add_command(label="Toggle OCR", command=self.toggle_ocr)
        self.view_menu.add_command(label="Toggle Translation Log", command=self.toggle_translation)
        self.view_btn["menu"] = self.view_menu
        self.view_btn.pack(side="left", padx=6)
        self.theme_btn = ttk.Button(self.header, text="🌙", style="Accent.TButton", command=self.toggle_theme)
        self.theme_btn.pack(side="right", padx=6)

    def populate_program_menu(self):
        self.program_menu.delete(0, "end")
        self.program_menu.add_command(label="Full Screen", command=self.select_full_screen)
        self.program_menu.add_command(label="Select Area (TODO)", command=lambda: None)
        self.program_menu.add_separator()
        for w in gw.getAllWindows():
            if w.title.strip():
                self.program_menu.add_command(label=w.title, command=lambda h=w._hWnd: self.select_hwnd(h))

    def select_hwnd(self, hwnd):
        self.selected_hwnd = hwnd
        # Feedback
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
        settings_win.geometry("340x240")
        settings_win.minsize(320, 200)
        settings_win.transient(self.root)

        mainframe = ttk.Frame(settings_win, style="Card.TFrame", padding=18)
        mainframe.pack(fill="both", expand=True)

        ttk.Label(mainframe, text="Check Interval (sec):").pack(pady=6, anchor="w")
        interval_var = tk.IntVar(value=CHECK_INTERVAL)
        ttk.Spinbox(mainframe, from_=1, to=60, textvariable=interval_var, width=8).pack()

        ttk.Label(mainframe, text="Similarity Threshold (0.0 - 1.0):").pack(pady=6, anchor="w")
        threshold_var = tk.DoubleVar(value=SIMILARITY_THRESHOLD)
        ttk.Scale(mainframe, from_=0.5, to=1.0, orient=tk.HORIZONTAL, variable=threshold_var).pack(fill="x")

        def save_settings():
            global CHECK_INTERVAL, SIMILARITY_THRESHOLD
            CHECK_INTERVAL = interval_var.get()
            SIMILARITY_THRESHOLD = threshold_var.get()
            settings_win.destroy()

        ttk.Button(mainframe, text="Save", style="Accent.TButton", command=save_settings).pack(pady=(16, 0), anchor="e")

    def toggle_theme(self):
        current = self.root.tk.call("ttk::style", "theme", "use")
        if current == "azure-dark":
            self.root.tk.call("set_theme", "light")
            self.root.configure(bg="#f2f2f2")
            self.theme_btn.config(text="🌞")
        else:
            self.root.tk.call("set_theme", "dark")
            self.root.configure(bg="#202124")
            self.theme_btn.config(text="🌙")

    def toggle_ocr(self):
        if self.ocr_text in self.pane.panes():
            self.pane.forget(self.ocr_text)
        else:
            self.pane.add(self.ocr_text, before=self.translation_text)
            self.pane.update_idletasks()
            self.pane.sashpos(0, 350)

    def toggle_translation(self):
        if self.translation_text in self.pane.panes():
            self.pane.forget(self.translation_text)
        else:
            self.pane.add(self.translation_text, minsize=300)

    def create_main_pane(self):
        self.pane = ttk.PanedWindow(self.main_card, orient=tk.HORIZONTAL, style="Card.TFrame")
        self.pane.pack(fill="both", expand=True, padx=(0, 0), pady=(0, 0))

        self.ocr_text = tk.Text(self.pane, width=30, wrap=tk.WORD, font=("Consolas", 12),
                                bg="#232323", fg="#fff", insertbackground="#fff", relief="flat", bd=0)
        self.translation_text = tk.Text(self.pane, wrap=tk.WORD, font=("Consolas", 12),
                                        bg="#232323", fg="#fff", insertbackground="#fff", relief="flat", bd=0)
        self.pane.add(self.ocr_text)
        self.pane.add(self.translation_text)
        self.pane.update_idletasks()
        self.pane.sashpos(0, 350)

    def create_controls(self):
        controls = ttk.Frame(self.main_card, style="Card.TFrame")
        controls.pack(fill="x", pady=(10, 0), padx=(0,0))
        self.toggle_button = ttk.Button(controls, text="▶ Start", style="Accent.TButton", command=self.toggle_pipeline)
        self.toggle_button.pack(side="right", padx=10, pady=3)
        self.sizegrip = ttk.Sizegrip(self.root)
        self.sizegrip.pack(side="right", anchor="se", padx=6, pady=4)

    def toggle_pipeline(self):
        if self.running:
            self.stop_thread = True
            self.toggle_button.config(text="▶ Start")
        else:
            self.stop_thread = False
            threading.Thread(target=self.ocr_loop, daemon=True).start()
            self.toggle_button.config(text="⏸ Stop")
        self.running = not self.running

    def ocr_loop(self):
        while not self.stop_thread:
            if self.selected_hwnd is None or not ocr.is_visible(self.selected_hwnd):
                time.sleep(CHECK_INTERVAL)
                continue

            if self.llm_request_in_progress:
                time.sleep(CHECK_INTERVAL)
                continue

            screenshot = ocr.screenshot_window(self.selected_hwnd)

            if self.last_image and ocr.images_are_similar(screenshot, self.last_image, SIMILARITY_THRESHOLD):
                time.sleep(CHECK_INTERVAL)
                continue

            self.last_image = screenshot
            img_b64 = ocr.encode_image(screenshot)
            self.llm_request_in_progress = True
            try:
                ocr_text = ocr.ocr_image_with_vllm(img_b64)
            finally:
                self.llm_request_in_progress = False
            translation_text = translation.translate_text(ocr_text)
            self.ocr_queue.put((ocr_text, translation_text))
            time.sleep(CHECK_INTERVAL)

    def poll_queue(self):
        try:
            while not self.ocr_queue.empty():
                ocr_text, translation = self.ocr_queue.get_nowait()
                self.ocr_text.delete("1.0", tk.END)
                self.ocr_text.insert(tk.END, ocr_text)
                self.translation_text.insert(tk.END, f"\n{translation}\n")
                self.translation_text.see(tk.END)
        finally:
            self.root.after(500, self.poll_queue)
