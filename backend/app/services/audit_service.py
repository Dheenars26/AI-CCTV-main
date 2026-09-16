"""
Dedicated Security Audit Service.
Records security events (Logins, Failed Attempts, Revocations, RBAC Denials, Entity Mutations)
in the database 'audit_logs' table while strictly redacting sensitive credentials and tokens.
"""

from typing import Optional, Dict, Any, Union
import json
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.utils.security import sanitize_dict_for_logging
from app.utils.logger import logger


class AuditService:
    """
    Service for writing structured security audit events.
    """

    @staticmethod
    def log_event(
        db: Session,
        event_type: str,
        actor_id: Optional[str] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "SUCCESS",
        details: Optional[Union[Dict[str, Any], str]] = None
    ) -> Optional[AuditLog]:
        """
        Creates and persists an AuditLog entry. Automatically redacts passwords/tokens in details.
        """
        try:
            sanitized_details_str = None
            if details:
                if isinstance(details, dict):
                    safe_details = sanitize_dict_for_logging(details)
                elif isinstance(details, str):
                    safe_details = {"info": details}
                else:
                    safe_details = {"info": str(details)}
                sanitized_details_str = json.dumps(safe_details)

            audit_entry = AuditLog(
                event_type=event_type,
                actor_id=actor_id,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                details=sanitized_details_str
            )
            db.add(audit_entry)
            db.commit()

            logger.info(
                f"SECURITY AUDIT [{status}]: Event '{event_type}' by User '{username or actor_id or 'anonymous'}' "
                f"from IP '{ip_address or 'unknown'}'"
            )
            return audit_entry

        except Exception as e:
            logger.error(f"AuditService: Failed to record audit log entry: {str(e)}")
            return None
