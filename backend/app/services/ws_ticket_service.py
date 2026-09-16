"""
Single-Use WebSocket Handshake Ticket Service.
Issues 10-second ephemeral single-use tickets to authenticate WebSockets without URL query string tokens.
"""

import time
import uuid
from typing import Dict, Any, Optional
from threading import Lock
from app.utils.logger import logger


class WSTicketService:
    """
    In-memory single-use ticket store with TTL expiration and thread safety.
    """

    def __init__(self, ttl_seconds: float = 30.0):
        self.ttl_seconds = ttl_seconds
        self._tickets: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    def issue_ticket(self, user_id: str, username: str, role: str) -> str:
        """
        Generates and stores a unique single-use WebSocket ticket for a user.
        Returns ticket string 'wst_<uuid>'.
        """
        ticket_id = f"wst_{uuid.uuid4().hex}"
        now = time.time()
        
        with self._lock:
            # Clean expired tickets
            self._purge_expired(now)

            self._tickets[ticket_id] = {
                "user_id": user_id,
                "username": username,
                "role": role,
                "expires_at": now + self.ttl_seconds
            }

        logger.debug(f"WSTicketService: Issued ticket '{ticket_id}' for user '{username}' (TTL {self.ttl_seconds}s)")
        return ticket_id

    def consume_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        Atomically validates and consumes (deletes) a ticket.
        Returns user payload if valid, None if expired, invalid, or already consumed.
        """
        now = time.time()
        with self._lock:
            self._purge_expired(now)

            ticket_data = self._tickets.pop(ticket_id, None)
            if not ticket_data:
                logger.warning(f"WSTicketService: Ticket '{ticket_id}' invalid, expired, or already consumed.")
                return None

            if now > ticket_data["expires_at"]:
                logger.warning(f"WSTicketService: Ticket '{ticket_id}' expired.")
                return None

            return ticket_data

    def _purge_expired(self, now: float):
        expired_keys = [k for k, v in self._tickets.items() if now > v["expires_at"]]
        for k in expired_keys:
            self._tickets.pop(k, None)


ws_ticket_service = WSTicketService()
