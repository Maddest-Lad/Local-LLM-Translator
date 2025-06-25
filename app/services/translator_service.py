"""
Service for translating text using LLM models
"""

import re
import json
import requests
import asyncio
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
    translation_model_id: str = DEFAULT_TRANSLATION_MODEL,
    stream_callback: Optional[Callable[[str], None]] = None
) -> str:
    """
    Stream translation of text using LM Studio's native API.
    
    Args:
        extracted_text: Text to translate
        timeout: API timeout in seconds
        translation_model_id: Model ID for translation
        stream_callback: Optional callback for streaming updates
        
    Returns:
        Final translation text
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
        
        with requests.post(LM_STUDIO_API_URL, json=payload, timeout=timeout, stream=True) as resp:
            resp.raise_for_status()
            
            # Initialize variables to store the accumulated translation
            accumulated_content = ""
            last_callback_time = 0
            
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
                                    
                                    # Call the callback with some rate limiting
                                    import time
                                    current_time = time.time()
                                    if stream_callback and (current_time - last_callback_time >= 0.1):
                                        try:
                                            # Extract partial translation and call callback
                                            partial_translation = extract_translation(accumulated_content)
                                            stream_callback(partial_translation)
                                            last_callback_time = current_time
                                        except Exception as e:
                                            logger.error(f"Error in stream callback: {e}")
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse JSON chunk: {data}")
                            continue
            
            # Final extraction and callback
            final_translation = extract_translation(accumulated_content)
            if stream_callback:
                try:
                    stream_callback(final_translation)
                except Exception as e:
                    logger.error(f"Error in final stream callback: {e}")
            
            # Log the final translation
            log_translation(extracted_text, final_translation)
            
            return final_translation
            
    except Exception as e:
        logger.error(f"Translation API error: {e}")
        return ""

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
    
    # Use streaming translation if callback is provided
    if stream_callback:
        logger.info("Using streaming translation")
        return stream_translation(text, timeout, translation_model_id, stream_callback)
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