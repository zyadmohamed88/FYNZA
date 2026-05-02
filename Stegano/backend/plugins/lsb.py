import struct

import numpy as np

from plugin_manager import SteganographyPlugin

# Constants
DELIMITER = b"####END####"
DELIMITER_BITS = "".join(format(byte, "08b") for byte in DELIMITER)

class LSBBasicPlugin(SteganographyPlugin):
    """
    Standard Least Significant Bit (LSB) Steganography.
    Embeds data sequentially into the least significant bits of the image pixels.
    """

    @property
    def name(self) -> str:
        return "LSB_Basic"

    @property
    def description(self) -> str:
        return "Standard sequential LSB embedding. High capacity, but statistically detectable by chi-square attacks."

    def get_capacity(self, image: np.ndarray) -> int:
        return image.size // 8

    def embed(self, carrier: np.ndarray, payload: bytes) -> np.ndarray:
        # Truly basic: just payload + delimiter, no length header
        payload_with_delim = payload + DELIMITER
        payload_bits = "".join(format(byte, "08b") for byte in payload_with_delim)
        
        bits_needed = len(payload_bits)
        capacity_bits = carrier.size
        
        if bits_needed > capacity_bits:
            raise ValueError(f"Image too small! Needs {bits_needed} bits, holds {capacity_bits}.")

        stego_flat = carrier.flatten().copy()
        
        for i, bit_char in enumerate(payload_bits):
            stego_flat[i] = (stego_flat[i] & 0b11111110) | int(bit_char)
            
        return stego_flat.reshape(carrier.shape)

    def extract(self, stego: np.ndarray) -> bytes:
        flat_pixels = stego.flatten()
        
        # We read bits and collect them into bytes until we find the delimiter
        all_bytes = []
        current_byte_bits = ""
        
        for i in range(len(flat_pixels)):
            current_byte_bits += str(flat_pixels[i] & 1)
            
            if len(current_byte_bits) == 8:
                byte_val = int(current_byte_bits, 2)
                all_bytes.append(byte_val)
                current_byte_bits = ""
                
                # Check for delimiter at the end of collected bytes
                if len(all_bytes) >= len(DELIMITER):
                    if bytes(all_bytes[-len(DELIMITER):]) == DELIMITER:
                        # Found it! Return everything before the delimiter
                        return bytes(all_bytes[:-len(DELIMITER)])
        
        raise ValueError("No valid message or delimiter found in the image.")
