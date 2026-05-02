"""
crypto_utils.py  —  Advanced Cryptographic Primitives
"""

import os
from Crypto.Cipher import AES, ChaCha20
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import PBKDF2, scrypt
from Crypto.Util.Padding import pad, unpad

def derive_key(password: str, kdf: str, iterations: int, salt: bytes = b"StegoCrypt_Salt_123") -> bytes:
    """Derive a 32-byte (256-bit) key using the specified KDF."""
    # PyCryptodome's KDFs default to latin-1 if passed a string. We must force UTF-8.
    password_bytes = password.encode('utf-8')
    
    if kdf == "pbkdf2":
        return PBKDF2(password_bytes, salt, dkLen=32, count=iterations, hmac_hash_module=SHA256)
    elif kdf == "scrypt":
        # Map iterations to scrypt N parameter (CPU/Memory cost factor)
        if iterations >= 1000000:
            n_factor = 2**16
        elif iterations >= 500000:
            n_factor = 2**15
        else:
            n_factor = 2**14
            
        return scrypt(password_bytes, salt, key_len=32, N=n_factor, r=8, p=1)
    else:
        # Fallback to simple SHA256 (not recommended, but supported for legacy)
        hasher = SHA256.new(password_bytes)
        return hasher.digest()

def get_random_bytes(length: int) -> bytes:
    return os.urandom(length)

def encrypt_message(message, password: str, encryption="aes_cbc", kdf="pbkdf2", iterations=100000) -> bytes:
    """Encrypts a message (str or bytes) using selected advanced cipher."""
    salt = get_random_bytes(16)
    key = derive_key(password, kdf, iterations, salt)
    
    if isinstance(message, str):
        message_bytes = message.encode('utf-8')
    else:
        message_bytes = message
        
    if encryption == "aes_cbc":
        iv = get_random_bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        ciphertext = cipher.encrypt(pad(message_bytes, AES.block_size))
        return b"CBC" + salt + iv + ciphertext
        
    elif encryption == "aes_gcm":
        nonce = get_random_bytes(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(message_bytes) # GCM doesn't need padding
        return b"GCM" + salt + nonce + tag + ciphertext
        
    elif encryption == "chacha20":
        nonce = get_random_bytes(8)
        cipher = ChaCha20.new(key=key, nonce=nonce)
        ciphertext = cipher.encrypt(message_bytes) # Stream cipher, no padding
        return b"CHA" + salt + nonce + ciphertext
        
    raise ValueError(f"Unknown encryption algorithm: {encryption}")

def decrypt_message(encrypted_data: bytes, password: str, kdf="pbkdf2", iterations=100000) -> bytes:
    """Decrypts data using the automatically detected cipher."""
    if len(encrypted_data) < 20:
        raise ValueError("Invalid encrypted data (too short).")

    cipher_type = encrypted_data[:3]
    salt = encrypted_data[3:19]
    key = derive_key(password, kdf, iterations, salt)
    
    try:
        if cipher_type == b"CBC":
            iv = encrypted_data[19:35]
            ciphertext = encrypted_data[35:]
            cipher = AES.new(key, AES.MODE_CBC, iv)
            padded_message = cipher.decrypt(ciphertext)
            return unpad(padded_message, AES.block_size)
            
        elif cipher_type == b"GCM":
            nonce = encrypted_data[19:31]
            tag = encrypted_data[31:47]
            ciphertext = encrypted_data[47:]
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            return cipher.decrypt_and_verify(ciphertext, tag)
            
        elif cipher_type == b"CHA":
            nonce = encrypted_data[19:27]
            ciphertext = encrypted_data[27:]
            cipher = ChaCha20.new(key=key, nonce=nonce)
            return cipher.decrypt(ciphertext)
            
        else:
            raise ValueError("Corrupted data or unknown cipher type.")
            
    except Exception as e:
        raise ValueError(f"Decryption failed. Exact Error: {type(e).__name__} - {str(e)}")
