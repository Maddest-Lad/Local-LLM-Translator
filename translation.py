import threading

log_file_path = "translation_log.txt"
log_lock = threading.Lock()

def log_to_file(ocr_text, translation_text):
    with log_lock:
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(f"OCR: {ocr_text}\nTRANSLATION: {translation_text}\n{'-'*40}\n")

def translate_text(text, timeout=None):
    # Example: In real code, pass timeout to requests if using an API.
    import time
    start = time.time()
    # Simulate variable-length work
    while time.time() - start < 1:
        if timeout and time.time() - start > timeout:
            raise TimeoutError("Translation timed out.")
        time.sleep(0.1)
    return f"[Translated] {text}"
