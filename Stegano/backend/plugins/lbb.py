import struct
import numpy as np
from plugin_manager import SteganographyPlugin

class LBBPlugin(SteganographyPlugin):
    """
    Local Binary Block (LBB) Steganography.
    Embeds bits by modifying the relationship between a center pixel and its 8 neighbors.
    Inspired by Local Binary Patterns (LBP).
    """

    @property
    def name(self) -> str:
        return "LBB"

    @property
    def description(self) -> str:
        return "Local Binary Block embedding. Hides 8 bits in every 3x3 block by adjusting neighbor values relative to the center."

    def get_capacity(self, image: np.ndarray) -> int:
        h, w = image.shape[:2]
        # Each 3x3 block holds 8 bits (1 byte)
        blocks_h = h // 3
        blocks_w = w // 3
        channels = 1 if len(image.shape) == 2 else image.shape[2]
        return (blocks_h * blocks_w * channels)

    def embed(self, carrier: np.ndarray, payload: bytes) -> np.ndarray:
        full_payload = struct.pack(">I", len(payload)) + payload
        payload_bits = "".join(format(b, "08b") for b in full_payload)
        
        h, w = carrier.shape[:2]
        channels = 1 if len(carrier.shape) == 2 else carrier.shape[2]
        
        if len(payload_bits) > (h // 3) * (w // 3) * 8 * channels:
            raise ValueError("Payload too large for LBB embedding.")

        stego = carrier.copy().astype(np.int32)
        bit_idx = 0
        
        for c in range(channels):
            for i in range(0, h - 2, 3):
                for j in range(0, w - 2, 3):
                    if bit_idx >= len(payload_bits): break
                    
                    # Get the 3x3 block
                    if channels == 1:
                        block = stego[i:i+3, j:j+3]
                    else:
                        block = stego[i:i+3, j:j+3, c]
                        
                    center = block[1, 1]
                    
                    # Embed 8 bits in the neighbors
                    for x in range(3):
                        for y in range(3):
                            if x == 1 and y == 1: continue # Skip center
                            if bit_idx >= len(payload_bits): break
                            
                            bit = int(payload_bits[bit_idx])
                            neighbor = block[x, y]
                            
                            if bit == 1:
                                # Ensure neighbor >= center
                                if neighbor < center:
                                    block[x, y] = center
                            else:
                                # Ensure neighbor < center
                                if neighbor >= center:
                                    block[x, y] = max(0, center - 1)
                            
                            bit_idx += 1
                if bit_idx >= len(payload_bits): break
            if bit_idx >= len(payload_bits): break
            
        return np.clip(stego, 0, 255).astype(np.uint8)

    def extract(self, stego: np.ndarray) -> bytes:
        h, w = stego.shape[:2]
        channels = 1 if len(stego.shape) == 2 else stego.shape[2]
        
        bits = []
        max_bits = (h // 3) * (w // 3) * 8 * channels
        
        for c in range(channels):
            for i in range(0, h - 2, 3):
                for j in range(0, w - 2, 3):
                    if len(bits) >= max_bits: break
                    
                    if channels == 1:
                        block = stego[i:i+3, j:j+3]
                    else:
                        block = stego[i:i+3, j:j+3, c]
                        
                    center = block[1, 1]
                    
                    for x in range(3):
                        for y in range(3):
                            if x == 1 and y == 1: continue
                            if len(bits) >= max_bits: break
                            
                            neighbor = block[x, y]
                            bits.append("1" if neighbor >= center else "0")
                            
                if len(bits) >= max_bits: break
            if len(bits) >= max_bits: break
            
        # Parse header
        if len(bits) < 32: raise ValueError("LBB header not found.")
        length_bits = "".join(bits[:32])
        payload_len = struct.unpack(">I", bytes([int(length_bits[i:i+8], 2) for i in range(0, 32, 8)]))[0]
        
        if 32 + payload_len * 8 > len(bits):
            raise ValueError("Invalid LBB data.")
            
        payload_bits = "".join(bits[32 : 32 + payload_len * 8])
        return bytes([int(payload_bits[i:i+8], 2) for i in range(0, len(payload_bits), 8)])
