"""
image_utils.py
--------------
Handles loading, saving, and quality evaluation of images.

Supports:
  - RGB colour images
  - Grayscale images
  - PSNR (Peak Signal-to-Noise Ratio) calculation to measure
    how much the steganography visually affects the image
"""

import math

import cv2
import numpy as np


# ─────────────────────────────────────────────────────────────
#  Load / Save
# ─────────────────────────────────────────────────────────────

def load_image(image_path: str) -> np.ndarray:
    """
    Load an image from disk and return it as a NumPy array.

    Uses cv2.IMREAD_UNCHANGED so that:
      - RGB/BGR colour images keep all three channels.
      - Grayscale images keep a single channel.

    Args:
        image_path: Absolute or relative path to the image file.

    Returns:
        NumPy array with shape (H, W, 3) for colour or (H, W) for grayscale.

    Raises:
        FileNotFoundError: If the path does not exist or is unreadable.
    """
    image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(
            f"Cannot load image — check the path: '{image_path}'"
        )
    return image


def save_image(image: np.ndarray, output_path: str) -> None:
    """
    Save a NumPy array as an image file.

    The format is inferred from the file extension (e.g. .png, .bmp).
    Always use a lossless format (PNG or BMP) when saving stego images
    because JPEG compression would destroy the hidden LSB data.

    Args:
        image:       NumPy array to save.
        output_path: Destination path including file extension.
    """
    success = cv2.imwrite(output_path, image)
    if not success:
        raise IOError(f"Failed to write image to '{output_path}'.")
    print(f"[✓] Image saved → {output_path}")


# ─────────────────────────────────────────────────────────────
#  Capacity Check
# ─────────────────────────────────────────────────────────────

def get_image_capacity(image: np.ndarray) -> int:
    """
    Calculate how many bytes can be hidden in this image.

    Each pixel channel can store 1 bit in its LSB.
    Total bits available = total number of pixel-channel values.
    Total bytes available = total bits // 8.

    Args:
        image: NumPy array of the carrier image.

    Returns:
        Maximum number of bytes that can be embedded.
    """
    total_pixels  = image.size          # total pixel-channel values
    total_bits    = total_pixels        # 1 bit per channel value
    capacity_bytes = total_bits // 8
    return capacity_bytes


# ─────────────────────────────────────────────────────────────
#  Quality Evaluation — PSNR
# ─────────────────────────────────────────────────────────────

def calculate_psnr(original: np.ndarray, modified: np.ndarray) -> float:
    """
    Compute the Peak Signal-to-Noise Ratio between two images.

    PSNR formula:
        MSE  = mean( (original - modified)^2 )
        PSNR = 10 * log10( MAX^2 / MSE )

    where MAX is the maximum possible pixel value (255 for 8-bit images).

    A higher PSNR means less visible distortion:
      - > 40 dB  →  excellent (imperceptible change)
      - 30–40 dB →  acceptable
      - < 30 dB  →  noticeable distortion

    Args:
        original: The carrier image before embedding.
        modified: The stego image after embedding.

    Returns:
        PSNR value in decibels (dB), or math.inf if the images are identical.
    """
    if original.shape != modified.shape:
        raise ValueError("Original and modified images must have the same shape.")

    # Convert to float64 to avoid integer overflow during squaring
    orig_f = original.astype(np.float64)
    mod_f  = modified.astype(np.float64)

    mse = np.mean((orig_f - mod_f) ** 2)

    if mse == 0:
        return math.inf          # Images are perfectly identical

    max_pixel = 255.0
    psnr = 10.0 * math.log10((max_pixel ** 2) / mse)
    return psnr
