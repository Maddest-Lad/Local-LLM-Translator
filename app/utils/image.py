"""
Image processing utilities.
"""

import base64
import io
import cv2
import numpy as np
from PIL import Image
from typing import Tuple, Optional
import logging

from app.utils.logging import get_logger, log_function_call

# Initialize logger
logger = get_logger(__name__)

@log_function_call
def encode_image(image: Image.Image) -> str:
    """
    Encode a PIL Image to base64.
    
    Args:
        image: PIL Image to encode
        
    Returns:
        Base64 encoded image string
    """
    try:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return img_str
    except Exception as e:
        logger.error(f"Error encoding image: {e}")
        return ""

@log_function_call
def decode_image(base64_string: str) -> Optional[Image.Image]:
    """
    Decode a base64 string to a PIL Image.
    
    Args:
        base64_string: Base64 encoded image string
        
    Returns:
        PIL Image or None if decoding fails
    """
    try:
        img_data = base64.b64decode(base64_string)
        img = Image.open(io.BytesIO(img_data))
        return img
    except Exception as e:
        logger.error(f"Error decoding image: {e}")
        return None

@log_function_call
def pil_to_cv2(pil_image: Image.Image) -> np.ndarray:
    """
    Convert a PIL Image to a cv2 image (numpy array).
    
    Args:
        pil_image: PIL Image to convert
        
    Returns:
        cv2 image (numpy array)
    """
    try:
        # Convert PIL Image to numpy array
        cv2_image = np.array(pil_image)
        
        # Convert RGB to BGR (cv2 format)
        if cv2_image.shape[2] == 3:  # If it has 3 channels (RGB)
            cv2_image = cv2.cvtColor(cv2_image, cv2.COLOR_RGB2BGR)
        
        return cv2_image
    except Exception as e:
        logger.error(f"Error converting PIL to cv2: {e}")
        return np.zeros((100, 100, 3), dtype=np.uint8)  # Return empty image

@log_function_call
def cv2_to_pil(cv2_image: np.ndarray) -> Image.Image:
    """
    Convert a cv2 image (numpy array) to a PIL Image.
    
    Args:
        cv2_image: cv2 image (numpy array) to convert
        
    Returns:
        PIL Image
    """
    try:
        # Convert BGR to RGB (PIL format)
        if cv2_image.shape[2] == 3:  # If it has 3 channels (BGR)
            cv2_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
        
        # Convert numpy array to PIL Image
        pil_image = Image.fromarray(cv2_image)
        
        return pil_image
    except Exception as e:
        logger.error(f"Error converting cv2 to PIL: {e}")
        return Image.new('RGB', (100, 100), 0)  # Return empty image (black)

@log_function_call
def images_are_similar(img1: Image.Image, img2: Image.Image, threshold: float = 0.90) -> bool:
    """
    Check if two images are similar using structural similarity index.
    
    Args:
        img1: First image
        img2: Second image
        threshold: Similarity threshold (0.0 to 1.0)
        
    Returns:
        True if images are similar, False otherwise
    """
    try:
        # Convert PIL images to cv2 format
        cv2_img1 = pil_to_cv2(img1)
        cv2_img2 = pil_to_cv2(img2)
        
        # Resize images to the same size if they are different
        if cv2_img1.shape != cv2_img2.shape:
            height, width = cv2_img1.shape[:2]
            cv2_img2 = cv2.resize(cv2_img2, (width, height))
        
        # Convert to grayscale
        gray1 = cv2.cvtColor(cv2_img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(cv2_img2, cv2.COLOR_BGR2GRAY)
        
        # Calculate Mean Structural Similarity Index (SSIM)
        # We'll implement a simplified version of SSIM using NumPy operations
        
        # Convert to NumPy arrays for easier calculations
        gray1_np = np.array(gray1, dtype=np.float64)
        gray2_np = np.array(gray2, dtype=np.float64)
        
        # 1. Calculate mean of each image
        mean1 = np.mean(gray1_np)
        mean2 = np.mean(gray2_np)
        
        # 2. Calculate variance and covariance
        # Variance of image1
        temp1 = gray1_np - mean1
        variance1 = np.mean(temp1 * temp1)
        
        # Variance of image2
        temp2 = gray2_np - mean2
        variance2 = np.mean(temp2 * temp2)
        
        # Covariance
        covariance = np.mean(temp1 * temp2)
        
        # 3. Constants to stabilize division (standard values from the SSIM paper)
        C1 = (0.01 * 255)**2
        C2 = (0.03 * 255)**2
        
        # 4. Calculate SSIM
        numerator = (2 * mean1 * mean2 + C1) * (2 * covariance + C2)
        denominator = (mean1**2 + mean2**2 + C1) * (variance1 + variance2 + C2)
        score = numerator / denominator
        
        logger.debug(f"Image similarity score: {score:.4f}")
        
        return bool(score >= threshold)
    except Exception as e:
        logger.error(f"Error comparing images: {e}")
        return False
