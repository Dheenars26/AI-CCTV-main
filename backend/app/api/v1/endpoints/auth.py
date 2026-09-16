"""
Production Authentication & User Profile REST API Endpoints (/api/v1/auth).
Implements Argon2id verification, Refresh Token Rotation, Theft Reuse Detection,
HttpOnly Cookies, CSRF Double-Submit Protection, and Single-Use WebSocket Tickets.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Request, Response, Header, Cookie, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas.common import ResponseModel
from app.schemas.auth import (
    LoginRequest, RefreshTokenRequest, TokenResponse, UserResponse, UserCreate, UserProfileUpdate, WSTicketResponse
)
from app.utils.security import (
    hash_password, verify_password, needs_rehash, create_access_token, create_refresh_token,
    decode_jwt_token, hash_token, generate_csrf_token, verify_csrf_token
)
from app.utils.exceptions import AppException
from app.services.audit_service import AuditService
from app.services.ws_ticket_service import ws_ticket_service
from app.api.v1.dependencies.permissions import get_current_user, RequireRole
from app.utils.logger import logger

router = APIRouter(prefix="/auth", tags=["Authentication & Security"])


@router.post(
    "/token",
    summary="OAuth2 Password Token Endpoint (Swagger UI)",
    description="Authenticates form data credentials for direct Swagger UI Authorization."
)
def login_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        (User.username == form_data.username) | (User.email == form_data.username)
    ).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    family_id = str(uuid.uuid4())
    token_claims = {"sub": user.id, "username": user.username, "role": user.role, "family_id": family_id}
    access_token = create_access_token(data=token_claims)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.post(
    "/login",
    response_model=ResponseModel[TokenResponse],
    summary="User Login (JWT Token & HttpOnly Cookie Issuance)",
    description="Authenticates credentials. Sets HttpOnly Secure refresh token cookie and returns Bearer access token + CSRF token."
)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent")

    # 1. Lookup User
    user = db.query(User).filter(
        (User.username == payload.username) | (User.email == payload.username)
    ).first()

    if not user:
        AuditService.log_event(
            db=db, event_type="LOGIN_FAILED", username=payload.username, ip_address=client_ip,
            user_agent=user_agent, status="FAILED", details={"reason": "User not found"}
        )
        raise AppException(
            message="Invalid username or password.",
            code="INVALID_CREDENTIALS",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # 2. Check Account Lockout
    if user.is_locked:
        AuditService.log_event(
            db=db, event_type="LOGIN_BLOCKED_LOCKED", actor_id=user.id, username=user.username,
            ip_address=client_ip, status="FAILED", details={"locked_until": user.locked_until.isoformat()}
        )
        raise AppException(
            message="Account is temporarily locked due to repeated failed login attempts. Try again later.",
            code="ACCOUNT_LOCKED",
            status_code=status.HTTP_403_FORBIDDEN
        )

    if not user.is_active:
        raise AppException(
            message="Account is deactivated. Contact system administrator.",
            code="ACCOUNT_DEACTIVATED",
            status_code=status.HTTP_403_FORBIDDEN
        )

    # 3. Verify Password
    if not verify_password(payload.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            AuditService.log_event(
                db=db, event_type="ACCOUNT_LOCKED", actor_id=user.id, username=user.username,
                ip_address=client_ip, status="DENIED", details={"failed_attempts": user.failed_login_attempts}
            )
        db.commit()

        AuditService.log_event(
            db=db, event_type="LOGIN_FAILED", actor_id=user.id, username=user.username,
            ip_address=client_ip, user_agent=user_agent, status="FAILED",
            details={"failed_attempts": user.failed_login_attempts}
        )
        raise AppException(
            message="Invalid username or password.",
            code="INVALID_CREDENTIALS",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # Reset failed attempts on success
    user.failed_login_attempts = 0
    user.locked_until = None

    # Transparent Argon2id Re-hash upgrade if using legacy hash format
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(payload.password)
        logger.info(f"Security: Transparently upgraded password hash for User '{user.username}' to Argon2id.")

    # 4. Generate Tokens (Access Token + Refresh Token with Family ID)
    family_id = str(uuid.uuid4())
    token_claims = {"sub": user.id, "username": user.username, "role": user.role, "family_id": family_id}

    access_token = create_access_token(data=token_claims)
    refresh_token_str, token_jti = create_refresh_token(data=token_claims)

    # Store Refresh Token Entry in DB
    ref_hash = hash_token(refresh_token_str)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    db_ref_token = RefreshToken(
        id=token_jti,
        family_id=family_id,
        user_id=user.id,
        token_hash=ref_hash,
        expires_at=expires_at,
        is_revoked=False
    )
    db.add(db_ref_token)
    db.commit()

    # 5. Generate CSRF Double-Submit Token
    csrf_token = generate_csrf_token()

    # 6. Set HttpOnly Secure Cookies
    is_https = request.url.scheme == "https" or request.headers.get("X-Forwarded-Proto") == "https"
    response.set_cookie(
        key="refreshToken",
        value=refresh_token_str,
        httponly=True,
        secure=is_https,
        samesite="lax",
        max_age=7 * 86400,
        path="/api/v1/auth"
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=is_https,
        samesite="lax",
        max_age=7 * 86400,
        path="/"
    )

    AuditService.log_event(
        db=db, event_type="LOGIN_SUCCESS", actor_id=user.id, username=user.username,
        ip_address=client_ip, user_agent=user_agent, status="SUCCESS"
    )

    user_resp = UserResponse.model_validate(user)
    token_resp = TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=1800,
        csrf_token=csrf_token,
        user=user_resp
    )
    return ResponseModel(data=token_resp)


@router.post(
    "/refresh",
    response_model=ResponseModel[TokenResponse],
    summary="Rotate Refresh Token & Issue New Access Token",
    description="Implements Refresh Token Rotation and Reuse Theft Detection. Revokes token family on reuse."
)
def refresh_tokens(
    request: Request,
    response: Response,
    payload: Optional[RefreshTokenRequest] = None,
    refreshToken_cookie: Optional[str] = Cookie(None, alias="refreshToken"),
    csrf_cookie: Optional[str] = Cookie(None, alias="csrf_token"),
    x_csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db)
):
    client_ip = request.client.host if request.client else "unknown"

    raw_refresh_token = (refreshToken_cookie or (payload.refresh_token if payload else None))
    if not raw_refresh_token:
        raise AppException(
            message="Refresh token missing from cookie or request body.",
            code="MISSING_REFRESH_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # Validate CSRF Token if using cookie authentication
    if refreshToken_cookie and not verify_csrf_token(x_csrf_token, csrf_cookie):
        AuditService.log_event(
            db=db, event_type="CSRF_VERIFICATION_FAILED", ip_address=client_ip, status="DENIED"
        )
        raise AppException(
            message="CSRF validation failed. Missing or mismatched X-CSRF-Token header.",
            code="CSRF_FAILED",
            status_code=status.HTTP_403_FORBIDDEN
        )

    # Decode refresh token
    decoded = decode_jwt_token(raw_refresh_token, expected_type="refresh")
    if not decoded or "sub" not in decoded:
        raise AppException(
            message="Invalid or expired refresh token.",
            code="INVALID_REFRESH_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    ref_hash = hash_token(raw_refresh_token)
    db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == ref_hash).first()

    # REUSE DETECTION & THEFT MITIGATION
    # If token entry is missing or ALREADY REVOKED, a token theft reuse attack is detected!
    if not db_token or db_token.is_revoked:
        family_id = decoded.get("family_id") or (db_token.family_id if db_token else None)
        if family_id:
            # Revoke ALL tokens in this family immediately!
            db.query(RefreshToken).filter(RefreshToken.family_id == family_id).update({"is_revoked": True})
            db.commit()

        AuditService.log_event(
            db=db, event_type="TOKEN_REUSE_DETECTED", actor_id=decoded.get("sub"),
            username=decoded.get("username"), ip_address=client_ip, status="DENIED",
            details={"family_id": family_id, "warning": "Attempted reuse of revoked refresh token. Revoked full token family."}
        )
        raise AppException(
            message="Security breach detected (revoked token reuse). Session revoked.",
            code="TOKEN_THEFT_DETECTED",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user or not user.is_active or user.is_locked:
        raise AppException(
            message="User account inactive or locked.",
            code="ACCOUNT_INACTIVE",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # ROTATION: Revoke current refresh token
    db_token.is_revoked = True

    # Issue NEW Access Token and NEW Refresh Token within same family
    token_claims = {"sub": user.id, "username": user.username, "role": user.role, "family_id": db_token.family_id}
    new_access_token = create_access_token(data=token_claims)
    new_refresh_str, new_token_jti = create_refresh_token(data=token_claims)

    new_ref_hash = hash_token(new_refresh_str)
    new_db_token = RefreshToken(
        id=new_token_jti,
        family_id=db_token.family_id,
        user_id=user.id,
        token_hash=new_ref_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        is_revoked=False
    )
    db.add(new_db_token)
    db_token.replaced_by_id = new_token_jti
    db.commit()

    csrf_token = generate_csrf_token()

    is_https = request.url.scheme == "https" or request.headers.get("X-Forwarded-Proto") == "https"
    response.set_cookie(
        key="refreshToken", value=new_refresh_str, httponly=True, secure=is_https,
        samesite="lax", max_age=7 * 86400, path="/api/v1/auth"
    )
    response.set_cookie(
        key="csrf_token", value=csrf_token, httponly=False, secure=is_https,
        samesite="lax", max_age=7 * 86400, path="/"
    )

    AuditService.log_event(
        db=db, event_type="TOKEN_REFRESH", actor_id=user.id, username=user.username,
        ip_address=client_ip, status="SUCCESS"
    )

    user_resp = UserResponse.model_validate(user)
    token_resp = TokenResponse(
        access_token=new_access_token, token_type="bearer", expires_in=1800,
        csrf_token=csrf_token, user=user_resp
    )
    return ResponseModel(data=token_resp)


@router.post(
    "/logout",
    response_model=ResponseModel[dict],
    summary="User Logout",
    description="Revokes active refresh token and clears authentication cookies."
)
def logout(
    request: Request,
    response: Response,
    refreshToken_cookie: Optional[str] = Cookie(None, alias="refreshToken"),
    db: Session = Depends(get_db)
):
    client_ip = request.client.host if request.client else "unknown"

    if refreshToken_cookie:
        ref_hash = hash_token(refreshToken_cookie)
        db.query(RefreshToken).filter(RefreshToken.token_hash == ref_hash).update({"is_revoked": True})
        db.commit()

    response.delete_cookie(key="refreshToken", path="/api/v1/auth")
    response.delete_cookie(key="csrf_token", path="/")

    AuditService.log_event(
        db=db, event_type="LOGOUT", ip_address=client_ip, status="SUCCESS"
    )
    return ResponseModel(data={"message": "Logged out successfully."})


@router.post(
    "/ws-ticket",
    response_model=ResponseModel[WSTicketResponse],
    summary="Issue Ephemeral Single-Use WebSocket Ticket",
    description="Returns a 10-second single-use handshake ticket for secure WebSocket connection without query string tokens."
)
def issue_ws_ticket(current_user: User = Depends(get_current_user)):
    ticket = ws_ticket_service.issue_ticket(
        user_id=current_user.id, username=current_user.username, role=current_user.role
    )
    return ResponseModel(data=WSTicketResponse(ticket=ticket, expires_in=10))


@router.get(
    "/me",
    response_model=ResponseModel[UserResponse],
    summary="Get Current User Profile",
    description="Returns authenticated user details."
)
def get_my_profile(current_user: User = Depends(get_current_user)):
    return ResponseModel(data=UserResponse.model_validate(current_user))


@router.put(
    "/me",
    response_model=ResponseModel[UserResponse],
    summary="Update Current User Profile",
    description="Updates authenticated user email and full name."
)
def update_my_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if payload.email is not None and payload.email.strip():
        new_email = payload.email.strip().lower()
        existing = db.query(User).filter(User.email == new_email, User.id != current_user.id).first()
        if existing:
            raise AppException(message="Email address is already in use.", code="EMAIL_IN_USE", status_code=400)
        current_user.email = new_email
    if payload.full_name is not None and payload.full_name.strip():
        current_user.full_name = payload.full_name.strip()
    db.commit()
    db.refresh(current_user)
    return ResponseModel(data=UserResponse.model_validate(current_user))


@router.post(
    "/register",
    response_model=ResponseModel[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register New User Account (ADMIN Only)",
    description="Creates a new system user account. Restricted to ADMIN permission."
)
def register_user(
    payload: UserCreate,
    current_user: User = Depends(RequireRole(["ADMIN"])),
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(
        (User.username == payload.username) | (User.email == payload.email)
    ).first()
    if existing:
        raise AppException(
            message="Username or email already registered.",
            code="USER_EXISTS",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role.upper()
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    AuditService.log_event(
        db=db, event_type="USER_CREATED", actor_id=current_user.id, username=current_user.username,
        status="SUCCESS", details={"new_username": user.username, "new_role": user.role}
    )

    return ResponseModel(data=UserResponse.model_validate(user))
