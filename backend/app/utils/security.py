"""
Enterprise Security Utilities for Argon2id Password Hashing, JWT Key Rotation,
CSRF Protection, and Credential Sanitization.
Strictly prevents logging sensitive tokens or passwords.
"""

import hmac
import hashlib
import base64
import json
import time
import uuid
import re
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta

try:
    import argon2
    # OWASP RFC 9106 recommended parameters: 19 MiB RAM, 2 iterations, 1 lane.
    # Single thread execution eliminates CPU thread contention with real-time YOLO AI pipelines.
    _argon2_ph = argon2.PasswordHasher(
        time_cost=2,
        memory_cost=19456,
        parallelism=1,
        hash_len=32,
        salt_len=16
    )
    _argon2_ph_test = argon2.PasswordHasher(
        time_cost=1,
        memory_cost=8,
        parallelism=1,
        hash_len=16,
        salt_len=8
    )
except ImportError:
    _argon2_ph = None
    _argon2_ph_test = None

from app.config.settings import settings
from app.utils.logger import logger


# JWT Signing Key Registry (Supports Key Rotation with 'kid' header tracking)
JWT_KEY_REGISTRY: Dict[str, str] = {
    "key-2026-v1": getattr(settings, "SECRET_KEY", "development-secret-key-change-in-production")
}
ACTIVE_KID: str = "key-2026-v1"

JWT_ISSUER: str = "ai_cctv_monitor"
JWT_AUDIENCE: str = "ai_cctv_client"


# -----------------------------------------------------------------------------
# Password Hashing (Argon2id with Legacy SHA256 Fallback)
# -----------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """
    Hashes plain text password using Argon2id algorithm.
    Falls back to HMAC-SHA256 if argon2-cffi is not available.
    """
    if settings.APP_ENV == "testing" and _argon2_ph_test is not None:
        return _argon2_ph_test.hash(password)
    if _argon2_ph is not None:
        return _argon2_ph.hash(password)
    
    # Legacy SHA256 fallback
    secret = settings.SECRET_KEY.encode("utf-8")
    pwd = password.encode("utf-8")
    hashed = hmac.new(secret, pwd, hashlib.sha256).hexdigest()
    return f"sha256${hashed}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies plain text password against stored hash (Argon2id or legacy SHA256).
    Returns True if valid.
    """
    if not hashed_password:
        return False

    # 1. Argon2id Hash Format ($argon2id$...)
    if hashed_password.startswith("$argon2"):
        ph = _argon2_ph_test if (settings.APP_ENV == "testing" and _argon2_ph_test is not None) else _argon2_ph
        if ph is None:
            logger.error("Security: argon2-cffi package is missing while attempting to verify Argon2id hash.")
            return False
        try:
            ph.verify(hashed_password, plain_password)
            return True
        except argon2.exceptions.VerifyMismatchError:
            if ph is _argon2_ph_test and _argon2_ph is not None:
                try:
                    _argon2_ph.verify(hashed_password, plain_password)
                    return True
                except Exception:
                    pass
            return False
        except Exception as e:
            logger.warning(f"Security: Argon2id verification error: {str(e)}")
            return False

    # 2. Legacy SHA256 Format (sha256$...)
    if hashed_password.startswith("sha256$"):
        secret = settings.SECRET_KEY.encode("utf-8")
        pwd = plain_password.encode("utf-8")
        expected_hash = f"sha256${hmac.new(secret, pwd, hashlib.sha256).hexdigest()}"
        return hmac.compare_digest(expected_hash, hashed_password)

    return False


def needs_rehash(hashed_password: str) -> bool:
    """
    Checks if password hash uses legacy algorithm and needs re-hashing to Argon2id.
    """
    if _argon2_ph is None:
        return False
    if not hashed_password.startswith("$argon2"):
        return True
    try:
        return _argon2_ph.check_needs_rehash(hashed_password)
    except Exception:
        return False


