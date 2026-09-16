"""
Protected Prometheus Metrics REST Endpoint (/metrics).
Exposes non-cardinal Prometheus exposition output guarded by authorization controls.
"""

from fastapi import APIRouter, Depends, Response
from app.models.user import User
from app.api.v1.dependencies.permissions import RequirePermission
from app.utils.metrics import metrics_collector

router = APIRouter(tags=["Metrics Telemetry"])


@router.get(
    "/metrics",
    summary="Get Prometheus Metrics Telemetry",
    description="Returns system operational metrics in Prometheus exposition format. Guarded by RBAC permissions."
)
async def get_prometheus_metrics(
    current_user: User = Depends(RequirePermission("system:status"))
):
    output = metrics_collector.generate_prometheus_output()
    return Response(content=output, media_type="text/plain; version=0.0.4; charset=utf-8")
