"""
DVR Adapters Package.
"""
from app.camera.adapters.base import DVRAdapter
from app.camera.adapters.factory import DVRAdapterFactory

__all__ = ["DVRAdapter", "DVRAdapterFactory"]
