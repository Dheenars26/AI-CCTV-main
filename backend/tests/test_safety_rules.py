"""
Unit tests for SafetyRuleEngine correlation, severity assignment, and alert deduplication.
"""

import pytest
from app.detection.base import BoundingBox, DetectionResult
from app.safety.association import WorkerPPEAnalysis
from app.zones.engine import ZoneEvaluationResult
from app.safety.rules import SafetyRuleEngine


def test_ppe_severity_calculation():
    engine = SafetyRuleEngine()

    assert engine.calculate_ppe_severity(["helmet"]) == "HIGH"
    assert engine.calculate_ppe_severity(["vest"]) == "HIGH"
    assert engine.calculate_ppe_severity(["safety_vest"]) == "HIGH"
    assert engine.calculate_ppe_severity(["goggles"]) == "HIGH"
    assert engine.calculate_ppe_severity(["safety_glass"]) == "HIGH"
    assert engine.calculate_ppe_severity(["safety_glasses"]) == "HIGH"
    assert engine.calculate_ppe_severity(["gloves"]) == "MEDIUM"
    assert engine.calculate_ppe_severity(["fire"]) == "CRITICAL"
    assert engine.calculate_ppe_severity(["smoke"]) == "CRITICAL"
    assert engine.calculate_ppe_severity([]) == "LOW"


test_worker_box = BoundingBox(x_min=0.2, y_min=0.2, x_max=0.4, y_max=0.5)

def test_fire_and_ppe_correlation_combined_incident():
    engine = SafetyRuleEngine(cooldown_seconds=0.0)  # Disable cooldown for immediate evaluation

    fire_dets = [DetectionResult(label="fire", confidence=0.92, bbox=test_worker_box)]
    
    worker = WorkerPPEAnalysis(
        person_id=101,
        camera_id=1,
        bounding_box=test_worker_box,
        status="VIOLATION",
        required_equipment=["helmet", "vest"],
        detected_equipment=["vest"],
        missing_equipment=["helmet"],
        confidence=0.90,
        timestamp="2026-08-26T10:00:00Z"
    )

    decisions = engine.evaluate_rules(
        camera_id=1,
        fire_smoke_detections=fire_dets,
        worker_analyses=[worker],
        zone_evaluations=[]
    )

    assert len(decisions) >= 1
    combined = [d for d in decisions if d.incident_type == "SAFETY_INCIDENT"]
    assert len(combined) == 1
    inc = combined[0]
    assert inc.severity == "CRITICAL"
    assert "FIRE_DETECTED" in inc.events
    assert "PPE_VIOLATION" in inc.events
