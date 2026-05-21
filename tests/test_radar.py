"""Tests for radar module."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt6.QtCore import QPointF
from radar import Radar


class TestRadarInit:
    """Test Radar initialization."""

    def test_basic_init(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        assert radar.name == "Test"
        assert radar.center.x() == 0
        assert radar.center.y() == 0
        assert radar.max_range == 100.0
        assert radar.view_angle == 30.0
        assert radar.rotation_speed == 36.0
        assert radar.start_angle == 0.0
        assert radar.current_angle == 0.0
        assert radar.tracked_target is None
        assert radar.tracked_point is None

    def test_custom_start_angle(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0, start_angle=45.0)
        assert radar.start_angle == 45.0
        assert radar.current_angle == 45.0

    def test_center_from_qpointf(self):
        center = QPointF(50, 75)
        radar = Radar("Test", center, 100.0, 30.0, 36.0)
        assert radar.center.x() == 50
        assert radar.center.y() == 75

    def test_center_from_list(self):
        radar = Radar("Test", [10, 20], 100.0, 30.0, 36.0)
        assert radar.center.x() == 10
        assert radar.center.y() == 20


class TestRadarGetDistanceToPoint:
    """Test get_distance_to_point method."""

    def test_zero_distance(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        assert radar.get_distance_to_point(QPointF(0, 0)) == 0.0

    def test_horizontal_distance(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        assert radar.get_distance_to_point(QPointF(3, 4)) == 5.0

    def test_vertical_distance(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        assert radar.get_distance_to_point(QPointF(0, 10)) == 10.0


class TestRadarGetCurrentAngle:
    """Test get_current_angle method."""

    def test_no_tracking_rotates(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        angle = radar.get_current_angle(1.0)
        assert angle == 36.0

    def test_tracking_stays_fixed(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        radar.tracked_target = "target"
        radar.current_angle = 90.0
        angle = radar.get_current_angle(10.0)
        assert angle == 90.0

    def test_angle_wraps_360(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        angle = radar.get_current_angle(10.0)
        assert 0 <= angle < 360.0


class TestRadarPointAngle:
    """Test _point_angle helper method."""

    def test_angle_east(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        angle = radar._point_angle(QPointF(10, 0))
        assert angle == 0.0

    def test_angle_north(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        angle = radar._point_angle(QPointF(0, -10))
        assert angle == 90.0

    def test_angle_west(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        angle = radar._point_angle(QPointF(-10, 0))
        assert angle == 180.0

    def test_angle_south(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        angle = radar._point_angle(QPointF(0, 10))
        assert angle == 270.0


class TestRadarPointInRange:
    """Test _point_in_range helper method."""

    def test_point_at_center(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        assert radar._point_in_range(QPointF(0, 0)) is True

    def test_point_inside_range(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        assert radar._point_in_range(QPointF(50, 0)) is True

    def test_point_at_range(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        assert radar._point_in_range(QPointF(100, 0)) is True

    def test_point_outside_range(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        assert radar._point_in_range(QPointF(150, 0)) is False


class TestRadarCanTrackPoint:
    """Test can_track_point method."""

    def test_in_range_can_track(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        assert radar.can_track_point(QPointF(50, 0)) is True

    def test_out_of_range_cannot_track(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        assert radar.can_track_point(QPointF(150, 0)) is False


class TestRadarStartTracking:
    """Test start_tracking method."""

    def test_sets_tracked_target(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        radar.start_tracking("target", QPointF(10, 0), 0.0)
        assert radar.tracked_target == "target"

    def test_sets_tracked_point(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        point = QPointF(10, 0)
        radar.start_tracking("target", point, 0.0)
        assert radar.tracked_point.x() == 10
        assert radar.tracked_point.y() == 0

    def test_sets_current_angle_to_point_angle(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        radar.start_tracking("target", QPointF(10, 0), 0.0)
        assert radar.current_angle == 0.0

    def test_sets_rotation_reference_time(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        radar.start_tracking("target", QPointF(10, 0), 5.0)
        assert radar.rotation_reference_time == 5.0


class TestRadarUpdateTracking:
    """Test update_tracking method."""

    def test_updates_tracked_point(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        radar.start_tracking("target", QPointF(10, 0), 0.0)
        radar.update_tracking(QPointF(0, 10), 1.0)
        assert radar.tracked_point.x() == 0
        assert radar.tracked_point.y() == 10

    def test_updates_rotation_reference_time(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        radar.start_tracking("target", QPointF(10, 0), 0.0)
        radar.update_tracking(QPointF(0, 10), 2.0)
        assert radar.rotation_reference_time == 2.0

    def test_angle_moves_toward_target(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 360.0)  # Fast rotation
        radar.start_tracking("target", QPointF(10, 0), 0.0)
        initial_angle = radar.current_angle
        radar.update_tracking(QPointF(0, 10), 0.25)  # 90 degrees away
        # Angle should have moved toward 90 degrees
        assert radar.current_angle != initial_angle or abs(radar.current_angle - 90.0) < 1.0


class TestRadarStopTracking:
    """Test stop_tracking method."""

    def test_clears_tracked_target(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        radar.start_tracking("target", QPointF(10, 0), 0.0)
        radar.stop_tracking(1.0)
        assert radar.tracked_target is None

    def test_clears_tracked_point(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        radar.start_tracking("target", QPointF(10, 0), 0.0)
        radar.stop_tracking(1.0)
        assert radar.tracked_point is None

    def test_preserves_current_angle(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        radar.start_tracking("target", QPointF(10, 0), 0.0)
        radar.update_tracking(QPointF(0, 10), 1.0)
        angle_before = radar.current_angle
        radar.stop_tracking(2.0)
        assert radar.current_angle == angle_before

    def test_sets_start_angle(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        radar.start_tracking("target", QPointF(10, 0), 0.0)
        radar.update_tracking(QPointF(0, 10), 1.0)
        radar.stop_tracking(2.0)
        assert radar.start_angle == radar.current_angle


class TestRadarContainsPoint:
    """Test contains_point method."""

    def test_in_range_and_in_sector(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0, start_angle=0.0)
        # Point at angle 0, within 15 degree half-angle
        assert radar.contains_point(QPointF(50, 0), 0.0) is True

    def test_in_range_but_out_of_sector(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0, start_angle=0.0)
        # Point at angle 90, outside sector centered at 0
        assert radar.contains_point(QPointF(0, -50), 0.0) is False

    def test_out_of_range(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        assert radar.contains_point(QPointF(150, 0), 0.0) is False

    def test_rotates_into_view(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 360.0)  # Full rotation per second
        # Point at angle 90 degrees
        # At t=0.25, radar should be at 90 degrees
        result = radar.contains_point(QPointF(0, -50), 0.25)
        assert result is True


class TestRadarContainsPointDuringInterval:
    """Test contains_point_during_interval method."""

    def test_point_in_range_not_in_sector_no_sweep(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 0.0)  # No rotation
        # Point outside initial sector
        result = radar.contains_point_during_interval(QPointF(0, -50), 0.0, 1.0)
        assert result is False

    def test_full_sweep_catches_point(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 360.0)
        # Full rotation in 1 second should catch any point in range
        result = radar.contains_point_during_interval(QPointF(0, -50), 0.0, 1.0)
        assert result is True

    def test_out_of_range_never_detected(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 360.0)
        result = radar.contains_point_during_interval(QPointF(150, 0), 0.0, 10.0)
        assert result is False

    def test_tracking_always_sees_point(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 36.0)
        radar.tracked_target = "target"
        result = radar.contains_point_during_interval(QPointF(50, 0), 0.0, 1.0)
        assert result is True

    def test_zero_duration_uses_end_time(self):
        radar = Radar("Test", (0, 0), 100.0, 30.0, 0.0, start_angle=0.0)
        result = radar.contains_point_during_interval(QPointF(50, 0), 1.0, 1.0)
        assert result is True


class TestRadarSerialization:
    """Test to_dict and from_dict methods."""

    def test_to_dict(self):
        radar = Radar("Test", (10, 20), 150.0, 45.0, 72.0, start_angle=30.0)
        d = radar.to_dict()
        assert d["name"] == "Test"
        assert d["center"] == (10.0, 20.0)
        assert d["max_range"] == 150.0
        assert d["view_angle"] == 45.0
        assert d["rotation_speed"] == 72.0
        assert d["start_angle"] == 30.0

    def test_from_dict(self):
        d = {
            "name": "Restored",
            "center": (5, 10),
            "max_range": 200.0,
            "view_angle": 60.0,
            "rotation_speed": 180.0,
            "start_angle": 90.0
        }
        radar = Radar.from_dict(d)
        assert radar.name == "Restored"
        assert radar.center.x() == 5
        assert radar.center.y() == 10
        assert radar.max_range == 200.0
        assert radar.view_angle == 60.0
        assert radar.rotation_speed == 180.0
        assert radar.start_angle == 90.0

    def test_roundtrip(self):
        original = Radar("Original", (100, 200), 300.0, 45.0, 90.0, start_angle=15.0)
        restored = Radar.from_dict(original.to_dict())
        
        assert restored.name == original.name
        assert restored.center.x() == original.center.x()
        assert restored.center.y() == original.center.y()
        assert restored.max_range == original.max_range
        assert restored.view_angle == original.view_angle
        assert restored.rotation_speed == original.rotation_speed
        assert restored.start_angle == original.start_angle
