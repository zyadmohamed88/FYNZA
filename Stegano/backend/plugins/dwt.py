import struct
import numpy as np
from plugin_manager import SteganographyPlugin

class SimpleDWT(SteganographyPlugin):

    @property
    def name(self):
        return "DWT"

    @property
    def description(self):
        return "Very simple and stable DWT using LSB on HH band"

    # ======================
    # Haar DWT
    # ======================
    def haar_2d(self, img):
        img = img.astype(np.float32)
        L = (img[:, 0::2] + img[:, 1::2]) / 2
        H = (img[:, 0::2] - img[:, 1::2]) / 2

        LL = (L[0::2] + L[1::2]) / 2
        LH = (L[0::2] - L[1::2]) / 2
        HL = (H[0::2] + H[1::2]) / 2
        HH = (H[0::2] - H[1::2]) / 2

        return LL, LH, HL, HH

    def ihaar_2d(self, LL, LH, HL, HH):
        h, w = LL.shape[0]*2, LL.shape[1]*2

        L = np.zeros((h, w//2))
        H = np.zeros((h, w//2))

        L[0::2] = LL + LH
        L[1::2] = LL - LH
        H[0::2] = HL + HH
        H[1::2] = HL - HH

        img = np.zeros((h, w))
        img[:, 0::2] = L + H
        img[:, 1::2] = L - H

        return img

    # ======================
    # Capacity
    # ======================
    def get_capacity(self, image):
        h, w = image.shape[:2]
        channels = 1 if len(image.shape) == 2 else image.shape[2]
        return (h//2 * w//2 * channels) // 8

    # ======================
    # Embed
    # ======================
    def embed(self, carrier, payload):

        payload = struct.pack(">I", len(payload)) + payload
        bits = "".join(format(b, "08b") for b in payload)

        h, w = carrier.shape[:2]
        carrier = carrier[:h//2*2, :w//2*2]
        
        channels = 1 if len(carrier.shape) == 2 else carrier.shape[2]
        stego = carrier.copy()
        
        bit_idx = 0

        for c in range(channels):
            if channels == 1:
                channel_data = carrier
            else:
                channel_data = carrier[:, :, c]

            LL, LH, HL, HH = self.haar_2d(channel_data)

            flat = HH.flatten()

            for i in range(len(flat)):
                if bit_idx >= len(bits):
                    break
                
                val = int(round(flat[i]))

                # LSB embedding
                if (val % 2) != int(bits[bit_idx]):
                    if val % 2 == 0:
                        val += 1
                    else:
                        val -= 1

                flat[i] = val
                bit_idx += 1

            HH = flat.reshape(HH.shape)

            channel_stego = self.ihaar_2d(LL, LH, HL, HH)
            
            if channels == 1:
                stego[:, :] = channel_stego
            else:
                stego[:, :, c] = channel_stego
                
            if bit_idx >= len(bits):
                break

        if bit_idx < len(bits):
            raise ValueError("Payload too large")

        return np.clip(np.round(stego), 0, 255).astype(np.uint8)

    # ======================
    # Extract
    # ======================
    def extract(self, stego):

        h, w = stego.shape[:2]
        stego = stego[:h//2*2, :w//2*2]
        channels = 1 if len(stego.shape) == 2 else stego.shape[2]

        bits = []

        for c in range(channels):
            if channels == 1:
                channel_data = stego
            else:
                channel_data = stego[:, :, c]

            _, _, _, HH = self.haar_2d(channel_data)

            flat = HH.flatten()

            for val in flat:
                bits.append(str(int(round(val)) % 2))

        bits = "".join(bits)

        # header (32 bit)
        if len(bits) < 32:
            raise ValueError("Invalid DWT length header.")
            
        length = int(bits[:32], 2)

        if 32 + length*8 > len(bits):
            raise ValueError("Invalid DWT length header.")

        data_bits = bits[32:32 + length*8]

        data = bytes(int(data_bits[i:i+8], 2)
                     for i in range(0, len(data_bits), 8))

        return data