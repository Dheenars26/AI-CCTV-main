"""
Safety Rule Engine & Event Correlation Subsystem (SafetyRuleEngine).
Evaluates zone-specific PPE compliance, missing item severities, unauthorized zone entries, and correlates Fire/Smoke + PPE events into combined SAFETY_INCIDENT payloads without alert duplication.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from app.config.settings import settings
from app.detection.base import DetectionResult
from app.safety.association import WorkerPPEAnalysis
from app.zones.engine import ZoneEvaluationResult
from app.utils.logger import logger


@dataclass
class SafetyRuleDecision:
    camera_id: int
    incident_type: str  # "FIRE", "SMOKE", "PPE_VIOLATION", "ZONE_VIOLATION", "SAFETY_INCIDENT"
    events: List[str]
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    person_id: Optional[int] = None
    zone_id: Optional[int] = None
    zone_name: Optional[str] = None
    missing_items: List[str] = field(default_factory=list)
    confidence: float = 0.0
    timestamp: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "incident_type": self.incident_type,
            "events": self.events,
            "severity": self.severity,
            "person_id": self.person_id,
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "missing_items": self.missing_items,
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp,
            "details": self.details
        }


class SafetyRuleEngine:
    """
    Safety Rule Engine & Alert Deduplication Controller.
    """

    SEVERITY_MAPPING: Dict[str, str] = {
        "helmet": "HIGH",
        "vest": "HIGH",
        "safety_vest": "HIGH",
        "goggles": "HIGH",
        "safety_glasses": "HIGH",
        "safety_glass": "HIGH",
        "glass": "HIGH",
        "glasses": "HIGH",
        "mask": "MEDIUM",
        "gloves": "MEDIUM",
        "safety_shoes": "MEDIUM",
        "unauthorized_zone": "HIGH",
        "fire": "CRITICAL",
        "smoke": "CRITICAL"
    }

    def __init__(self, cooldown_seconds: float = 60.0):
        self.cooldown_seconds = cooldown_seconds
        # Cooldown map key: (camera_id, person_id, incident_type) -> last_timestamp
        self._alert_cooldown_registry: Dict[Tuple[int, Optional[int], str], float] = {}

    def evaluate_rules(
        self,
        camera_id: int,
        fire_smoke_detections: List[DetectionResult],
        worker_analyses: List[WorkerPPEAnalysis],
        zone_evaluations: List[ZoneEvaluationResult],
        timestamp: Optional[str] = None
    ) -> List[SafetyRuleDecision]:
        """
        Evaluates frame detections, worker analyses, and zone events against safety rules.
        Applies Fire/Smoke + PPE correlation and deduplication.
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        decisions: List[SafetyRuleDecision] = []
        now_ts = time.time()

        has_fire = any(d.label.lower() == "fire" for d in fire_smoke_detections)
        has_smoke = any(d.label.lower() == "smoke" for d in fire_smoke_detections)
        max_fire_conf = max([d.confidence for d in fire_smoke_detections if d.label.lower() == "fire"], default=0.0)
        max_smoke_conf = max([d.confidence for d in fire_smoke_detections if d.label.lower() == "smoke"], default=0.0)

        # 1. Evaluate Worker PPE & Zone Violations
        active_violations: List[Dict[str, Any]] = []

        for worker in worker_analyses:
            # Find matching zone evaluation for this worker
            worker_zones = [z for z in zone_evaluations if z.worker_analysis.person_id == worker.person_id]

            if worker_zones:
                for z_eval in worker_zones:
                    # Check for unauthorized restricted zone entry
                    if z_eval.is_unauthorized:
                        decisions.append(SafetyRuleDecision(
                            camera_id=camera_id,
                            incident_type="ZONE_VIOLATION",
                            events=["UNAUTHORIZED_AREA_ENTRY"],
                            severity="HIGH",
                            person_id=worker.person_id,
                            zone_id=z_eval.zone_id,
                            zone_name=z_eval.zone_name,
                            confidence=worker.confidence,
                            timestamp=ts,
                            details={"worker_status": worker.status, "bounding_box": worker.bounding_box.to_dict()}
                        ))

                    # Check for PPE violation inside zone
                    if worker.status == "VIOLATION":
                        sev = self.calculate_ppe_severity(worker.missing_equipment)
                        active_violations.append({
                            "worker": worker,
                            "zone": z_eval,
                            "severity": sev
                        })

                        # Standalone PPE Violation decision
                        if not has_fire and not has_smoke:
                            decisions.append(SafetyRuleDecision(
                                camera_id=camera_id,
                                incident_type="PPE_VIOLATION",
                                events=["PPE_VIOLATION"],
                                severity=sev,
                                person_id=worker.person_id,
                                zone_id=z_eval.zone_id,
                                zone_name=z_eval.zone_name,
                                missing_items=worker.missing_equipment,
                                confidence=worker.confidence,
                                timestamp=ts,
                                details={"detected_items": worker.detected_equipment, "bounding_box": worker.bounding_box.to_dict()}
                            ))
            else:
                # Worker outside designated zones
                if worker.status == "VIOLATION":
                    sev = self.calculate_ppe_severity(worker.missing_equipment)
                    active_violations.append({
                        "worker": worker,
                        "zone": None,
                        "severity": sev
                    })
                    if not has_fire and not has_smoke:
                        decisions.append(SafetyRuleDecision(
                            camera_id=camera_id,
                            incident_type="PPE_VIOLATION",
                            events=["PPE_VIOLATION"],
                            severity=sev,
                            person_id=worker.person_id,
                            missing_items=worker.missing_equipment,
                            confidence=worker.confidence,
                            timestamp=ts,
                            details={"detected_items": worker.detected_equipment, "bounding_box": worker.bounding_box.to_dict()}
                        ))

        # 2. Fire/Smoke + PPE Correlation Logic (Combined Incident)
        if has_fire or has_smoke:
            events_list = []
            if has_fire:
                events_list.append("FIRE_DETECTED")
            if has_smoke:
                events_list.append("SMOKE_DETECTED")

            if active_violations:
                events_list.append("PPE_VIOLATION")
                for viol in active_violations:
                    w = viol["worker"]
                    z = viol["zone"]
                    decisions.append(SafetyRuleDecision(
                        camera_id=camera_id,
                        incident_type="SAFETY_INCIDENT",
                        events=events_list,
                        severity="CRITICAL",
                        person_id=w.person_id,
                        zone_id=z.zone_id if z else None,
                        zone_name=z.zone_name if z else None,
                        missing_items=w.missing_equipment,
                        confidence=max(max_fire_conf, max_smoke_conf, w.confidence),
                        timestamp=ts,
                        details={
                            "correlation": "FIRE_SMOKE_AND_PPE_VIOLATION",
                            "worker_status": w.status,
                            "missing_equipment": w.missing_equipment
                        }
                    ))
            else:
                # Standalone Fire/Smoke incident
                inc_type = "FIRE" if has_fire else "SMOKE"
                conf = max_fire_conf if has_fire else max_smoke_conf
                decisions.append(SafetyRuleDecision(
                    camera_id=camera_id,
                    incident_type=inc_type,
                    events=events_list,
                    severity="CRITICAL",
                    confidence=conf,
                    timestamp=ts,
                    details={"class_name": inc_type.lower()}
                ))

        # 3. Apply Alert Deduplication & Cooldown Filtering
        filtered_decisions: List[SafetyRuleDecision] = []
        for dec in decisions:
            cooldown_key = (dec.camera_id, dec.person_id, dec.incident_type)
            last_sent = self._alert_cooldown_registry.get(cooldown_key, 0.0)

            if (now_ts - last_sent) >= self.cooldown_seconds:
                self._alert_cooldown_registry[cooldown_key] = now_ts
                filtered_decisions.append(dec)
            else:
                logger.debug(f"SafetyRuleEngine: Suppressed duplicate alert for {cooldown_key} due to active cooldown.")

        return filtered_decisions

    def calculate_ppe_severity(self, missing_items: List[str]) -> str:
        """
        Determines overall severity based on missing equipment list.
        """
        if not missing_items:
            return "LOW"

        highest_sev = "LOW"
        for item in missing_items:
            item_sev = self.SEVERITY_MAPPING.get(item.lower(), "HIGH")
            if item_sev == "CRITICAL":
                return "CRITICAL"
            elif item_sev == "HIGH":
                highest_sev = "HIGH"
            elif item_sev == "MEDIUM" and highest_sev != "HIGH":
                highest_sev = "MEDIUM"

        return highest_sev
