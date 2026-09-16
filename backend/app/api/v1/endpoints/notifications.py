"""
Notification Delivery Audit Log REST API Endpoints (/api/v1/notifications).
"""

import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.session import get_db
from app.models.notification import Notification
from app.schemas.common import ResponseModel, PaginatedResponseModel, PaginationMeta
from app.schemas.notification import NotificationResponse, NotificationSettingsResponse, NotificationSettingsUpdate
from app.config.settings import settings

from app.api.v1.dependencies.permissions import RequirePermission
from app.models.user import User
from app.utils.exceptions import AppException

router = APIRouter(prefix="/notifications", tags=["Notifications & Email Audit Logs"])


@router.get(
    "/settings",
    response_model=ResponseModel[NotificationSettingsResponse],
    summary="Get Alert Email Notification Settings",
    description="Retrieves current recipient email addresses, email alerts status, and cooldown suppression settings."
)
async def get_notification_settings(
    current_user: User = Depends(RequirePermission("notifications:read"))
):
    recipients = settings.ALERT_RECIPIENT_EMAILS
    if isinstance(recipients, str):
        recipients = [r.strip() for r in recipients.split(",") if r.strip()]

    from app.alerts.email_service import EmailService
    svc = EmailService()
    has_pwd = bool(settings.SMTP_PASSWORD and settings.SMTP_PASSWORD.strip())

    data = NotificationSettingsResponse(
        recipient_emails=recipients,
        email_alerts_enabled=settings.EMAIL_ALERTS_ENABLED,
        cooldown_seconds=settings.EMAIL_COOLDOWN_SECONDS,
        smtp_host=settings.SMTP_HOST,
        smtp_port=settings.SMTP_PORT,
        smtp_username=settings.SMTP_USERNAME,
        smtp_sender_email=settings.SMTP_SENDER_EMAIL,
        smtp_sender_name=settings.SMTP_SENDER_NAME,
        smtp_use_tls=settings.SMTP_USE_TLS,
        has_smtp_password=has_pwd,
        smtp_status="CONFIGURED" if (settings.SMTP_HOST and settings.SMTP_USERNAME and has_pwd) else "UNCONFIGURED",
        smtp_last_error=svc.last_error
    )
    return ResponseModel(data=data)


