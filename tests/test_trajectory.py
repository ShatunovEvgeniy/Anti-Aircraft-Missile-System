"""Tests for trajectory module."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt6.QtCore import QPointF
from trajectory import Trajectory


class TestTrajectoryInit:
    """Test Trajectory initialization."""

    def test_default_name(self):
        traj = Trajectory()
        assert traj.name == "Траектория"

    def test_custom_name(self):
        traj = Trajectory(name="Test")
        assert traj.name == "Test"

    def test_default_speed(self):
        traj = Trajectory()
        assert traj.speed == 200.0

    def test_custom_speed(self):
        traj = Trajectory(speed=100.0)
        assert traj.speed == 100.0

    def test_default_color_random(self):
        traj = Trajectory()
        assert traj.color is not None
        assert 0 <= traj.color.red() <= 255
        assert 0 <= traj.color.green() <= 255
        assert 0 <= traj.color.blue() <= 255

    def test_custom_color(self):
        from PyQt6.QtGui import QColor
        color = QColor(255, 0, 0)
        traj = Trajectory(color=color)
        assert traj.color.red() == 255
        assert traj.color.green() == 0
        assert traj.color.blue() == 0

    def test_initial_points_empty(self):
        traj = Trajectory()
        assert len(traj.points) == 0

    def test_initial_segments_empty(self):
        traj = Trajectory()
        assert len(traj.segments) == 0

    def test_initial_length_zero(self):
        traj = Trajectory()
        assert traj.total_length == 0.0

    def test_initial_travel_time_infinity(self):
        traj = Trajectory()
        assert traj.travel_time == float('inf')

    def test_not_destroyed_initially(self):
        traj = Trajectory()
        assert traj.is_destroyed is False


class TestTrajectoryAddPoint:
    """Test adding points to trajectory."""

    def test_add_single_point(self):
        traj = Trajectory()
        traj.add_point(QPointF(0, 0))
        assert len(traj.points) == 1
        assert traj.points[0].x() == 0
        assert traj.points[0].y() == 0

    def test_add_multiple_points(self):
        traj = Trajectory()
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(10, 0))
        traj.add_point(QPointF(10, 10))
        assert len(traj.points) == 3

    def test_segment_created_on_second_point(self):
        traj = Trajectory()
        traj.add_point(QPointF(0, 0))
        assert len(traj.segments) == 0
        traj.add_point(QPointF(10, 0))
        assert len(traj.segments) == 1

    def test_length_calculation(self):
        traj = Trajectory()
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(3, 4))
        assert traj.total_length == 5.0

    def test_travel_time_calculation(self):
        traj = Trajectory(speed=10.0)
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(100, 0))
        assert traj.travel_time == 10.0


class TestTrajectoryRemovePoint:
    """Test removing points from trajectory."""

    def test_remove_from_empty(self):
        traj = Trajectory()
        result = traj.remove_last_point()
        assert result is None

    def test_remove_single_point(self):
        traj = Trajectory()
        traj.add_point(QPointF(0, 0))
        result = traj.remove_last_point()
        assert result.x() == 0
        assert result.y() == 0
        assert len(traj.points) == 0

    def test_remove_updates_length(self):
        traj = Trajectory()
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(10, 0))
        assert traj.total_length == 10.0
        traj.remove_last_point()
        assert traj.total_length == 0.0

    def test_remove_updates_segments(self):
        traj = Trajectory()
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(10, 0))
        traj.add_point(QPointF(10, 10))
        assert len(traj.segments) == 2
        traj.remove_last_point()
        assert len(traj.segments) == 1


class TestTrajectoryComputeSegments:
    """Test compute_segments method."""

    def test_empty_points(self):
        traj = Trajectory()
        traj.compute_segments()
        assert len(traj.segments) == 0
        assert traj.total_length == 0.0
        assert traj.travel_time == float('inf')

    def test_single_point(self):
        traj = Trajectory()
        traj.add_point(QPointF(0, 0))
        traj.compute_segments()
        assert len(traj.segments) == 0
        assert traj.total_length == 0.0

    def test_multiple_points(self):
        traj = Trajectory()
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(10, 0))
        traj.add_point(QPointF(10, 10))
        traj.compute_segments()
        assert len(traj.segments) == 2
        assert traj.total_length == 20.0


class TestTrajectoryGetPosition:
    """Test get_position method."""

    def test_destroyed_returns_none(self):
        traj = Trajectory()
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(10, 0))
        traj.compute_segments()
        traj.is_destroyed = True
        assert traj.get_position(0.0) is None

    def test_empty_points_returns_none(self):
        traj = Trajectory()
        assert traj.get_position(0.0) is None

    def test_time_zero_returns_first_point(self):
        traj = Trajectory()
        traj.add_point(QPointF(5, 10))
        traj.add_point(QPointF(15, 10))
        traj.compute_segments()
        pos = traj.get_position(0.0)
        assert pos.x() == 5
        assert pos.y() == 10

    def test_time_beyond_travel_returns_none(self):
        traj = Trajectory(speed=10.0)
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(100, 0))
        traj.compute_segments()
        assert traj.get_position(20.0) is None

    def test_intermediate_position(self):
        traj = Trajectory(speed=10.0)
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(100, 0))
        traj.compute_segments()
        pos = traj.get_position(5.0)
        assert pos.x() == 50.0
        assert pos.y() == 0.0


class TestTrajectoryGetPositionByT:
    """Test get_position_by_t method."""

    def test_empty_segments(self):
        traj = Trajectory()
        assert traj.get_position_by_t(0.0) is None

    def test_t_zero(self):
        traj = Trajectory()
        traj.add_point(QPointF(5, 10))
        traj.add_point(QPointF(15, 10))
        traj.compute_segments()
        pos = traj.get_position_by_t(0.0)
        assert pos.x() == 5
        assert pos.y() == 10

    def test_t_one(self):
        traj = Trajectory()
        traj.add_point(QPointF(5, 10))
        traj.add_point(QPointF(15, 10))
        traj.compute_segments()
        pos = traj.get_position_by_t(1.0)
        assert pos.x() == 15
        assert pos.y() == 10

    def test_t_half(self):
        traj = Trajectory()
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(100, 0))
        traj.compute_segments()
        pos = traj.get_position_by_t(0.5)
        assert pos.x() == 50.0
        assert pos.y() == 0.0

    def test_t_negative(self):
        traj = Trajectory()
        traj.add_point(QPointF(5, 10))
        traj.add_point(QPointF(15, 10))
        traj.compute_segments()
        pos = traj.get_position_by_t(-0.5)
        assert pos.x() == 5
        assert pos.y() == 10

    def test_t_above_one(self):
        traj = Trajectory()
        traj.add_point(QPointF(5, 10))
        traj.add_point(QPointF(15, 10))
        traj.compute_segments()
        pos = traj.get_position_by_t(1.5)
        assert pos.x() == 15
        assert pos.y() == 10


class TestTrajectoryGetVelocity:
    """Test get_velocity method."""

    def test_destroyed_returns_zero(self):
        traj = Trajectory()
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(10, 0))
        traj.compute_segments()
        traj.is_destroyed = True
        vel = traj.get_velocity(0.0)
        assert vel.x() == 0.0
        assert vel.y() == 0.0

    def test_empty_segments_returns_zero(self):
        traj = Trajectory()
        vel = traj.get_velocity(0.0)
        assert vel.x() == 0.0
        assert vel.y() == 0.0

    def test_zero_speed_returns_zero(self):
        traj = Trajectory(speed=0)
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(10, 0))
        traj.compute_segments()
        vel = traj.get_velocity(0.0)
        assert vel.x() == 0.0
        assert vel.y() == 0.0

    def test_beyond_travel_time_returns_zero(self):
        traj = Trajectory(speed=10.0)
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(100, 0))
        traj.compute_segments()
        vel = traj.get_velocity(20.0)
        assert vel.x() == 0.0
        assert vel.y() == 0.0

    def test_velocity_magnitude(self):
        traj = Trajectory(speed=10.0)
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(100, 0))
        traj.compute_segments()
        vel = traj.get_velocity(0.0)
        import math
        magnitude = math.hypot(vel.x(), vel.y())
        assert abs(magnitude - 10.0) < 0.001


class TestTrajectorySetSpeed:
    """Test set_speed method."""

    def test_set_positive_speed(self):
        traj = Trajectory()
        traj.set_speed(50.0)
        assert traj.speed == 50.0

    def test_set_zero_speed_becomes_minimum(self):
        traj = Trajectory()
        traj.set_speed(0.0)
        assert traj.speed == 0.001

    def test_set_negative_speed_becomes_minimum(self):
        traj = Trajectory()
        traj.set_speed(-10.0)
        assert traj.speed == 0.001

    def test_updates_travel_time(self):
        traj = Trajectory()
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(100, 0))
        traj.compute_segments()
        traj.set_speed(10.0)
        assert traj.travel_time == 10.0


class TestTrajectoryResetState:
    """Test reset_simulation_state method."""

    def test_resets_destroyed_flag(self):
        traj = Trajectory()
        traj.is_destroyed = True
        traj.reset_simulation_state()
        assert traj.is_destroyed is False


class TestTrajectorySerialization:
    """Test to_dict and from_dict methods."""

    def test_to_dict(self):
        from PyQt6.QtGui import QColor
        traj = Trajectory(name="Test", color=QColor(255, 128, 64), speed=150.0)
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(10, 20))
        d = traj.to_dict()
        assert d["name"] == "Test"
        assert d["speed"] == 150.0
        assert d["color"]["r"] == 255
        assert d["color"]["g"] == 128
        assert d["color"]["b"] == 64
        assert len(d["points"]) == 2
        assert d["points"][0] == (0.0, 0.0)
        assert d["points"][1] == (10.0, 20.0)

    def test_from_dict(self):
        d = {
            "name": "Restored",
            "color": {"r": 100, "g": 150, "b": 200},
            "speed": 75.0,
            "points": [(0, 0), (30, 40)]
        }
        traj = Trajectory.from_dict(d)
        assert traj.name == "Restored"
        assert traj.speed == 75.0
        assert traj.color.red() == 100
        assert traj.color.green() == 150
        assert traj.color.blue() == 200
        assert len(traj.points) == 2
        assert traj.total_length == 50.0

    def test_roundtrip(self):
        from PyQt6.QtGui import QColor
        original = Trajectory(name="RoundTrip", color=QColor(50, 100, 150), speed=200.0)
        original.add_point(QPointF(0, 0))
        original.add_point(QPointF(10, 0))
        original.add_point(QPointF(10, 10))
        original.compute_segments()
        
        restored = Trajectory.from_dict(original.to_dict())
        
        assert restored.name == original.name
        assert restored.speed == original.speed
        assert restored.color.red() == original.color.red()
        assert restored.color.green() == original.color.green()
        assert restored.color.blue() == original.color.blue()
        assert len(restored.points) == len(original.points)
        assert restored.total_length == original.total_length


class TestTrajectoryMotionErrorKey:
    """Test motion error key generation."""

    def test_key_updated_on_add_point(self):
        traj = Trajectory(name="Test")
        initial_key = traj.motion_error_key
        traj.add_point(QPointF(0, 0))
        assert traj.motion_error_key != initial_key

    def test_key_updated_on_remove_point(self):
        traj = Trajectory(name="Test")
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(10, 0))
        initial_key = traj.motion_error_key
        traj.remove_last_point()
        assert traj.motion_error_key != initial_key

    def test_key_updated_on_set_speed(self):
        traj = Trajectory(name="Test")
        traj.add_point(QPointF(0, 0))
        traj.add_point(QPointF(10, 0))
        initial_key = traj.motion_error_key
        traj.set_speed(50.0)
        assert traj.motion_error_key != initial_key

    def test_refresh_method(self):
        traj = Trajectory(name="Test")
        traj.add_point(QPointF(0, 0))
        key1 = traj.motion_error_key
        traj.refresh_motion_error_key()
        key2 = traj.motion_error_key
        assert key1 == key2
