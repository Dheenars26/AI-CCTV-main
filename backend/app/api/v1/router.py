"""
API v1 Main Router Aggregator.
Combines auth, cameras, alerts, detections, evidence, notifications, and system routers under the /api/v1 prefix.
"""

from fastapi import APIRouter
from app.api.v1.endpoints import auth, cameras, dvrs, alerts, detections, evidence, notifications, system, ppe, zones, incidents, safety

api_v1_router = APIRouter(prefix="/api/v1")

# Include endpoint modules under /api/v1/
api_v1_router.include_router(auth.router)
api_v1_router.include_router(cameras.router)
api_v1_router.include_router(dvrs.router)
api_v1_router.include_router(alerts.router)
api_v1_router.include_router(detections.router)
api_v1_router.include_router(evidence.router)
api_v1_router.include_router(notifications.router)
api_v1_router.include_router(system.router)
api_v1_router.include_router(ppe.router)
api_v1_router.include_router(zones.router)
api_v1_router.include_router(incidents.router)
api_v1_router.include_router(incidents.events_router)
api_v1_router.include_router(safety.router)