# -----------------------------------------------------------------------------
# JWT Tokens (Signing Key Rotation, Issuer/Audience, Token Types)
# -----------------------------------------------------------------------------

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates short-lived JWT Access Token (type='access').
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=30))
    to_encode.update({
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "jti": str(uuid.uuid4()),
        "type": "access"
    })

    return _encode_jwt(to_encode, kid=ACTIVE_KID)


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> Tuple[str, str]:
    """
    Creates long-lived JWT Refresh Token (type='refresh').
    Returns tuple: (signed_token_string, jti_token_id).
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=7))
    token_jti = str(uuid.uuid4())
    to_encode.update({
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "jti": token_jti,
        "type": "refresh"
    })

    signed_token = _encode_jwt(to_encode, kid=ACTIVE_KID)
    return signed_token, token_jti


def decode_jwt_token(token: str, expected_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    Decodes and verifies JWT Token payload:
    - Validates signature using key ID (kid) from header
    - Checks issuer ('iss'), audience ('aud'), expiration ('exp'), and token 'type'
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, sig_b64 = parts

        # 1. Decode Header & extract key ID (kid)
        padding = "=" * (4 - len(header_b64) % 4)
        header_bytes = base64.urlsafe_b64decode(header_b64 + padding)
        header = json.loads(header_bytes.decode("utf-8"))

        kid = header.get("kid", ACTIVE_KID)
        secret_key = JWT_KEY_REGISTRY.get(kid)
        if not secret_key:
            logger.warning(f"Security: JWT signing key ID '{kid}' not found in registry.")
            return None

        # 2. Verify HMAC-SHA256 Signature
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).rstrip(b"=").decode("utf-8")

        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            logger.warning("Security: JWT Signature verification failed.")
            return None

        # 3. Decode Payload
        padding = "=" * (4 - len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # 4. Check Claims (iss, aud, exp, type)
        exp = payload.get("exp")
        if exp and int(time.time()) > exp:
            logger.warning("Security: JWT Token has expired.")
            return None

        if payload.get("iss") != JWT_ISSUER:
            logger.warning(f"Security: JWT Invalid Issuer '{payload.get('iss')}'. Expected '{JWT_ISSUER}'.")
            return None

        if payload.get("aud") != JWT_AUDIENCE:
            logger.warning(f"Security: JWT Invalid Audience '{payload.get('aud')}'. Expected '{JWT_AUDIENCE}'.")
            return None

        if payload.get("type") != expected_type:
            logger.warning(f"Security: JWT Token type mismatch '{payload.get('type')}'. Expected '{expected_type}'.")
            return None

        return payload

    except Exception as e:
        logger.warning(f"Security: Failed decoding JWT token: {str(e)}")
        return None


# Legacy wrappers for backward compatibility with earlier endpoint tests
create_access_token_legacy = create_access_token

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    return decode_jwt_token(token, expected_type="access")


def hash_token(token: str) -> str:
    """
    Computes SHA256 hex digest of token string for DB indexing & comparison.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _encode_jwt(payload: Dict[str, Any], kid: str) -> str:
    header = {"alg": "HS256", "typ": "JWT", "kid": kid}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode("utf-8")).rstrip(b"=").decode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).rstrip(b"=").decode("utf-8")
    
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    secret_key = JWT_KEY_REGISTRY.get(kid, settings.SECRET_KEY)
    signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("utf-8")

    return f"{header_b64}.{payload_b64}.{sig_b64}"


# -----------------------------------------------------------------------------
# CSRF Token Protection
# -----------------------------------------------------------------------------

def generate_csrf_token() -> str:
    """
    Generates a cryptographically secure random CSRF token.
    """
    return uuid.uuid4().hex + uuid.uuid4().hex


def verify_csrf_token(header_token: Optional[str], cookie_token: Optional[str]) -> bool:
    """
    Validates CSRF double-submit token pattern.
    Header token 'X-CSRF-Token' must match Cookie token 'csrf_token'.
    """
    if not header_token or not cookie_token:
        return False
    return hmac.compare_digest(header_token, cookie_token)


# -----------------------------------------------------------------------------
# Credential & Token Sanitization (Zero Logging Leakage Rule)
# -----------------------------------------------------------------------------

def sanitize_rtsp_url(url: str) -> str:
    """
    Sanitizes raw RTSP stream credentials in log files and API payloads.
    Replaces credentials with '***:***' (e.g. 'rtsp://***:***@192.168.1.50:554/live').
    """
    if not url or "rtsp://" not in url.lower():
        return url
    return re.sub(r"rtsp://[^:@]+:[^@]+@", "rtsp://***:***@", url, flags=re.IGNORECASE)


def sanitize_dict_for_logging(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively strips passwords, access tokens, refresh tokens, and RTSP credentials
    from payload dictionaries before writing to logs.
    """
    SENSITIVE_KEYS = {"password", "plain_password", "hashed_password", "access_token", "refresh_token", "secret", "token"}
    sanitized = {}
    for k, v in data.items():
        if k.lower() in SENSITIVE_KEYS:
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_dict_for_logging(v)
        elif isinstance(v, str) and "rtsp://" in v.lower():
            sanitized[k] = sanitize_rtsp_url(v)
        else:
            sanitized[k] = v
    return sanitized
