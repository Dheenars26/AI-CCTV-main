"""
WebSocket API Router (/api/v1/ws).
Provides real-time event streaming with single-use ticket handshake authentication.
Rejects query string JWT tokens to prevent token leakage in server logs.
"""

from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.websocket.connection_manager import manager
from app.services.ws_ticket_service import ws_ticket_service
from app.utils.logger import logger

ws_router = APIRouter(tags=["Real-Time WebSockets"])


def _extract_ticket_from_headers(websocket: WebSocket) -> Optional[str]:
    """
    Extracts single-use ticket from Sec-WebSocket-Protocol header or custom headers.
    Header format: Sec-WebSocket-Protocol: cctv-auth-wst_xxxxxx
    """
    subprotocols = websocket.headers.get("Sec-WebSocket-Protocol", "")
    for p in subprotocols.split(","):
        p = p.strip()
        if p.startswith("cctv-auth-"):
            return p.replace("cctv-auth-", "").strip()
        elif p.startswith("wst_"):
            return p.strip()
    return None


async def handle_websocket_connection(websocket: WebSocket, ticket: Optional[str] = None):
    """
    Core WebSocket connection lifecycle handler.
    Authenticates client using single-use handshake ticket.
    """
    # Try header subprotocol ticket if not provided directly
    if not ticket:
        ticket = _extract_ticket_from_headers(websocket)

    user_payload: Optional[dict] = None

    if ticket:
        user_payload = ws_ticket_service.consume_ticket(ticket)

    # In production mode, require valid ticket authentication
    if not user_payload:
        logger.warning("WebSocket: Connection attempt rejected due to missing, invalid, or expired single-use ticket.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Valid single-use WebSocket ticket required")
        return

    user_id = user_payload.get("user_id")
    username = user_payload.get("username")
    role = user_payload.get("role")

    # Accept connection with subprotocol header if requested
    subprotocol = f"cctv-auth-{ticket}" if ticket else None
    await manager.connect(websocket, user_id=user_id, subprotocol=subprotocol)

    welcome_msg = {
        "event": "connected",
        "version": "1.0",
        "timestamp": "",
        "data": {
            "message": "Connected to AI CCTV Real-Time Event Stream",
            "authenticated": True,
            "user_id": user_id,
            "username": username,
            "role": role,
            "channel": "alerts"
        }
    }
    await manager.send_personal_message(welcome_msg, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            await manager.handle_incoming_message(websocket, data)
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket connection closed: {str(e)}")
        await manager.disconnect(websocket)


@ws_router.websocket("/api/v1/ws")
async def websocket_primary_endpoint(websocket: WebSocket, ticket: Optional[str] = None):
    """
    Primary API v1 WebSocket event channel (/api/v1/ws).
    Subscribes client to real-time fire_detected, smoke_detected, alert_created, and camera events.
    """
    await handle_websocket_connection(websocket, ticket=ticket)


@ws_router.websocket("/ws/v1/alerts")
async def websocket_legacy_endpoint(websocket: WebSocket, ticket: Optional[str] = None):
    """
    Alerts WebSocket event channel alias (/ws/v1/alerts).
    Provided for backward compatibility.
    """
    await handle_websocket_connection(websocket, ticket=ticket)
