"""
audio_steg.py — WAV Audio Steganography (LSB on samples)
Supports hiding any binary payload inside a WAV audio file.
"""

import io
import struct
import wave
import numpy as np


DELIMITER_MAGIC = b"\xDE\xAD\xBE\xEF"


def get_wav_capacity(wav_path: str) -> int:
    """Return max bytes that can be embedded in this WAV file."""
    with wave.open(wav_path, "rb") as wf:
        n_frames = wf.getnframes()
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
    # Use only the LSB of each 16-bit sample (2 bytes per sample)
    # We treat each sample byte as 1 bit storage
    total_samples = n_frames * n_channels
    return total_samples // 8


def embed_in_wav(wav_path: str, payload: bytes) -> bytes:
    """
    Hide payload bytes in a WAV file via LSB of samples.
    Returns the modified WAV as raw bytes.
    """
    with wave.open(wav_path, "rb") as wf:
        params = wf.getparams()
        frames = bytearray(wf.readframes(wf.getnframes()))

    # Header: 4 bytes length + payload
    full_payload = struct.pack(">I", len(payload)) + payload
    required_bits = len(full_payload) * 8

    if required_bits > len(frames):
        raise ValueError(
            f"Audio too short! Need {required_bits} bits, have {len(frames)} bits available."
        )

    # Embed bits into LSBs of sample bytes
    bit_idx = 0
    for byte_val in full_payload:
        for bit_pos in range(7, -1, -1):
            bit = (byte_val >> bit_pos) & 1
            frames[bit_idx] = (frames[bit_idx] & 0xFE) | bit
            bit_idx += 1

    # Write to buffer
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf_out:
        wf_out.setparams(params)
        wf_out.writeframes(bytes(frames))
    return buf.getvalue()


def extract_from_wav(wav_path: str) -> bytes:
    """
    Extract hidden payload from a stego WAV file.
    Returns the raw payload bytes.
    """
    with wave.open(wav_path, "rb") as wf:
        frames = bytearray(wf.readframes(wf.getnframes()))

    def read_bytes(offset_bits: int, count_bytes: int) -> bytes:
        result = bytearray(count_bytes)
        for i in range(count_bytes):
            byte_val = 0
            for bit_pos in range(7, -1, -1):
                idx = offset_bits + i * 8 + (7 - bit_pos)
                bit = frames[idx] & 1
                byte_val = (byte_val << 1) | bit
            result[i] = byte_val
        return bytes(result)

    # Read 4-byte length header
    length_bytes = read_bytes(0, 4)
    payload_len = struct.unpack(">I", length_bytes)[0]

    if payload_len == 0 or payload_len * 8 + 32 > len(frames):
        raise ValueError("Invalid length header — no hidden data or corrupted audio.")

    # Read payload
    payload = read_bytes(32, payload_len)
    return payload


def get_wav_info(wav_path: str) -> dict:
    """Return human-readable info about a WAV file."""
    with wave.open(wav_path, "rb") as wf:
        return {
            "channels": wf.getnchannels(),
            "sample_rate_hz": wf.getframerate(),
            "sample_width_bytes": wf.getsampwidth(),
            "n_frames": wf.getnframes(),
            "duration_seconds": round(wf.getnframes() / wf.getframerate(), 2),
            "capacity_bytes": get_wav_capacity(wav_path),
        }
