"""Tests for missile module."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt6.QtCore import QPointF
from missile import Missile, predict_intercept_point, _distance, _solve_intercept_time


class TestDistance:
    """Test _distance helper function."""

    def test_zero_distance(self):
        p1 = QPointF(0, 0)
        p2 = QPointF(0, 0)
        assert _distance(p1, p2) == 0.0

    def test_horizontal_distance(self):
        p1 = QPointF(0, 0)
        p2 = QPointF(3, 4)
        assert _distance(p1, p2) == 5.0

    def test_vertical_distance(self):
        p1 = QPointF(0, 0)
        p2 = QPointF(0, 10)
        assert _distance(p1, p2) == 10.0


class TestSolveInterceptTime:
    """Test _solve_intercept_time function."""

    def test_zero_missile_speed_returns_none(self):
        result = _solve_intercept_time(QPointF(0, 0), 0, QPointF(10, 0), QPointF(0, 0))
        assert result is None

    def test_target_at_missile_position(self):
        result = _solve_intercept_time(QPointF(0, 0), 10.0, QPointF(0, 0), QPointF(0, 0))
        assert result == 0.0

    def test_stationary_target(self):
        # Target at distance 100, missile speed 10 -> time = 10
        result = _solve_intercept_time(QPointF(0, 0), 10.0, QPointF(100, 0), QPointF(0, 0))
        assert abs(result - 10.0) < 0.001

    def test_moving_target_away(self):
        # Target moving away at 5 m/s from position 100, missile at 10 m/s
        # Should take longer than 10 seconds
        result = _solve_intercept_time(QPointF(0, 0), 10.0, QPointF(100, 0), QPointF(5, 0))
        assert result > 10.0

    def test_impossible_intercept(self):
        # Target moving away faster than missile can catch up
        result = _solve_intercept_time(QPointF(0, 0), 5.0, QPointF(100, 0), QPointF(10, 0))
        assert result is None


class TestPredictInterceptPoint:
    """Test predict_intercept_point function."""

    def test_stationary_target(self):
        missile_pos = QPointF(0, 0)
        target_pos = QPointF(100, 0)
        target_vel = QPointF(0, 0)
        
        predicted_pos, intercept_time = predict_intercept_point(missile_pos, 10.0, target_pos, target_vel)
        
        assert abs(predicted_pos.x() - 100.0) < 0.001
        assert abs(predicted_pos.y()) < 0.001
        assert abs(intercept_time - 10.0) < 0.001

    def test_moving_target_perpendicular(self):
        missile_pos = QPointF(0, 0)
        target_pos = QPointF(0, 100)
        target_vel = QPointF(10, 0)
        
        predicted_pos, intercept_time = predict_intercept_point(missile_pos, 20.0, target_pos, target_vel)
        
        # Should predict a point ahead of current target position
        assert predicted_pos.x() > 0

    def test_zero_missile_speed(self):
        missile_pos = QPointF(0, 0)
        target_pos = QPointF(100, 0)
        target_vel = QPointF(0, 0)
        
        predicted_pos, intercept_time = predict_intercept_point(missile_pos, 0, target_pos, target_vel)
        
        # Should return target position with zero time
        assert abs(predicted_pos.x() - 100.0) < 0.001
        assert intercept_time == 0.0


class TestMissileInit:
    """Test Missile initialization."""

    def test_basic_init(self):
        from trajectory import Trajectory
        traj = Trajectory("Target")
        traj.add_point(QPointF(100, 0))
        traj.add_point(QPointF(200, 0))
        traj.compute_segments()
        
        missile = Missile(
            start_pos=QPointF(0, 0),
            target_traj=traj,
            target_pos=QPointF(100, 0),
            speed=100.0,
            lifetime=10.0,
            creation_time=0.0,
        )
        
        assert missile.pos.x() == 0
        assert missile.pos.y() == 0
        assert missile.speed == 100.0
        assert missile.lifetime == 10.0
        assert missile.creation_time == 0.0
        assert missile.is_dead is False
        assert missile.hit_target is False
        assert missile.missed_target is False

    def test_hit_radius_constant(self):
        assert Missile.HIT_RADIUS == 5.0

    def test_proximity_fuse_radius_constant(self):
        assert Missile.PROXIMITY_FUSE_RADIUS == 10.0

    def test_initial_last_known_target_velocity(self):
        from trajectory import Trajectory
        traj = Trajectory("Target")
        traj.add_point(QPointF(100, 0))
        traj.add_point(QPointF(200, 0))
        traj.compute_segments()
        
        missile = Missile(
            start_pos=QPointF(0, 0),
            target_traj=traj,
            target_pos=QPointF(100, 0),
            speed=100.0,
            lifetime=10.0,
            creation_time=0.0,
            target_velocity=QPointF(10, 0),
        )
        
        assert missile.last_known_target_velocity.x() == 10
        assert missile.last_known_target_velocity.y() == 0

    def test_meters_per_pixel_minimum(self):
        from trajectory import Trajectory
        traj = Trajectory("Target")
        traj.add_point(QPointF(100, 0))
        
        missile = Missile(
            start_pos=QPointF(0, 0),
            target_traj=traj,
            target_pos=QPointF(100, 0),
            speed=100.0,
            lifetime=10.0,
            creation_time=0.0,
            meters_per_pixel=0.01,  # Below minimum
        )
        
        assert missile.meters_per_pixel >= 0.1


class TestMissileUpdate:
    """Test Missile update method."""

    def test_does_not_update_when_dead(self):
        from trajectory import Trajectory
        traj = Trajectory("Target")
        traj.add_point(QPointF(100, 0))
        traj.add_point(QPointF(200, 0))
        traj.compute_segments()
        
        missile = Missile(
            start_pos=QPointF(0, 0),
            target_traj=traj,
            target_pos=QPointF(100, 0),
            speed=100.0,
            lifetime=10.0,
            creation_time=0.0,
        )
        missile.is_dead = True
        initial_pos = QPointF(missile.pos)
        
        missile.update(0.1, 0.1, [], [])
        
        assert missile.pos.x() == initial_pos.x()
        assert missile.pos.y() == initial_pos.y()

    def test_dies_when_target_destroyed(self):
        from trajectory import Trajectory
        traj = Trajectory("Target")
        traj.add_point(QPointF(100, 0))
        traj.add_point(QPointF(200, 0))
        traj.compute_segments()
        traj.is_destroyed = True
        
        missile = Missile(
            start_pos=QPointF(0, 0),
            target_traj=traj,
            target_pos=QPointF(100, 0),
            speed=100.0,
            lifetime=10.0,
            creation_time=0.0,
        )
        
        missile.update(0.1, 0.1, [], [])
        
        assert missile.is_dead is True

    def test_moves_toward_target(self):
        from trajectory import Trajectory
        traj = Trajectory("Target")
        traj.add_point(QPointF(1000, 0))
        traj.add_point(QPointF(1000, 0))  # Stationary
        traj.compute_segments()
        
        missile = Missile(
            start_pos=QPointF(0, 0),
            target_traj=traj,
            target_pos=QPointF(1000, 0),
            speed=100.0,
            lifetime=10.0,
            creation_time=0.0,
        )
        
        initial_pos = QPointF(missile.pos)
        missile.update(0.1, 0.1, [], [])
        
        # Should have moved toward target (positive x direction)
        assert missile.pos.x() > initial_pos.x()

    def test_hits_target(self):
        from trajectory import Trajectory
        traj = Trajectory("Target")
        traj.add_point(QPointF(50, 0))
        traj.add_point(QPointF(50, 0))  # Stationary close target
        traj.compute_segments()
        
        missile = Missile(
            start_pos=QPointF(0, 0),
            target_traj=traj,
            target_pos=QPointF(50, 0),
            speed=1000.0,  # Fast missile
            lifetime=10.0,
            creation_time=0.0,
        )
        
        # Update until hit
        for i in range(100):
            missile.update(0.1, i * 0.1, [], [traj])
            if missile.hit_target:
                break
        
        assert missile.hit_target is True
        assert missile.is_dead is True
        assert traj.is_destroyed is True


class TestMissileHitCurrentTarget:
    """Test _hit_current_target method."""

    def test_missile_at_target_position(self):
        from trajectory import Trajectory
        traj = Trajectory("Target")
        traj.add_point(QPointF(100, 0))
        
        missile = Missile(
            start_pos=QPointF(0, 0),
            target_traj=traj,
            target_pos=QPointF(100, 0),
            speed=100.0,
            lifetime=10.0,
            creation_time=0.0,
        )
        
        # Test with missile and target at same position
        result = missile._hit_current_target(
            QPointF(50, 0),  # missile_start
            QPointF(50, 0),  # missile_end
            QPointF(50, 0),  # target_start
            QPointF(50, 0),  # target_end
        )
        assert result is True

    def test_missile_within_proximity_fuse(self):
        from trajectory import Trajectory
        traj = Trajectory("Target")
        traj.add_point(QPointF(100, 0))
        
        missile = Missile(
            start_pos=QPointF(0, 0),
            target_traj=traj,
            target_pos=QPointF(100, 0),
            speed=100.0,
            lifetime=10.0,
            creation_time=0.0,
        )
        
        # Test with missile very close to target path
        result = missile._hit_current_target(
            QPointF(0, 0),
            QPointF(10, 0),
            QPointF(5, 0),
            QPointF(5, 0),
        )
        assert result is True

    def test_missile_misses_target(self):
        from trajectory import Trajectory
        traj = Trajectory("Target")
        traj.add_point(QPointF(100, 0))
        
        missile = Missile(
            start_pos=QPointF(0, 0),
            target_traj=traj,
            target_pos=QPointF(100, 0),
            speed=100.0,
            lifetime=10.0,
            creation_time=0.0,
        )
        
        # Test with missile far from target
        result = missile._hit_current_target(
            QPointF(0, 0),
            QPointF(10, 0),
            QPointF(100, 100),
            QPointF(100, 100),
        )
        assert result is False


class TestMissileDistance:
    """Test _distance static method."""

    def test_zero_distance(self):
        a = QPointF(0, 0)
        b = QPointF(0, 0)
        assert Missile._distance(a, b) == 0.0

    def test_pythagorean_distance(self):
        a = QPointF(0, 0)
        b = QPointF(3, 4)
        assert Missile._distance(a, b) == 5.0
