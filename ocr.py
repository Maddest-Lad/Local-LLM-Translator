# ocr.py
import base64
from io import BytesIO
from PIL import Image
import requests
import numpy as np
from skimage.metrics import structural_similarity as ssim
import mss
import win32gui

VLLM_API_BASE = "http://127.0.0.1:7860/v1"
MODEL_NAME = "nanonets/Nanonets-OCR-s"

def is_visible(hwnd):
    import win32gui
    return win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd)

def get_window_bbox(hwnd):
    rect = win32gui.GetWindowRect(hwnd)
    return {'left': rect[0], 'top': rect[1], 'width': rect[2] - rect[0], 'height': rect[3] - rect[1]}

def screenshot_window(hwnd):
    bbox = get_window_bbox(hwnd)
    with mss.mss() as sct:
        sct_img = sct.grab(bbox)
        img = Image.frombytes("RGB", (sct_img.width, sct_img.height), sct_img.rgb)
    return img

def images_are_similar(img1, img2, threshold):
    img1_gray = np.array(img1.convert("L").resize((512, 512)))
    img2_gray = np.array(img2.convert("L").resize((512, 512)))
    score, _ = ssim(img1_gray, img2_gray, full=True)
    return score >= threshold

def encode_image(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def ocr_image_with_vllm(image_b64):
    payload = {
        "model": MODEL_NAME,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": "Extract the plain text from the image."},
            ]
        }],
        "temperature": 0.0,
        "max_tokens": 15000
    }
    response = requests.post(f"{VLLM_API_BASE}/chat/completions", json=payload)
    result = response.json()
    return result["choices"][0]["message"]["content"]
