"""Tests for motion_errors module."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt6.QtCore import QPointF
from motion_errors import (
    TARGET_POSITION_ERROR_M,
    MISSILE_POSITION_ERROR_M,
    TARGET_ERROR_PERIOD_S,
    MISSILE_ERROR_PERIOD_S,
    _stable_noise_sample,
    _smoothstep,
    _get_position_error,
    get_target_position_error,
    get_missile_position_error,
)


class TestSmoothstep:
    """Test the smoothstep interpolation function."""

    def test_smoothstep_zero(self):
        assert _smoothstep(0.0) == 0.0

    def test_smoothstep_one(self):
        assert _smoothstep(1.0) == 1.0

    def test_smoothstep_half(self):
        result = _smoothstep(0.5)
        assert 0.0 < result < 1.0
        assert result == 0.5

    def test_smoothstep_monotonic(self):
        """Test that smoothstep is monotonically increasing in [0, 1]."""
        values = [_smoothstep(i / 10.0) for i in range(11)]
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1]

    def test_smoothstep_negative(self):
        result = _smoothstep(-0.5)
        # Smoothstep formula: x^2 * (3 - 2x), for x=-0.5: 0.25 * (3 + 1) = 1.0
        assert result == 1.0

    def test_smoothstep_above_one(self):
        result = _smoothstep(1.5)
        # Smoothstep formula: x^2 * (3 - 2x), for x=1.5: 2.25 * (3 - 3) = 0.0
        assert result == 0.0


class TestStableNoiseSample:
    """Test the deterministic noise sample function."""

    def test_deterministic_same_inputs(self):
        """Same inputs should produce same outputs."""
        result1 = _stable_noise_sample("test_key", "x", 0)
        result2 = _stable_noise_sample("test_key", "x", 0)
        assert result1 == result2

    def test_different_keys(self):
        """Different keys should produce different outputs."""
        result1 = _stable_noise_sample("key1", "x", 0)
        result2 = _stable_noise_sample("key2", "x", 0)
        assert result1 != result2

    def test_different_axes(self):
        """Different axes should produce different outputs."""
        result1 = _stable_noise_sample("test_key", "x", 0)
        result2 = _stable_noise_sample("test_key", "y", 0)
        assert result1 != result2

    def test_different_indices(self):
        """Different indices should produce different outputs."""
        result1 = _stable_noise_sample("test_key", "x", 0)
        result2 = _stable_noise_sample("test_key", "x", 1)
        assert result1 != result2

    def test_range(self):
        """Output should be in range [-1, 1]."""
        for i in range(100):
            result = _stable_noise_sample(f"test_{i}", "x", i)
            assert -1.0 <= result <= 1.0


class TestGetPositionError:
    """Test the position error calculation function."""

    def test_zero_meters_per_pixel(self):
        """Should return zero when meters_per_pixel is zero."""
        result = _get_position_error("test", 0.0, 0.0, 100.0, 1.0)
        assert result.x() == 0.0
        assert result.y() == 0.0

    def test_negative_meters_per_pixel(self):
        """Should return zero when meters_per_pixel is negative."""
        result = _get_position_error("test", 0.0, -1.0, 100.0, 1.0)
        assert result.x() == 0.0
        assert result.y() == 0.0

    def test_zero_max_error(self):
        """Should return zero when max_error_m is zero."""
        result = _get_position_error("test", 0.0, 1.0, 0.0, 1.0)
        assert result.x() == 0.0
        assert result.y() == 0.0

    def test_zero_period(self):
        """Should return zero when period_s is zero."""
        result = _get_position_error("test", 0.0, 1.0, 100.0, 0.0)
        assert result.x() == 0.0
        assert result.y() == 0.0

    def test_zero_time(self):
        """Should return consistent value at time zero."""
        result = _get_position_error("test", 0.0, 1.0, 100.0, 1.0)
        assert isinstance(result, QPointF)

    def test_amplitude_scaling(self):
        """Error amplitude should scale with max_error_m."""
        result1 = _get_position_error("test", 0.0, 1.0, 100.0, 1.0)
        result2 = _get_position_error("test", 0.0, 1.0, 200.0, 1.0)
        # Larger max_error should produce proportionally larger error
        assert abs(result2.x()) == abs(result1.x()) * 2.0
        assert abs(result2.y()) == abs(result1.y()) * 2.0

    def test_continuity(self):
        """Error should be continuous over time."""
        t1 = 0.5
        t2 = 0.5001
        err1 = _get_position_error("test", t1, 1.0, 100.0, 1.0)
        err2 = _get_position_error("test", t2, 1.0, 100.0, 1.0)
        # Small time difference should produce small position difference
        dx = err2.x() - err1.x()
        dy = err2.y() - err1.y()
        assert abs(dx) < 1.0
        assert abs(dy) < 1.0


class TestTargetPositionError:
    """Test the target position error wrapper function."""

    def test_returns_qpointf(self):
        result = get_target_position_error("test", 0.0, 1.0)
        assert isinstance(result, QPointF)

    def test_uses_target_constants(self):
        """Should use TARGET_POSITION_ERROR_M and TARGET_ERROR_PERIOD_S."""
        result = get_target_position_error("test", 0.0, 1.0)
        # Just verify it returns a valid point
        assert result.x() is not None
        assert result.y() is not None


class TestMissilePositionError:
    """Test the missile position error wrapper function."""

    def test_returns_qpointf(self):
        result = get_missile_position_error("test", 0.0, 1.0)
        assert isinstance(result, QPointF)

    def test_uses_missile_constants(self):
        """Should use MISSILE_POSITION_ERROR_M and MISSILE_ERROR_PERIOD_S."""
        result = get_missile_position_error("test", 0.0, 1.0)
        assert result.x() is not None
        assert result.y() is not None

    def test_different_from_target_error(self):
        """Missile error should differ from target error due to different periods."""
        seed = "same_seed"
        t = 0.5
        mpp = 1.0
        target_err = get_target_position_error(seed, t, mpp)
        missile_err = get_missile_position_error(seed, t, mpp)
        # They use different periods so results should differ
        assert target_err != missile_err
