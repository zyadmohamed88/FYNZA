import struct
import numpy as np

from plugin_manager import SteganographyPlugin

class AdaptiveEdgePlugin(SteganographyPlugin):
    """
    Scattered Pseudo-Random Steganography (Replaces fragile Canny Edge).
    Embeds data randomly across the image using a deterministic PRNG sequence.
    This provides maximum stealth against sequential structural attacks while
    ensuring 100% reliable extraction, unlike edge-based detectors.
    """

    @property
    def name(self) -> str:
        return "Adaptive_Edge"

    @property
    def description(self) -> str:
        return "Scatters payload pseudo-randomly across the image to avoid sequential detection signatures."

    def get_capacity(self, image: np.ndarray) -> int:
        return image.size // 8

    def embed(self, carrier: np.ndarray, payload: bytes) -> np.ndarray:
        full_payload = struct.pack(">I", len(payload)) + payload
        bits = "".join(format(b, "08b") for b in full_payload)
        
        if len(bits) > carrier.size:
            raise ValueError(f"Payload too large. Needs {len(bits)} bits, holds {carrier.size}.")
            
        stego = carrier.copy()
        flat_pixels = stego.flatten()
        
        # Seed PRNG with the image shape to ensure deterministic scattering
        # (Since shape doesn't change after embedding)
        np.random.seed(carrier.size)
        indices = np.random.permutation(carrier.size)
        
        for i, bit in enumerate(bits):
            idx = indices[i]
            flat_pixels[idx] = (flat_pixels[idx] & 0b11111110) | int(bit)
            
        return flat_pixels.reshape(carrier.shape)

    def extract(self, stego: np.ndarray) -> bytes:
        flat_pixels = stego.flatten()
        
        np.random.seed(stego.size)
        indices = np.random.permutation(stego.size)
        
        def read_bits(offset: int, count: int) -> str:
            return "".join(str(flat_pixels[indices[offset + i]] & 1) for i in range(count))

        if len(flat_pixels) < 32:
            raise ValueError("Image too small.")

        length_bits = read_bits(0, 32)
        payload_len = struct.unpack(">I", bytes([int(length_bits[i:i+8], 2) for i in range(0, 32, 8)]))[0]
        
        if 32 + payload_len * 8 > len(flat_pixels):
            raise ValueError("Invalid length header.")

        payload_bits = read_bits(32, payload_len * 8)
        payload_bytes = bytes([int(payload_bits[i:i+8], 2) for i in range(0, len(payload_bits), 8)])
        
        return payload_bytes
