"""Tests for launchpad module."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt6.QtCore import QPointF
from launchpad import LaunchPad


class TestLaunchPadInit:
    """Test LaunchPad initialization."""

    def test_basic_init(self):
        pad = LaunchPad("Test", (0, 0))
        assert pad.name == "Test"
        assert pad.center.x() == 0
        assert pad.center.y() == 0
        assert pad.missile_speed == 200.0
        assert pad.launch_range == 200.0
        assert pad.missile_lifetime == 5.0
        assert len(pad.missiles) == 0
        assert len(pad.miss_markers) == 0

    def test_custom_parameters(self):
        pad = LaunchPad("Custom", (10, 20), missile_speed=300.0, launch_range=250.0, missile_lifetime=8.0)
        assert pad.name == "Custom"
        assert pad.center.x() == 10
        assert pad.center.y() == 20
        assert pad.missile_speed == 300.0
        assert pad.launch_range == 250.0
        assert pad.missile_lifetime == 8.0

    def test_center_from_qpointf(self):
        center = QPointF(50, 75)
        pad = LaunchPad("Test", center)
        assert pad.center.x() == 50
        assert pad.center.y() == 75

    def test_center_from_list(self):
        pad = LaunchPad("Test", [10, 20])
        assert pad.center.x() == 10
        assert pad.center.y() == 20


class TestLaunchPadGetDistance:
    """Test get_distance static method."""

    def test_zero_distance(self):
        p1 = QPointF(0, 0)
        p2 = QPointF(0, 0)
        assert LaunchPad.get_distance(p1, p2) == 0.0

    def test_horizontal_distance(self):
        p1 = QPointF(0, 0)
        p2 = QPointF(3, 4)
        assert LaunchPad.get_distance(p1, p2) == 5.0

    def test_vertical_distance(self):
        p1 = QPointF(0, 0)
        p2 = QPointF(0, 10)
        assert LaunchPad.get_distance(p1, p2) == 10.0


class TestLaunchPadCanLaunch:
    """Test can_launch method."""

    def test_target_in_range(self):
        pad = LaunchPad("Test", (0, 0), launch_range=100.0)
        assert pad.can_launch(QPointF(50, 0)) is True

    def test_target_at_range(self):
        pad = LaunchPad("Test", (0, 0), launch_range=100.0)
        assert pad.can_launch(QPointF(100, 0)) is True

    def test_target_out_of_range(self):
        pad = LaunchPad("Test", (0, 0), launch_range=100.0)
        assert pad.can_launch(QPointF(150, 0)) is False

    def test_target_diagonal(self):
        pad = LaunchPad("Test", (0, 0), launch_range=100.0)
        # Distance = sqrt(60^2 + 80^2) = 100
        assert pad.can_launch(QPointF(60, 80)) is True


class TestLaunchPadLaunchMissile:
    """Test launch_missile method."""

    def test_launches_missile(self):
        from trajectory import Trajectory
        pad = LaunchPad("Test", (0, 0))
        traj = Trajectory("Target")
        traj.add_point(QPointF(100, 0))
        traj.add_point(QPointF(200, 0))
        traj.compute_segments()
        
        initial_count = len(pad.missiles)
        pad.launch_missile(traj, QPointF(100, 0), 0.0)
        assert len(pad.missiles) == initial_count + 1

    def test_missile_starts_at_pad_center(self):
        from trajectory import Trajectory
        pad = LaunchPad("Test", (50, 100))
        traj = Trajectory("Target")
        traj.add_point(QPointF(100, 0))
        traj.add_point(QPointF(200, 0))
        traj.compute_segments()
        
        pad.launch_missile(traj, QPointF(100, 0), 0.0)
        missile = pad.missiles[0]
        assert missile.pos.x() == 50
        assert missile.pos.y() == 100

    def test_missile_has_correct_speed(self):
        from trajectory import Trajectory
        pad = LaunchPad("Test", (0, 0), missile_speed=300.0)
        traj = Trajectory("Target")
        traj.add_point(QPointF(100, 0))
        traj.add_point(QPointF(200, 0))
        traj.compute_segments()
        
        pad.launch_missile(traj, QPointF(100, 0), 0.0)
        missile = pad.missiles[0]
        assert missile.speed == 300.0

    def test_missile_has_correct_lifetime(self):
        from trajectory import Trajectory
        pad = LaunchPad("Test", (0, 0), missile_lifetime=10.0)
        traj = Trajectory("Target")
        traj.add_point(QPointF(100, 0))
        traj.add_point(QPointF(200, 0))
        traj.compute_segments()
        
        pad.launch_missile(traj, QPointF(100, 0), 0.0)
        missile = pad.missiles[0]
        assert missile.lifetime == 10.0


class TestLaunchPadUpdateMissiles:
    """Test update_missiles method."""

    def test_returns_empty_list_when_no_missiles(self):
        pad = LaunchPad("Test", (0, 0))
        events = pad.update_missiles(0.1, 0.0, [], [])
        assert events == []

    def test_updates_missile_position(self):
        from trajectory import Trajectory
        pad = LaunchPad("Test", (0, 0), missile_speed=100.0)
        traj = Trajectory("Target")
        traj.add_point(QPointF(1000, 0))
        traj.add_point(QPointF(1000, 0))  # Stationary target
        traj.compute_segments()
        
        pad.launch_missile(traj, QPointF(1000, 0), 0.0)
        initial_pos = QPointF(pad.missiles[0].pos)
        
        pad.update_missiles(0.1, 0.1, [], [])
        
        # Missile should have moved
        final_pos = pad.missiles[0].pos
        distance_moved = LaunchPad.get_distance(initial_pos, final_pos)
        assert distance_moved > 0

    def test_generates_target_destroyed_event(self):
        from trajectory import Trajectory
        pad = LaunchPad("Test", (0, 0), missile_speed=1000.0)
        traj = Trajectory("Target")
        traj.add_point(QPointF(50, 0))
        traj.add_point(QPointF(50, 0))
        traj.compute_segments()
        
        pad.launch_missile(traj, QPointF(50, 0), 0.0)
        
        # Update until missile hits
        for i in range(100):
            events = pad.update_missiles(0.1, i * 0.1, [], [traj])
            if events:
                assert any(e[0] == "target_destroyed" for e in events)
                break

    def test_removes_dead_missiles(self):
        from trajectory import Trajectory
        pad = LaunchPad("Test", (0, 0), missile_speed=1000.0)
        traj = Trajectory("Target")
        traj.add_point(QPointF(50, 0))
        traj.add_point(QPointF(50, 0))
        traj.compute_segments()
        
        pad.launch_missile(traj, QPointF(50, 0), 0.0)
        assert len(pad.missiles) == 1
        
        # Update until missile is removed
        for i in range(100):
            pad.update_missiles(0.1, i * 0.1, [], [traj])
            if len(pad.missiles) == 0:
                break
        
        assert len(pad.missiles) == 0


class TestLaunchPadResetState:
    """Test reset_simulation_state method."""

    def test_clears_missiles(self):
        from trajectory import Trajectory
        pad = LaunchPad("Test", (0, 0))
        traj = Trajectory("Target")
        traj.add_point(QPointF(100, 0))
        traj.add_point(QPointF(200, 0))
        traj.compute_segments()
        
        pad.launch_missile(traj, QPointF(100, 0), 0.0)
        assert len(pad.missiles) == 1
        
        pad.reset_simulation_state()
        assert len(pad.missiles) == 0

    def test_clears_miss_markers(self):
        pad = LaunchPad("Test", (0, 0))
        pad.miss_markers.append(QPointF(10, 10))
        assert len(pad.miss_markers) == 1
        
        pad.reset_simulation_state()
        assert len(pad.miss_markers) == 0


class TestLaunchPadSerialization:
    """Test to_dict and from_dict methods."""

    def test_to_dict(self):
        pad = LaunchPad("Test", (10, 20), missile_speed=300.0, launch_range=250.0, missile_lifetime=8.0)
        d = pad.to_dict()
        assert d["name"] == "Test"
        assert d["center"] == (10.0, 20.0)
        assert d["missile_speed"] == 300.0
        assert d["launch_range"] == 250.0
        assert d["missile_lifetime"] == 8.0

    def test_from_dict(self):
        d = {
            "name": "Restored",
            "center": (5, 10),
            "missile_speed": 150.0,
            "launch_range": 175.0,
            "missile_lifetime": 6.0
        }
        pad = LaunchPad.from_dict(d)
        assert pad.name == "Restored"
        assert pad.center.x() == 5
        assert pad.center.y() == 10
        assert pad.missile_speed == 150.0
        assert pad.launch_range == 175.0
        assert pad.missile_lifetime == 6.0

    def test_roundtrip(self):
        original = LaunchPad("Original", (100, 200), missile_speed=400.0, launch_range=300.0, missile_lifetime=12.0)
        restored = LaunchPad.from_dict(original.to_dict())
        
        assert restored.name == original.name
        assert restored.center.x() == original.center.x()
        assert restored.center.y() == original.center.y()
        assert restored.missile_speed == original.missile_speed
        assert restored.launch_range == original.launch_range
        assert restored.missile_lifetime == original.missile_lifetime
