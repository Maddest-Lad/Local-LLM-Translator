import base64
from io import BytesIO
import re
from PIL import Image
import requests
import numpy as np
from skimage.metrics import structural_similarity as ssim
import mss
import win32gui
from datetime import datetime

GEMMA_API_URL = "http://127.0.0.1:7860/v1/chat/completions"
GEMMA_MODEL = "gemma-3-27b-it"
LOG_FILE = "translation_log.txt"

def is_window_visible(hwnd):
    return win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd)

def get_window_bbox(hwnd):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    return {'left': left, 'top': top, 'width': right - left, 'height': bottom - top}

def screenshot_window(hwnd):
    bbox = get_window_bbox(hwnd)
    with mss.mss() as sct:
        img = Image.frombytes(
            "RGB",
            (bbox['width'], bbox['height']),
            sct.grab(bbox).rgb
        )
    return img

def images_are_similar(img1, img2, threshold=0.90):
    """Returns True if two images are visually similar using SSIM."""
    a = np.array(img1.convert("L").resize((512, 512)))
    b = np.array(img2.convert("L").resize((512, 512)))
    score, _ = ssim(a, b, full=True)
    return score >= threshold

def encode_image(image):
    """Encode a PIL image as base64 PNG."""
    buf = BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def extract_translation(content):
    # Remove markdown code blocks
    content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)

    # Look for the TRANSLATION block (case-insensitive)
    match = re.search(r'TRANSLATION:\s*([\s\S]+)', content, flags=re.IGNORECASE)
    if match:
        translation = match.group(1).strip()
    else:
        # If not found, assume the LLM returned just the translation
        translation = content.strip()

    # Remove common instruction lines or apologies if present
    translation = re.sub(
        r"(instructions?:|the above|as requested|no other commentary|do not include).*",
        "",
        translation,
        flags=re.IGNORECASE | re.DOTALL
    ).strip()

    # Remove any markdown left (accidental formatting)
    translation = re.sub(r"^[#>*\-`]", "", translation, flags=re.MULTILINE).strip()

    return translation

def translate_screen(image_b64, timeout=45):
    prompt = (
        "You are a professional translator. Extract all visible text from the image and translate it to English."
        "\n\n"
        "Respond ONLY in the following format, and do not include any original (foreign) text, explanations, or formatting:\n"
        "TRANSLATION: [The full English translation here, and nothing else]\n\n"
        "If the text is already in English, output:\n"
        "TRANSLATION: [The original English text here, and nothing else]\n"
        "DO NOT REPEAT ANY PART OF THE ORIGINAL (FOREIGN) TEXT IN YOUR RESPONSE."
    )
    payload = {
        "model": GEMMA_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ]
        }],
        "temperature": 0.1,
        "max_tokens": 6000,
    }
    try:
        resp = requests.post(GEMMA_API_URL, json=payload, timeout=timeout)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        translation = extract_translation(content)
        return translation
    except Exception as e:
        print(f"Translation API error: {e}")
        return ""

def log_translation(original_text, translation_text):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{'='*60}\nTimestamp: {ts}\n")
            f.write(f"Extracted: {original_text}\n")
            f.write(f"Translation: {translation_text}\n")
    except Exception as e:
        print(f"Logging failed: {e}")
