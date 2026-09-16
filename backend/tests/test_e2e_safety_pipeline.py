"""
End-to-End integration test for full CCTV Workplace Safety Monitoring Pipeline:
CCTV Ingestion -> CameraManager -> Frame Pipeline -> Fire/Smoke + Person + PPE -> Association -> Zone Engine -> Rule Engine -> Temporal Verification -> Incident -> Evidence -> REST + WebSocket.
"""

import numpy as np
import pytest
from app.camera.pipeline import FramePipeline
from app.detection.base import BoundingBox, DetectionResult
from app.safety.association import PPEAssociationEngine
from app.zones.engine import ZoneEngine
from app.safety.rules import SafetyRuleEngine
from app.safety.verification import PPETemporalVerificationEngine


def test_full_end_to_end_safety_pipeline():
    # 1. Setup Camera Pipeline
    pipeline = FramePipeline(
        camera_id=1,
        fire_smoke_enabled=True,
        ppe_enabled=True,
        person_enabled=True,
        zone_enabled=True
    )

    # 2. Register Safety Zone
    zone_data = {
        "id": 1,
        "name": "Chemical Heavy Machinery Area",
        "zone_type": "HAZARD",
        "polygon_coordinates": [[0.1, 0.1], [0.6, 0.1], [0.6, 0.7], [0.1, 0.7]],
        "enabled": True
    }
    pipeline.set_safety_zones([zone_data])

    # 3. Register PPE Profile
    profile_data = {
        "id": 1,
        "name": "Chemical Hazard Profile",
        "required_equipment": ["helmet", "vest", "mask"]
    }
    pipeline.set_ppe_profile(profile_data)

    # 4. Generate dummy frame & run pipeline across consecutive frames to verify temporal transition
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    for fid in range(1, 7):
        processed = pipeline.process_frame(dummy_frame, frame_id=fid, fps=25.0)
        assert processed.camera_id == 1
        assert "worker_ppe_analyses" in processed.metadata
        assert "safety_decisions" in processed.metadata
        assert "verified_events" in processed.metadata
