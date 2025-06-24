"""
Service for translating text using LLM models.
"""

import re
import json
import requests
from typing import Optional, Generator, Callable
from datetime import datetime
from app.utils.logging import get_logger, log_function_call

# Initialize logger
logger = get_logger(__name__)

# API URLs
OPENAI_COMPAT_API_URL = "http://127.0.0.1:7860/v1/chat/completions"  # OpenAI-compatible endpoint
LM_STUDIO_API_URL = "http://127.0.0.1:7860/api/v0/chat/completions"  # LM Studio native API
DEFAULT_TRANSLATION_MODEL = "gemma-3-12b-it"
LOG_FILE = "logs/translation_log.txt"

@log_function_call
def extract_translation(content: str) -> str:
    """
    Extract the translation from the LLM response.
    
    Args:
        content: Raw LLM response
        
    Returns:
        Extracted translation text
    """
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

    logger.debug(f"Extracted translation (length: {len(translation)})")
    return translation

@log_function_call
def stream_translation(
    extracted_text: str, 
    timeout: int = 45, 
    translation_model_id: str = DEFAULT_TRANSLATION_MODEL
) -> Generator[str, None, None]:
    """
    Stream translation of text using LM Studio's native API.
    
    Args:
        extracted_text: Text to translate
        timeout: API timeout in seconds
        translation_model_id: Model ID for translation
        
    Yields:
        Partial translations as they become available
    """
    prompt = (
        "You are a professional translator. Translate the following text to English:"
        f"\n\n{extracted_text}\n\n"
        "Respond ONLY in the following format, and do not include any original (foreign) text, explanations, or formatting:\n"
        "TRANSLATION: [The full English translation here, and nothing else]\n\n"
        "If the text is already in English, output:\n"
        "TRANSLATION: [The original English text here, and nothing else]\n"
        "DO NOT REPEAT ANY PART OF THE ORIGINAL (FOREIGN) TEXT IN YOUR RESPONSE."
    )
    
    payload = {
        "model": translation_model_id,
        "messages": [{
            "role": "user",
            "content": prompt
        }],
        "temperature": 0.1,
        "max_tokens": 6000,
        "stream": True  # Enable streaming
    }
    
    try:
        logger.info(f"Starting streaming translation with model {translation_model_id}")
        
        # Start a thread to yield periodic updates even if the API is slow to respond
        import threading
        import time
        
        # Flag to signal when to stop the progress updates
        stop_event = threading.Event()
        
        # Variable to store the latest translation
        latest_translation = "Translating..."
        
        # Thread function to yield periodic updates
        def yield_periodic_updates():
            last_yield_time = time.time()
            while not stop_event.is_set():
                current_time = time.time()
                # Yield an update every 0.2 seconds if no new content has been received
                if current_time - last_yield_time >= 0.2:
                    yield latest_translation
                    last_yield_time = current_time
                time.sleep(0.1)
        
        # Start the periodic update thread
        update_thread = threading.Thread(target=lambda: None)  # Dummy thread, we'll use the generator directly
        
        with requests.post(LM_STUDIO_API_URL, json=payload, timeout=timeout, stream=True) as resp:
            resp.raise_for_status()
            
            # Initialize variables to store the accumulated translation
            accumulated_content = ""
            last_yield_time = time.time()
            
            # Process the streaming response
            for line in resp.iter_lines():
                if line:
                    # Parse the SSE data
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]  # Remove 'data: ' prefix
                        
                        # Check for the end of the stream
                        if data == "[DONE]":
                            break
                        
                        try:
                            # Parse the JSON chunk
                            chunk = json.loads(data)
                            
                            # Extract the content delta
                            if 'choices' in chunk and len(chunk['choices']) > 0:
                                delta = chunk['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                
                                if content:
                                    accumulated_content += content
                                    latest_translation = accumulated_content
                                    
                                    # Only yield if enough time has passed since last yield
                                    current_time = time.time()
                                    if current_time - last_yield_time >= 0.2:
                                        yield accumulated_content
                                        last_yield_time = current_time
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse JSON chunk: {data}")
                            continue
                
                # Yield periodic updates even if no new content
                current_time = time.time()
                if current_time - last_yield_time >= 0.5:
                    yield accumulated_content if accumulated_content else "Translating..."
                    last_yield_time = current_time
            
            # Final yield with extracted translation
            final_translation = extract_translation(accumulated_content)
            yield final_translation
            
            # Log the final translation
            log_translation(extracted_text, final_translation)
            
    except Exception as e:
        logger.error(f"Translation API error: {e}")
        yield ""
    finally:
        # Signal any background threads to stop
        stop_event.set()

@log_function_call
def translate_text(
    text: str, 
    timeout: int = 45, 
    stream_callback: Optional[Callable[[str], None]] = None,
    translation_model_id: str = DEFAULT_TRANSLATION_MODEL
) -> str:
    """
    Translate text to English, with optional streaming.
    
    Args:
        text: Text to translate
        timeout: API timeout in seconds
        stream_callback: Optional callback function for streaming updates
        translation_model_id: Model ID for translation
        
    Returns:
        The final translation text
    """
    if not text:
        logger.warning("Empty text provided for translation")
        return ""
    
    # Step 2: Translate with streaming if callback is provided
    if stream_callback:
        # Start streaming translation
        logger.info("Using streaming translation")
        final_translation = ""
        for partial_translation in stream_translation(text, timeout, translation_model_id):
            if partial_translation:
                final_translation = partial_translation
                # Call the callback with the partial translation
                stream_callback(partial_translation)
        return final_translation
    else:
        # Non-streaming version (fallback)
        logger.info("Using non-streaming translation")
        prompt = (
            "You are a professional translator. Translate the following text to English:"
            f"\n\n{text}\n\n"
            "Respond ONLY in the following format, and do not include any original (foreign) text, explanations, or formatting:\n"
            "TRANSLATION: [The full English translation here, and nothing else]\n\n"
            "If the text is already in English, output:\n"
            "TRANSLATION: [The original English text here, and nothing else]\n"
            "DO NOT REPEAT ANY PART OF THE ORIGINAL (FOREIGN) TEXT IN YOUR RESPONSE."
        )
        
        payload = {
            "model": translation_model_id,
            "messages": [{
                "role": "user",
                "content": prompt
            }],
            "temperature": 0.1,
            "max_tokens": 6000,
        }
        
        try:
            # Use LM Studio native API for non-streaming too
            resp = requests.post(LM_STUDIO_API_URL, json=payload, timeout=timeout)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            translation = extract_translation(content)
            
            # Log the translation
            log_translation(text, translation)
            
            return translation
        except Exception as e:
            logger.error(f"Translation API error: {e}")
            return ""

@log_function_call
def log_translation(original_text: str, translation_text: str) -> None:
    """
    Log a translation to a file.
    
    Args:
        original_text: Original text
        translation_text: Translated text
    """
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{'='*60}\nTimestamp: {ts}\n")
            f.write(f"Extracted: {original_text}\n")
            f.write(f"Translation: {translation_text}\n")
    except Exception as e:
        logger.error(f"Logging failed: {e}")
