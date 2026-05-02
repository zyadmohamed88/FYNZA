import struct
import cv2
import numpy as np
from plugin_manager import SteganographyPlugin

class OverlayBase(SteganographyPlugin):
    """Base class for Overlay-based watermarking plugins."""
    
    def __init__(self, mode="add", k=0.1):
        self._mode = mode
        self._k = k

    def get_capacity(self, image: np.ndarray) -> int:
        # We use 8x8 blocks to store 1 bit each for robustness
        h, w = image.shape[:2]
        return (h // 8) * (w // 8) // 8

    def _get_base_pattern(self):
        # We use strictly orthogonal structured patterns for each mode.
        # This guarantees that the cross-correlation between different modes is zero.
        if self._mode == "add":
            # 1x1 checkerboard (standard)
            p = np.indices((8, 8)).sum(axis=0) % 2
        elif self._mode == "alpha":
            # 2x2 blocks checkerboard
            p = (np.indices((8, 8))[0] // 2 + np.indices((8, 8))[1] // 2) % 2
        elif self._mode == "mul":
            # 4x4 blocks checkerboard
            p = (np.indices((8, 8))[0] // 4 + np.indices((8, 8))[1] // 4) % 2
        else:
            p = np.indices((8, 8)).sum(axis=0) % 2
            
        return (p * 2 - 1).astype(np.float32)

    def _payload_to_pattern(self, payload_bits, shape):
        h, w = shape
        pattern = np.zeros((h, w), dtype=np.float32)
        base = self._get_base_pattern()
        idx = 0
        for i in range(0, h - 7, 8):
            for j in range(0, w - 7, 8):
                if idx >= len(payload_bits): break
                # If bit is '1', embed base; if '0', embed -base
                sign = 1.0 if payload_bits[idx] == '1' else -1.0
                pattern[i:i+8, j:j+8] = sign * base
                idx += 1
        return pattern

    def embed_logic(self, img, pattern):
        k = self._k
        if self._mode == "add":
            # img + k * pattern * 128
            # pattern is already symmetric (-1 to 1)
            return img + k * pattern * 128
        elif self._mode == "alpha":
            # img*(1-k) + w*k, where w is pattern-based
            # Neutral point is 128
            w = pattern * 128 + 128
            return img * (1 - k) + w * k
        elif self._mode == "mul":
            # img*(1 + k*pattern)
            img_norm = img / 255.0
            res = img_norm * (1 + k * pattern * 0.5)
            return res * 255.0
        return img

    def embed(self, carrier: np.ndarray, payload: bytes) -> np.ndarray:
        full_payload = struct.pack(">I", len(payload)) + payload
        payload_bits = "".join(format(b, "08b") for b in full_payload)
        
        h, w = carrier.shape[:2]
        pattern = self._payload_to_pattern(payload_bits, (h, w))
        
        stego = carrier.astype(np.float32).copy()
        channels = 1 if len(carrier.shape) == 2 else carrier.shape[2]
        
        for c in range(channels):
            if channels == 1:
                stego = self.embed_logic(stego, pattern)
            else:
                stego[:, :, c] = self.embed_logic(stego[:, :, c], pattern)
                
        return np.clip(stego, 0, 255).astype(np.uint8)

    def extract(self, stego: np.ndarray) -> bytes:
        h, w = stego.shape[:2]
        channels = 1 if len(stego.shape) == 2 else stego.shape[2]
        stego_f = stego.astype(np.float32)
        
        # Blind extraction using high-pass (difference from blurred version)
        if channels > 1:
            # Use luminance or average for extraction
            img = np.mean(stego_f, axis=2)
        else:
            img = stego_f
            
        blurred = cv2.GaussianBlur(img, (15, 15), 0)
        diff = img - blurred
        
        bits = []
        max_bits = (h // 8) * (w // 8)
        base = self._get_base_pattern()
        
        for i in range(0, h - 7, 8):
            for j in range(0, w - 7, 8):
                if len(bits) >= max_bits: break
                block = diff[i:i+8, j:j+8]
                # Correlate with base pattern
                correlation = np.mean(block * base)
                bits.append("1" if correlation > 0 else "0")
        
        if len(bits) < 32: raise ValueError("Header not found")
        len_bits = "".join(bits[:32])
        p_len = struct.unpack(">I", bytes([int(len_bits[i:i+8], 2) for i in range(0, 32, 8)]))[0]
        
        if 32 + p_len * 8 > len(bits): raise ValueError("Extraction failed")
        p_bits = "".join(bits[32 : 32 + p_len * 8])
        return bytes([int(p_bits[i:i+8], 2) for i in range(0, len(p_bits), 8)])

class OverlayAddPlugin(OverlayBase):
    def __init__(self): super().__init__(mode="add", k=0.2)
    @property
    def name(self): return "Overlay_Add"
    @property
    def description(self): return "Additive Overlay: img + k*watermark. High robustness."

class OverlayAlphaPlugin(OverlayBase):
    def __init__(self): super().__init__(mode="alpha", k=0.15)
    @property
    def name(self): return "Overlay_Alpha"
    @property
    def description(self): return "Transparency Overlay: img*(1-k) + w*k. Balanced visibility."

class OverlayMulPlugin(OverlayBase):
    def __init__(self): super().__init__(mode="mul", k=0.2)
    @property
    def name(self): return "Overlay_Mul"
    @property
    def description(self): return "Multiplicative Overlay: img*(1 + k*w). Natural blending."
