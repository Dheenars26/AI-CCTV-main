"""
Webhook Notification Service.
Dispatches real-time JSON alert payloads to configured external Webhook endpoints
with SHA256 HMAC security signature verification.
"""

import hmac
import hashlib
import json
import time
from typing import Dict, Any, List, Optional
import httpx

from app.config.settings import settings
from app.utils.logger import logger


class WebhookService:
    """
    Service responsible for dispatching HTTP POST webhook notifications
    for fire and smoke incident alerts.
    """

    def __init__(
        self,
        urls: Optional[List[str]] = None,
        secret_key: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        self.urls = urls if urls is not None else settings.WEBHOOK_URLS
        self.secret_key = secret_key or settings.WEBHOOK_SECRET_KEY
        self.timeout = timeout if timeout is not None else settings.WEBHOOK_TIMEOUT_SECONDS

    def generate_signature(self, payload_bytes: bytes) -> str:
        """
        Generates HMAC SHA256 signature string for payload authentication.
        """
        return hmac.new(
            self.secret_key.encode("utf-8"),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

    def dispatch_webhook(
        self,
        target_url: str,
        alert_payload: Dict[str, Any]
    ) -> bool:
        """
        Dispatches alert JSON payload to a single target Webhook URL.
        Returns True on HTTP 2xx success, False otherwise.
        """
        try:
            payload_bytes = json.dumps(alert_payload, separators=(',', ':')).encode('utf-8')
            signature = self.generate_signature(payload_bytes)

            headers = {
                "Content-Type": "application/json",
                "User-Agent": f"AI-CCTV-Monitor/{settings.VERSION}",
                "X-CCTV-Signature": f"sha256={signature}",
                "X-CCTV-Timestamp": str(int(time.time()))
            }

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(target_url, content=payload_bytes, headers=headers)

            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"WebhookService: Successfully delivered alert payload to '{target_url}' (HTTP {response.status_code}).")
                return True
            else:
                logger.warning(f"WebhookService: Webhook endpoint '{target_url}' returned non-success status code {response.status_code}.")
                return False

        except Exception as e:
            logger.error(f"WebhookService: Exception delivering webhook to '{target_url}': {str(e)}")
            return False

    def dispatch_all(
        self,
        alert_payload: Dict[str, Any],
        custom_urls: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Dispatches alert JSON payload to all configured target Webhook URLs.
        Returns a dictionary mapping target_url -> delivery_success_bool.
        """
        target_urls = custom_urls if custom_urls is not None else self.urls
        if not target_urls:
            logger.info("WebhookService: No target webhook URLs configured.")
            return {}

        results: Dict[str, bool] = {}
        for url in target_urls:
            results[url] = self.dispatch_webhook(url, alert_payload)

        return results
