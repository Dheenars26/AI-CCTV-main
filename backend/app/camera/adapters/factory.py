"""
DVR Adapter Factory (DVRAdapterFactory).
Instantiates manufacturer-specific adapter instances based on manufacturer enum/string.
"""

from app.camera.adapters.base import DVRAdapter
from app.camera.adapters.generic import GenericRTSPAdapter
from app.camera.adapters.hikvision import HikvisionAdapter
from app.camera.adapters.dahua import DahuaAdapter
from app.camera.adapters.cpplus import CPPlusAdapter


class DVRAdapterFactory:

    @staticmethod
    def get_adapter(manufacturer: str) -> DVRAdapter:
        m = (manufacturer or "GENERIC_RTSP").upper()
        if "HIKVISION" in m:
            return HikvisionAdapter()
        elif "DAHUA" in m:
            return DahuaAdapter()
        elif "CPPLUS" in m or "CP_PLUS" in m:
            return CPPlusAdapter()
        else:
            return GenericRTSPAdapter()
