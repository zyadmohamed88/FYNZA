import struct
import cv2
import numpy as np
from plugin_manager import SteganographyPlugin

class DCTPlugin(SteganographyPlugin):
    """
    Discrete Cosine Transform (DCT) Steganography.
    Embeds data in the frequency domain of the image.
    More robust than LSB against compression and filtering.
    """

    @property
    def name(self) -> str:
        return "DCT"

    @property
    def description(self) -> str:
        return "Frequency domain embedding using Discrete Cosine Transform. Robust and stealthy."

    def get_capacity(self, image: np.ndarray) -> int:
        # 1 bit per 8x8 block per channel
        h, w = image.shape[:2]
        blocks_count = (h // 8) * (w // 8)
        channels = 1 if len(image.shape) == 2 else image.shape[2]
        return (blocks_count * channels) // 8

    def embed(self, carrier: np.ndarray, payload: bytes) -> np.ndarray:
        # Header: 4 bytes length
        full_payload = struct.pack(">I", len(payload)) + payload
        payload_bits = "".join(format(b, "08b") for b in full_payload)
        
        h, w = carrier.shape[:2]
        channels = 1 if len(carrier.shape) == 2 else carrier.shape[2]
        
        if len(payload_bits) > (h // 8) * (w // 8) * channels:
            raise ValueError("Payload too large for DCT embedding in this image.")

        stego = carrier.astype(np.float32).copy()
        bit_idx = 0
        
        # Iterate over channels and 8x8 blocks
        for c in range(channels):
            for i in range(0, h - 7, 8):
                for j in range(0, w - 7, 8):
                    if bit_idx >= len(payload_bits):
                        break
                    
                    # Get block
                    if channels == 1:
                        block = stego[i:i+8, j:j+8]
                    else:
                        block = stego[i:i+8, j:j+8, c]
                    
                    # Apply DCT
                    dct_block = cv2.dct(block)
                    
                    # Embed bit in a mid-frequency coefficient (e.g., (4,4))
                    coeff = dct_block[4, 4]
                    # Iterative Robust Embedding
                    q = 100 # High quantization for robustness
                    target_bit = int(payload_bits[bit_idx])
                    
                    # We'll try to find the best coefficient value that survives uint8 rounding
                    val_q = coeff / q
                    quantized = int(round(val_q))
                    if quantized % 2 != target_bit:
                        if val_q > quantized: quantized += 1
                        else: quantized -= 1
                    
                    best_coeff = quantized * q
                    
                    # Inner loop to ensure the bit survives the float32 -> uint8 -> float32 trip
                    max_attempts = 5
                    for attempt in range(max_attempts):
                        dct_block[4, 4] = best_coeff
                        # IDCT -> Clip -> Round -> Uint8
                        temp_block = cv2.idct(dct_block)
                        stego_block_uint8 = np.round(np.clip(temp_block, 0, 255)).astype(np.uint8)
                        
                        # Test Extraction
                        test_dct = cv2.dct(stego_block_uint8.astype(np.float32))
                        test_val = test_dct[4, 4]
                        test_bit = int(round(test_val / q)) % 2
                        
                        if test_bit == target_bit:
                            # Success! Put the idct result back into stego
                            if channels == 1:
                                stego[i:i+8, j:j+8] = temp_block
                            else:
                                stego[i:i+8, j:j+8, c] = temp_block
                            break
                        else:
                            # Adjust best_coeff to be even more "inside" the quantization bin
                            diff = (quantized * q) - test_val
                            best_coeff += diff * 1.2
                    
                    bit_idx += 1
                if bit_idx >= len(payload_bits): break
            if bit_idx >= len(payload_bits): break
            
        # Use round instead of truncation to preserve DCT coefficients
        return np.round(np.clip(stego, 0, 255)).astype(np.uint8)

    def extract(self, stego: np.ndarray) -> bytes:
        h, w = stego.shape[:2]
        channels = 1 if len(stego.shape) == 2 else stego.shape[2]
        
        stego_f = stego.astype(np.float32)
        bits = []
        
        # We don't know the length yet, but we'll extract everything and then parse header
        # To be safe, we extract until capacity
        max_bits = (h // 8) * (w // 8) * channels
        q = 100
        
        for c in range(channels):
            for i in range(0, h - 7, 8):
                for j in range(0, w - 7, 8):
                    if len(bits) >= max_bits: break
                    
                    if channels == 1:
                        block = stego_f[i:i+8, j:j+8]
                    else:
                        block = stego_f[i:i+8, j:j+8, c]
                        
                    dct_block = cv2.dct(block)
                    coeff = dct_block[4, 4]
                    bit = int(round(coeff / q)) % 2
                    bits.append(str(bit))
                    
                if len(bits) >= max_bits: break
            if len(bits) >= max_bits: break
            
        # Parse header (first 32 bits)
        if len(bits) < 32:
            raise ValueError("Could not extract DCT header.")
            
        length_bits = "".join(bits[:32])
        payload_len = struct.unpack(">I", bytes([int(length_bits[i:i+8], 2) for i in range(0, 32, 8)]))[0]
        
        if 32 + payload_len * 8 > len(bits):
            raise ValueError("Extracted length header is invalid.")
            
        payload_bits = "".join(bits[32 : 32 + payload_len * 8])
        return bytes([int(payload_bits[i:i+8], 2) for i in range(0, len(payload_bits), 8)])
