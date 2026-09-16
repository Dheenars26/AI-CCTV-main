"""
Unit tests for PersonTracker and PPEAssociationEngine spatial body region correlation.
"""

import pytest
from app.detection.base import BoundingBox, DetectionResult
from app.safety.tracker import PersonTracker, TrackedPerson
from app.safety.association import PPEAssociationEngine, WorkerPPEAnalysis


def test_person_tracker_iou_matching():
    tracker = PersonTracker(camera_id=1, iou_threshold=0.3)
    
    # Frame 1: Single worker detection
    det1 = DetectionResult(
        label="person",
        confidence=0.90,
        bbox=BoundingBox(x_min=0.2, y_min=0.2, x_max=0.5, y_max=0.8)
    )
    tracks1 = tracker.update([det1])
    assert len(tracks1) == 1
    initial_pid = tracks1[0].person_id

    # Frame 2: Slightly shifted detection for same worker
    det2 = DetectionResult(
        label="person",
        confidence=0.92,
        bbox=BoundingBox(x_min=0.21, y_min=0.21, x_max=0.51, y_max=0.81)
    )
    tracks2 = tracker.update([det2])
    assert len(tracks2) == 1
    assert tracks2[0].person_id == initial_pid


def test_ppe_spatial_association_pass_and_violation():
    engine = PPEAssociationEngine()

    person_bbox = BoundingBox(x_min=0.2, y_min=0.2, x_max=0.5, y_max=0.8)
    tracked_persons = [
        TrackedPerson(person_id=101, camera_id=1, bbox=person_bbox, confidence=0.95, last_seen_timestamp=100.0)
    ]

    # Test Case 1: Helmet present on head region (top 30% of box: y_min=0.2 to 0.38)
    helmet_bbox = BoundingBox(x_min=0.25, y_min=0.21, x_max=0.45, y_max=0.32)
    vest_bbox = BoundingBox(x_min=0.22, y_min=0.35, x_max=0.48, y_max=0.65)

    ppe_dets = [
        DetectionResult(label="helmet", confidence=0.91, bbox=helmet_bbox),
        DetectionResult(label="vest", confidence=0.89, bbox=vest_bbox)
    ]

    # Required: helmet and vest -> Result: PASS
    analyses = engine.associate(
        camera_id=1,
        tracked_persons=tracked_persons,
        ppe_detections=ppe_dets,
        required_equipment=["helmet", "vest"]
    )
    assert len(analyses) == 1
    worker = analyses[0]
    assert worker.status == "PASS"
    assert "helmet" in worker.detected_equipment
    assert "vest" in worker.detected_equipment
    assert len(worker.missing_equipment) == 0

    # Test Case 2: Vest missing -> Result: VIOLATION
    analyses_viol = engine.associate(
        camera_id=1,
        tracked_persons=tracked_persons,
        ppe_detections=[DetectionResult(label="helmet", confidence=0.91, bbox=helmet_bbox)],
        required_equipment=["helmet", "vest"]
    )
    assert len(analyses_viol) == 1
    worker_viol = analyses_viol[0]
    assert worker_viol.status == "VIOLATION"
    assert "vest" in worker_viol.missing_equipment


def test_person_tracker_duplicate_purging_and_disappeared_filtering():
    tracker = PersonTracker(camera_id=1, iou_threshold=0.3)

    # Frame 1: Two overlapping person detections for the exact same worker
    detA = DetectionResult(label="person", confidence=0.92, bbox=BoundingBox(x_min=0.20, y_min=0.20, x_max=0.50, y_max=0.80))
    detB = DetectionResult(label="person", confidence=0.88, bbox=BoundingBox(x_min=0.22, y_min=0.21, x_max=0.51, y_max=0.81))

    # Single call should purge the duplicate track
    tracks = tracker.update([detA, detB])
    assert len(tracks) == 1
    active_pid = tracks[0].person_id

    # Frame 2: Empty detection frame -> track should be kept in memory but NOT returned in get_active_tracks()
    active_tracks = tracker.update([])
    assert len(active_tracks) == 0
    assert active_pid in tracker._tracked_persons
    assert tracker._disappeared_counts[active_pid] == 1

    # Frame 3: Worker reappears -> active track returned immediately with same person_id
    reappeared_tracks = tracker.update([detA])
    assert len(reappeared_tracks) == 1
    assert reappeared_tracks[0].person_id == active_pid

