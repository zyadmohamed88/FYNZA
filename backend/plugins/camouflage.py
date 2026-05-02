import os
import struct

import numpy as np

from plugin_manager import SteganographyPlugin

DELIMITER = b"####END####"

class CamouflageLSBPlugin(SteganographyPlugin):
    """
    Camouflage LSB Steganography.
    Embeds the payload, but ALSO overwrites ALL remaining LSBs in the image 
    with cryptographically secure random noise.
    This defeats Chi-Square and structural steganalysis because the entire image 
    has uniform LSB distribution, making it indistinguishable from a noisy sensor.
    """

    @property
    def name(self) -> str:
        return "Camouflage_LSB"

    @property
    def description(self) -> str:
        return "Embeds data and fills the rest of the image with random noise. Maximum stealth against statistical attacks."

    def get_capacity(self, image: np.ndarray) -> int:
        return image.size // 8

    def embed(self, carrier: np.ndarray, payload: bytes) -> np.ndarray:
        payload_with_header = struct.pack(">I", len(payload)) + payload + DELIMITER
        payload_bits = "".join(format(byte, "08b") for byte in payload_with_header)
        
        bits_needed = len(payload_bits)
        capacity_bits = carrier.size
        
        if bits_needed > capacity_bits:
            raise ValueError(f"Image too small! Needs {bits_needed} bits, holds {capacity_bits}.")

        stego_flat = carrier.flatten().copy()
        
        # 1. Embed the actual payload
        for i, bit_char in enumerate(payload_bits):
            stego_flat[i] = (stego_flat[i] & 0b11111110) | int(bit_char)
            
        # 2. Fill the rest with random noise (Camouflage)
        remaining_bits = capacity_bits - bits_needed
        if remaining_bits > 0:
            # Generate random bytes
            random_bytes = os.urandom((remaining_bits // 8) + 1)
            random_bits = "".join(format(byte, "08b") for byte in random_bytes)[:remaining_bits]
            
            for i, bit_char in enumerate(random_bits):
                idx = bits_needed + i
                stego_flat[idx] = (stego_flat[idx] & 0b11111110) | int(bit_char)
                
        return stego_flat.reshape(carrier.shape)

    def extract(self, stego: np.ndarray) -> bytes:
        flat_pixels = stego.flatten()
        
        def read_bits(offset: int, count: int) -> str:
            return "".join(str(flat_pixels[offset + i] & 1) for i in range(count))

        if len(flat_pixels) < 32:
            raise ValueError("Image too small.")

        # 1. Read length header
        length_bits = read_bits(0, 32)
        payload_len = struct.unpack(">I", bytes([int(length_bits[i:i+8], 2) for i in range(0, 32, 8)]))[0]
        
        # 2. Safety check
        delim_bits_len = len(DELIMITER) * 8
        if 32 + payload_len * 8 + delim_bits_len > len(flat_pixels):
            raise ValueError("Invalid payload length or image too small.")

        # 3. Read payload
        payload_bits = read_bits(32, payload_len * 8)
        payload = bytes([int(payload_bits[i:i+8], 2) for i in range(0, len(payload_bits), 8)])
        
        # 4. Verify delimiter
        delim_bits = read_bits(32 + payload_len * 8, delim_bits_len)
        found_delim = bytes([int(delim_bits[i:i+8], 2) for i in range(0, len(delim_bits), 8)])
        
        if found_delim != DELIMITER:
            raise ValueError("Data corruption or invalid algorithm: Delimiter not found.")
            
        return payload
