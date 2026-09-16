"""
Unit tests for ZoneEngine polygon validation and point-in-polygon containment evaluation.
"""

import pytest
from app.detection.base import BoundingBox
from app.zones.engine import ZoneEngine
from app.safety.association import WorkerPPEAnalysis


def test_polygon_validation():
    # Valid polygon (square)
    valid_poly = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]
    is_valid, msg = ZoneEngine.validate_polygon(valid_poly)
    assert is_valid is True

    # Invalid polygon (< 3 vertices)
    invalid_poly = [[0.1, 0.1], [0.5, 0.1]]
    is_valid, msg = ZoneEngine.validate_polygon(invalid_poly)
    assert is_valid is False
    assert "at least 3 vertices" in msg

    # Out of bounds coordinates
    oob_poly = [[-0.1, 0.1], [0.5, 0.1], [0.5, 1.5]]
    is_valid, msg = ZoneEngine.validate_polygon(oob_poly)
    assert is_valid is False


def test_point_and_worker_containment():
    poly = [[0.1, 0.1], [0.6, 0.1], [0.6, 0.6], [0.1, 0.6]]

    # Point inside
    assert ZoneEngine.point_in_polygon(0.3, 0.3, poly) is True
    # Point outside
    assert ZoneEngine.point_in_polygon(0.8, 0.8, poly) is False

    # Worker inside zone
    worker_inside_box = BoundingBox(x_min=0.2, y_min=0.2, x_max=0.4, y_max=0.5)
    assert ZoneEngine.is_worker_in_zone(worker_inside_box, poly) is True

    # Worker outside zone
    worker_outside_box = BoundingBox(x_min=0.7, y_min=0.7, x_max=0.9, y_max=0.9)
    assert ZoneEngine.is_worker_in_zone(worker_outside_box, poly) is False
