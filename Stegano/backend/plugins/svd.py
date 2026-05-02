import struct
import numpy as np
from plugin_manager import SteganographyPlugin

class SVDPlugin(SteganographyPlugin):
    """
    Singular Value Decomposition (SVD) Steganography.
    Embeds data by modifying the singular values of image blocks.
    SVD provides a good balance between imperceptibility and robustness.
    """

    @property
    def name(self) -> str:
        return "SVD"

    @property
    def description(self) -> str:
        return "Singular Value Decomposition (SVD) based embedding. High robustness and low distortion."

    def get_capacity(self, image: np.ndarray) -> int:
        # 1 bit per 8x8 block per channel
        h, w = image.shape[:2]
        blocks_count = (h // 8) * (w // 8)
        channels = 1 if len(image.shape) == 2 else image.shape[2]
        # Total bits = blocks * channels. Return in bytes.
        return (blocks_count * channels) // 8

    def embed(self, carrier: np.ndarray, payload: bytes) -> np.ndarray:
        # Header: 4 bytes length
        full_payload = struct.pack(">I", len(payload)) + payload
        payload_bits = "".join(format(b, "08b") for b in full_payload)
        
        h, w = carrier.shape[:2]
        channels = 1 if len(carrier.shape) == 2 else carrier.shape[2]
        
        if len(payload_bits) > (h // 8) * (w // 8) * channels:
            raise ValueError(f"Payload too large for SVD embedding. Max bits: {(h // 8) * (w // 8) * channels}")

        stego = carrier.astype(np.float32).copy()
        bit_idx = 0
        
        # Quantization step for SVD
        # SVD values are typically larger than DCT coefficients, so we need a larger Q for robustness
        # or a smaller one for imperceptibility. 40-60 is usually okay for 8x8.
        Q = 60 

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
                    
                    # Apply SVD
                    u, s, vh = np.linalg.svd(block)
                    
                    # Iterative Robust Embedding
                    Q = 100.0
                    target_bit = int(payload_bits[bit_idx])
                    
                    val = s[0]
                    q_val = round(val / Q)
                    if q_val % 2 != target_bit:
                        if q_val > (val / Q): q_val -= 1
                        else: q_val += 1
                    
                    best_s0 = q_val * Q
                    
                    # Inner loop for rounding protection
                    max_attempts = 5
                    for attempt in range(max_attempts):
                        s[0] = best_s0
                        s_mat = np.zeros((8, 8))
                        np.fill_diagonal(s_mat, s)
                        temp_block = np.dot(u, np.dot(s_mat, vh))
                        
                        stego_block_uint8 = np.round(np.clip(temp_block, 0, 255)).astype(np.uint8)
                        
                        # Test extraction
                        _, s_extracted, _ = np.linalg.svd(stego_block_uint8.astype(np.float32))
                        test_val = s_extracted[0]
                        test_bit = int(round(test_val / Q)) % 2
                        
                        if test_bit == target_bit:
                            if channels == 1:
                                stego[i:i+8, j:j+8] = temp_block
                            else:
                                stego[i:i+8, j:j+8, c] = temp_block
                            break
                        else:
                            # Adjust
                            diff = (q_val * Q) - test_val
                            best_s0 += diff * 1.2
                    
                    bit_idx += 1
                if bit_idx >= len(payload_bits): break
            if bit_idx >= len(payload_bits): break
            
        # Use round instead of truncation to preserve singular values
        return np.round(np.clip(stego, 0, 255)).astype(np.uint8)

    def extract(self, stego: np.ndarray) -> bytes:
        h, w = stego.shape[:2]
        channels = 1 if len(stego.shape) == 2 else stego.shape[2]
        
        stego_f = stego.astype(np.float32)
        bits = []
        
        max_bits = (h // 8) * (w // 8) * channels
        Q = 100.0

        for c in range(channels):
            for i in range(0, h - 7, 8):
                for j in range(0, w - 7, 8):
                    if len(bits) >= max_bits: break
                    
                    if channels == 1:
                        block = stego_f[i:i+8, j:j+8]
                    else:
                        block = stego_f[i:i+8, j:j+8, c]
                        
                    u, s, vh = np.linalg.svd(block)
                    val = s[0]
                    bit = int(round(val / Q)) % 2
                    bits.append(str(bit))
                    
                if len(bits) >= max_bits: break
            if len(bits) >= max_bits: break
            
        if len(bits) < 32:
            raise ValueError("Could not extract SVD header.")
            
        length_bits = "".join(bits[:32])
        payload_len = struct.unpack(">I", bytes([int(length_bits[i:i+8], 2) for i in range(0, 32, 8)]))[0]
        
        if 32 + payload_len * 8 > len(bits):
            raise ValueError("Invalid length header or incorrect password/algorithm.")
            
        payload_bits = "".join(bits[32 : 32 + payload_len * 8])
        return bytes([int(payload_bits[i:i+8], 2) for i in range(0, len(payload_bits), 8)])
