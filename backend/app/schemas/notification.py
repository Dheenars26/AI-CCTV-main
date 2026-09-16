"""
Pydantic Schemas for Alert Notification Delivery Logs.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Notification Log ID")
    alert_id: str = Field(..., description="Target Alert Event ID")
    channel: str = Field(..., description="Delivery channel (email, websocket, webhook)")
    recipient: str = Field(..., description="Recipient email address")
    status: str = Field(..., description="Delivery status (DELIVERED, FAILED, SUPPRESSED_COOLDOWN)")
    error_message: Optional[str] = Field(default=None, description="Detailed failure diagnostic message")
    sent_at: datetime = Field(..., description="Delivery attempt timestamp")


class NotificationSettingsUpdate(BaseModel):
    recipient_emails: list[str] = Field(..., description="List of target alert recipient email addresses")
    email_alerts_enabled: Optional[bool] = Field(default=True, description="Enable or disable email notifications globally")
    cooldown_seconds: Optional[float] = Field(default=60.0, description="Cooldown suppression window in seconds between duplicate email alerts")
    smtp_host: Optional[str] = Field(default=None, description="SMTP server hostname (e.g. smtp.gmail.com)")
    smtp_port: Optional[int] = Field(default=None, description="SMTP port (e.g. 587)")
    smtp_username: Optional[str] = Field(default=None, description="SMTP username/email")
    smtp_password: Optional[str] = Field(default=None, description="SMTP App Password")
    smtp_sender_email: Optional[str] = Field(default=None, description="From sender email address")
    smtp_sender_name: Optional[str] = Field(default=None, description="Display sender name")
    smtp_use_tls: Optional[bool] = Field(default=None, description="Enable TLS encryption")


class NotificationSettingsResponse(BaseModel):
    recipient_emails: list[str]
    email_alerts_enabled: bool
    cooldown_seconds: float
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_sender_email: str = ""
    smtp_sender_name: str = ""
    smtp_use_tls: bool = True
    has_smtp_password: bool = False
    smtp_status: str = "UNCONFIGURED"
    smtp_last_error: Optional[str] = None


