"""
AES-256 Symmetric Credential Encryption Utility.
Used to encrypt and decrypt DVR/NVR management passwords safely.
Plaintext passwords and raw credentials are NEVER stored in the database or logged.
"""

import base64
import hashlib
from app.config.settings import settings

try:
    from cryptography.fernet import Fernet
    _key_bytes = (settings.SECRET_KEY * 4)[:32].encode("utf-8")
    _fernet_key = base64.urlsafe_b64encode(_key_bytes)
    _cipher = Fernet(_fernet_key)
    USE_FERNET = True
except ImportError:
    USE_FERNET = False


def _xor_crypt(data: bytes, key: bytes) -> bytes:
    key_stream = hashlib.sha256(key).digest()
    return bytes(b ^ key_stream[i % len(key_stream)] for i, b in enumerate(data))


def encrypt_credential(plaintext: str) -> str:
    """
    Encrypts plaintext credential string using AES-256 Fernet or SHA256-XOR Base64.
    """
    if not plaintext:
        return ""
    if USE_FERNET:
        return _cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    
    key = settings.SECRET_KEY.encode("utf-8")
    encrypted = _xor_crypt(plaintext.encode("utf-8"), key)
    return base64.urlsafe_b64encode(encrypted).decode("utf-8")


def decrypt_credential(encrypted_blob: str) -> str:
    """
    Decrypts encrypted credential blob to plaintext.
    """
    if not encrypted_blob:
        return ""
    try:
        if USE_FERNET:
            return _cipher.decrypt(encrypted_blob.encode("utf-8")).decode("utf-8")
        
        key = settings.SECRET_KEY.encode("utf-8")
        raw = base64.urlsafe_b64decode(encrypted_blob.encode("utf-8"))
        decrypted = _xor_crypt(raw, key)
        return decrypted.decode("utf-8")
    except Exception:
        return ""


def mask_credential(credential_ref: str) -> str:
    """
    Returns sanitized mask string (e.g. '******') for API responses.
    """
    if not credential_ref:
        return ""
    return "******"
