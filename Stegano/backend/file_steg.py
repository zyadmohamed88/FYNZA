"""
file_steg.py — Generic Binary File Steganography
Hides an encrypted payload inside ANY binary file by appending it
with a magic marker. The host file remains fully functional.

Structure appended at end of host file:
  [FYNZA_MAGIC 8 bytes][payload_len 4 bytes BE][payload bytes]
"""

import struct

# MAGIC = b"\xFY\xNZ\xA0\xFF\x53\x54\x47\x21"  # FYNZA_STG!
# Fix: use proper bytes
MAGIC = bytes([0xF0, 0xEE, 0xAB, 0xFF, 0x53, 0x54, 0x47, 0x21])
MAGIC_LEN = len(MAGIC)


def get_file_capacity(host_path: str) -> int:
    """
    For generic files, capacity is effectively unlimited
    (we just append data). Return a large nominal capacity.
    """
    import os
    host_size = os.path.getsize(host_path)
    # Report capacity as 10x the host file size (practical limit)
    return host_size * 10


def embed_in_file(host_path: str, payload: bytes) -> bytes:
    """
    Embed payload into any binary file by appending after host content.
    Returns the modified file bytes.
    """
    with open(host_path, "rb") as f:
        host_data = f.read()

    length_header = struct.pack(">I", len(payload))
    result = host_data + MAGIC + length_header + payload
    return result


def extract_from_file(stego_path: str) -> bytes:
    """
    Extract payload from a stego file produced by embed_in_file.
    Searches for the magic marker from the end of the file.
    """
    with open(stego_path, "rb") as f:
        data = f.read()

    idx = data.rfind(MAGIC)
    if idx == -1:
        raise ValueError("No hidden payload found in this file — wrong file or no data was embedded.")

    offset = idx + MAGIC_LEN
    if offset + 4 > len(data):
        raise ValueError("File is corrupted — payload header missing.")

    payload_len = struct.unpack(">I", data[offset: offset + 4])[0]
    payload_start = offset + 4

    if payload_start + payload_len > len(data):
        raise ValueError(f"File is corrupted — expected {payload_len} bytes but only {len(data) - payload_start} available.")

    return data[payload_start: payload_start + payload_len]


def get_file_info(host_path: str) -> dict:
    """Return human-readable info about a generic file."""
    import os, mimetypes
    size = os.path.getsize(host_path)
    mime, _ = mimetypes.guess_type(host_path)
    return {
        "filename": os.path.basename(host_path),
        "size_bytes": size,
        "mime_type": mime or "application/octet-stream",
        "extension": os.path.splitext(host_path)[1].lower(),
        "capacity_bytes": get_file_capacity(host_path),
    }
