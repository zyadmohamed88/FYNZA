"""
steganography.py
----------------
Core LSB (Least Significant Bit) engine.

How LSB steganography works:
  Every pixel channel value is an 8-bit number (0-255).
  We replace the *last* bit (the least significant bit) with
  one bit of our secret data.  Changing 0→1 or 1→0 in the LSB
  alters the channel value by at most ±1, which is invisible to
  the human eye.

  Example:
      Original pixel R value : 10110101  (181)
      Secret bit to hide      :        1
      New pixel R value       : 10110101  (181)  ← LSB was already 1
                     or       : 10110101  (181)  same

      Original pixel R value : 11001100  (204)
      Secret bit to hide      :        1
      New pixel R value       : 11001101  (205)  ← only +1 change

Data layout embedded in the image:
  [ 4-byte length header (big-endian uint32) ][ encrypted payload bytes ][ delimiter "####END####" ]

The length header lets extraction stop precisely without scanning the
entire image, and the delimiter acts as a second safety net.
"""

import struct

import numpy as np

from image_utils import get_image_capacity

# ─────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────

# Unique end-of-message marker appended after the encrypted payload.
# "####END####" in UTF-8 bytes, then converted to a binary string.
DELIMITER       = b"####END####"
DELIMITER_BITS  = "".join(format(byte, "08b") for byte in DELIMITER)


# ─────────────────────────────────────────────────────────────
#  Helpers — bytes ↔ bit-string conversion
# ─────────────────────────────────────────────────────────────

def bytes_to_bits(data: bytes) -> str:
    """
    Convert a bytes object to a string of '0' and '1' characters.

    Example:
        bytes_to_bits(b'\\x00') → '00000000'
        bytes_to_bits(b'A')     → '01000001'

    Args:
        data: Any bytes object.

    Returns:
        A string of '0'/'1' characters, 8 per input byte.
    """
    return "".join(format(byte, "08b") for byte in data)


def bits_to_bytes(bit_string: str) -> bytes:
    """
    Convert a '0'/'1' string back into bytes.

    Args:
        bit_string: A string whose length is a multiple of 8.

    Returns:
        The corresponding bytes object.
    """
    # Split into 8-bit chunks and convert each to an integer
    byte_values = [
        int(bit_string[i : i + 8], 2)
        for i in range(0, len(bit_string), 8)
    ]
    return bytes(byte_values)


# ─────────────────────────────────────────────────────────────
#  Embedding
# ─────────────────────────────────────────────────────────────

def embed_message(carrier_image: np.ndarray, encrypted_data: bytes) -> np.ndarray:
    """
    Hide encrypted bytes inside a carrier image using LSB substitution.

    Process:
      1. Build payload = 4-byte length + encrypted_data + delimiter.
      2. Convert payload to a bit-string.
      3. Flatten the image pixel array.
      4. For each bit, replace the LSB of the next pixel channel.
      5. Reshape the flat array back to the original image shape.

    Args:
        carrier_image:  NumPy array of the original image (not modified in-place).
        encrypted_data: Bytes from crypto_utils.encrypt_message().

    Returns:
        A new NumPy array (the stego image) with the message hidden inside.

    Raises:
        ValueError: If the image does not have enough capacity.
    """
    # --- capacity check -----------------------------------------------
    # payload = 4-byte header + encrypted data + delimiter bytes
    payload       = struct.pack(">I", len(encrypted_data)) + encrypted_data + DELIMITER
    payload_bits  = bytes_to_bits(payload)
    bits_needed   = len(payload_bits)

    capacity_bytes = get_image_capacity(carrier_image)
    capacity_bits  = capacity_bytes * 8

    if bits_needed > capacity_bits:
        raise ValueError(
            f"Image too small!  Needs {bits_needed} bits but image only "
            f"holds {capacity_bits} bits ({capacity_bytes} bytes).  "
            f"Use a larger image or a shorter message."
        )

    # --- embedding -------------------------------------------------------
    # Work on a flat copy so we don't modify the caller's array
    stego_flat = carrier_image.flatten().copy()

    for bit_index, bit_char in enumerate(payload_bits):
        pixel_value = stego_flat[bit_index]

        # Replace LSB: clear bit-0 with AND 0b11111110, then OR with new bit
        stego_flat[bit_index] = (pixel_value & 0b11111110) | int(bit_char)

    # Reshape back to original image dimensions
    stego_image = stego_flat.reshape(carrier_image.shape)
    return stego_image


# ─────────────────────────────────────────────────────────────
#  Extraction
# ─────────────────────────────────────────────────────────────

def extract_message(stego_image: np.ndarray) -> bytes:
    """
    Recover the hidden encrypted bytes from a stego image.

    Process:
      1. Flatten the pixel array and read one LSB per channel value.
      2. Read the first 32 bits → decode the 4-byte length header.
      3. Read exactly (length * 8) more bits → that is the encrypted payload.
      4. Verify the delimiter follows (sanity check).
      5. Return the raw encrypted bytes.

    Args:
        stego_image: NumPy array of the stego image.

    Returns:
        The encrypted bytes that were embedded by embed_message().

    Raises:
        ValueError: If no valid message / delimiter is found (wrong image or
                    the image was not produced by this system).
    """
    flat_pixels = stego_image.flatten()

    # Helper: read N bits starting at offset, return bit-string
    def read_bits(offset: int, count: int) -> str:
        return "".join(str(flat_pixels[offset + i] & 1) for i in range(count))

    # ── Step 1: Read 4-byte (32-bit) length header ─────────────────────
    if len(flat_pixels) < 32:
        raise ValueError("Image is too small to contain any hidden data.")

    length_bits  = read_bits(0, 32)
    payload_len  = struct.unpack(">I", bits_to_bytes(length_bits))[0]   # number of encrypted bytes

    # Basic sanity check on reported length
    bits_needed = 32 + payload_len * 8 + len(DELIMITER_BITS)
    if bits_needed > len(flat_pixels):
        raise ValueError(
            "The length header in the image is invalid — this image may not "
            "contain a hidden message, or it has been modified."
        )

    # ── Step 2: Read the encrypted payload ─────────────────────────────
    payload_bits       = read_bits(32, payload_len * 8)
    encrypted_payload  = bits_to_bytes(payload_bits)

    # ── Step 3: Verify delimiter ────────────────────────────────────────
    delimiter_offset = 32 + payload_len * 8
    found_delim_bits = read_bits(delimiter_offset, len(DELIMITER_BITS))

    if found_delim_bits != DELIMITER_BITS:
        raise ValueError(
            "Delimiter not found at the expected position.  "
            "The image may not contain a valid hidden message."
        )

    return encrypted_payload