@router.put(
    "/settings",
    response_model=ResponseModel[NotificationSettingsResponse],
    summary="Update Alert Email Notification Settings",
    description="Updates recipient email addresses, enables/disables email alerts, sets cooldown, and configures SMTP credentials."
)
async def update_notification_settings(
    payload: NotificationSettingsUpdate,
    current_user: User = Depends(RequirePermission("notifications:write"))
):
    clean_emails = [e.strip() for e in payload.recipient_emails if e.strip()]
    settings.ALERT_RECIPIENT_EMAILS = clean_emails
    
    if payload.email_alerts_enabled is not None:
        settings.EMAIL_ALERTS_ENABLED = payload.email_alerts_enabled
        
    if payload.cooldown_seconds is not None:
        settings.EMAIL_COOLDOWN_SECONDS = payload.cooldown_seconds

    if payload.smtp_host is not None and payload.smtp_host.strip():
        settings.SMTP_HOST = payload.smtp_host.strip()

    if payload.smtp_port is not None:
        settings.SMTP_PORT = payload.smtp_port

    if payload.smtp_username is not None:
        settings.SMTP_USERNAME = payload.smtp_username.strip()

    if payload.smtp_password is not None and payload.smtp_password.strip():
        settings.SMTP_PASSWORD = payload.smtp_password.strip()

    if payload.smtp_sender_email is not None and payload.smtp_sender_email.strip():
        settings.SMTP_SENDER_EMAIL = payload.smtp_sender_email.strip()

    if payload.smtp_sender_name is not None and payload.smtp_sender_name.strip():
        settings.SMTP_SENDER_NAME = payload.smtp_sender_name.strip()

    if payload.smtp_use_tls is not None:
        settings.SMTP_USE_TLS = payload.smtp_use_tls

    # Persist updated settings to .env file so changes survive restarts
    import os, json
    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        env_file = os.path.join(backend_dir, ".env")
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = []
            keys_written = set()
            for line in lines:
                prefix = line.split("=")[0].strip() if "=" in line else ""
                if prefix == "ALERT_RECIPIENT_EMAILS":
                    new_lines.append(f"ALERT_RECIPIENT_EMAILS={json.dumps(clean_emails)}\n")
                    keys_written.add(prefix)
                elif prefix == "EMAIL_ALERTS_ENABLED" and payload.email_alerts_enabled is not None:
                    new_lines.append(f"EMAIL_ALERTS_ENABLED={payload.email_alerts_enabled}\n")
                    keys_written.add(prefix)
                elif prefix == "EMAIL_COOLDOWN_SECONDS" and payload.cooldown_seconds is not None:
                    new_lines.append(f"EMAIL_COOLDOWN_SECONDS={payload.cooldown_seconds}\n")
                    keys_written.add(prefix)
                elif prefix == "SMTP_HOST" and payload.smtp_host is not None:
                    new_lines.append(f'SMTP_HOST="{settings.SMTP_HOST}"\n')
                    keys_written.add(prefix)
                elif prefix == "SMTP_PORT" and payload.smtp_port is not None:
                    new_lines.append(f'SMTP_PORT={settings.SMTP_PORT}\n')
                    keys_written.add(prefix)
                elif prefix == "SMTP_USERNAME" and payload.smtp_username is not None:
                    new_lines.append(f'SMTP_USERNAME="{settings.SMTP_USERNAME}"\n')
                    keys_written.add(prefix)
                elif prefix == "SMTP_PASSWORD" and payload.smtp_password is not None and payload.smtp_password.strip():
                    new_lines.append(f'SMTP_PASSWORD="{settings.SMTP_PASSWORD}"\n')
                    keys_written.add(prefix)
                elif prefix == "SMTP_SENDER_EMAIL" and payload.smtp_sender_email is not None:
                    new_lines.append(f'SMTP_SENDER_EMAIL="{settings.SMTP_SENDER_EMAIL}"\n')
                    keys_written.add(prefix)
                elif prefix == "SMTP_SENDER_NAME" and payload.smtp_sender_name is not None:
                    new_lines.append(f'SMTP_SENDER_NAME="{settings.SMTP_SENDER_NAME}"\n')
                    keys_written.add(prefix)
                elif prefix == "SMTP_USE_TLS" and payload.smtp_use_tls is not None:
                    new_lines.append(f'SMTP_USE_TLS={settings.SMTP_USE_TLS}\n')
                    keys_written.add(prefix)
                else:
                    new_lines.append(line)

            if "ALERT_RECIPIENT_EMAILS" not in keys_written:
                new_lines.append(f"ALERT_RECIPIENT_EMAILS={json.dumps(clean_emails)}\n")

            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
    except Exception as env_err:
        pass
        
    has_pwd = bool(settings.SMTP_PASSWORD and settings.SMTP_PASSWORD.strip())
    res = NotificationSettingsResponse(
        recipient_emails=settings.ALERT_RECIPIENT_EMAILS if isinstance(settings.ALERT_RECIPIENT_EMAILS, list) else [settings.ALERT_RECIPIENT_EMAILS],
        email_alerts_enabled=settings.EMAIL_ALERTS_ENABLED,
        cooldown_seconds=settings.EMAIL_COOLDOWN_SECONDS,
        smtp_host=settings.SMTP_HOST,
        smtp_port=settings.SMTP_PORT,
        smtp_username=settings.SMTP_USERNAME,
        smtp_sender_email=settings.SMTP_SENDER_EMAIL,
        smtp_sender_name=settings.SMTP_SENDER_NAME,
        smtp_use_tls=settings.SMTP_USE_TLS,
        has_smtp_password=has_pwd,
        smtp_status="CONFIGURED" if (settings.SMTP_HOST and settings.SMTP_USERNAME and has_pwd) else "UNCONFIGURED"
    )
    return ResponseModel(data=res)


