import tkinter as tk
from gui import OCRApp

if __name__ == "__main__":
    root = tk.Tk()
    root.tk.call("source", "Azure-ttk-theme/azure.tcl")
    root.tk.call("set_theme", "dark")
    app = OCRApp(root)
    root.mainloop()