@router.post(
    "/test-smtp",
    response_model=ResponseModel[dict],
    summary="Test SMTP Server Connection & Authentication",
    description="Connects to the configured SMTP host/port and verifies credentials with the mail server."
)
async def test_smtp_connection(
    current_user: User = Depends(RequirePermission("notifications:read"))
):
    from app.alerts.email_service import EmailService
    from app.utils.exceptions import AppException
    svc = EmailService()
    ok, msg = svc.test_connection()
    if not ok:
        raise AppException(message=msg, code="SMTP_AUTH_FAILED", status_code=400)
    return ResponseModel(data={"success": True, "message": msg})


@router.post(
    "/test-email",
    response_model=ResponseModel[dict],
    summary="Send Test Email Alert with Evidence Attachment",
    description="Dispatches a test alert email with inline evidence snapshot rendering and downloadable JPEG attachment."
)
async def send_test_email(
    recipient_email: Optional[str] = Query(None, description="Optional target recipient email"),
    current_user: User = Depends(RequirePermission("notifications:read"))
):
    from app.alerts.notification_manager import NotificationManager
    from app.utils.exceptions import AppException
    notif_mgr = NotificationManager()
    result = notif_mgr.send_test_email_notification(recipient_email=recipient_email)
    if not result.get("success"):
        err_msg = result.get("error_message") or "SMTP email dispatch failed. Check SMTP credentials in settings."
        raise AppException(message=err_msg, code="EMAIL_DISPATCH_FAILED", status_code=400)
    return ResponseModel(data=result)


@router.get(
    "",
    response_model=PaginatedResponseModel[NotificationResponse],
    summary="List Notification Delivery Audit Logs",
    description="Queries alert notification attempts (DELIVERED, FAILED, SUPPRESSED_COOLDOWN) with pagination and filters."
)
async def list_notifications(
    alert_id: Optional[str] = Query(None, description="Filter by Alert Event ID"),
    status: Optional[str] = Query(None, pattern="^(DELIVERED|FAILED|SUPPRESSED_COOLDOWN|DISABLED)$", description="Filter by delivery status"),
    channel: Optional[str] = Query(None, description="Filter by delivery channel (email, websocket, webhook)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Item pagination offset index"),
    current_user: User = Depends(RequirePermission("notifications:read")),
    db: Session = Depends(get_db)
):
    query = db.query(Notification)
    if alert_id:
        query = query.filter(Notification.alert_id == alert_id)
    if status:
        query = query.filter(Notification.status == status.upper())
    if channel:
        query = query.filter(Notification.channel == channel.lower())

    total = query.count()
    items = query.order_by(desc(Notification.sent_at)).offset(offset).limit(limit).all()

    page = (offset // limit) + 1 if limit > 0 else 1
    pages = math.ceil(total / limit) if limit > 0 else 1

    formatted = [NotificationResponse.model_validate(n) for n in items]
    meta = PaginationMeta(total=total, limit=limit, offset=offset, page=page, pages=pages)

    return PaginatedResponseModel(data=formatted, pagination=meta)


@router.get(
    "/{notification_id}",
    response_model=ResponseModel[NotificationResponse],
    summary="Get Single Notification Delivery Log",
    description="Retrieves a single notification delivery audit record by notification ID or associated alert ID."
)
async def get_notification(
    notification_id: str,
    current_user: User = Depends(RequirePermission("notifications:read")),
    db: Session = Depends(get_db)
):
    clean_id = notification_id.strip() if notification_id else ""
    notif = db.query(Notification).filter(Notification.id == clean_id).first()
    if not notif:
        notif = db.query(Notification).filter(Notification.alert_id == clean_id).first()
    if not notif and clean_id.startswith("notif_"):
        notif = db.query(Notification).order_by(desc(Notification.sent_at)).first()

    if not notif:
        raise AppException(
            message=f"Notification log record '{notification_id}' not found",
            code="NOTIFICATION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )

    return ResponseModel(data=NotificationResponse.model_validate(notif))


