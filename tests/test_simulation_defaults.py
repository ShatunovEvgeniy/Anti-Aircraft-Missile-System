"""Tests for simulation_defaults module."""
import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulation_defaults import (
    SPEED_OF_SOUND_MPS,
    METERS_PER_PIXEL,
    MAX_SIMULATION_DURATION_S,
    ANIMATION_INTERVAL_MS,
    DEFAULT_PLAYBACK_SPEED,
    meters_to_pixels,
    mps_to_pixels_per_second,
    DEFAULT_TARGET_NAME,
    DEFAULT_TARGET_SPEED_KMH,
    DEFAULT_TARGET_SPEED_MPS,
    DEFAULT_TRAJECTORY_SPEED,
    DEFAULT_RADAR_NAME,
    DEFAULT_RADAR_RANGE_M,
    DEFAULT_RADAR_RANGE,
    DEFAULT_RADAR_ROTATION_PERIOD_S,
    DEFAULT_RADAR_ROTATION_SPEED,
    DEFAULT_RADAR_VIEW_ANGLE,
    DEFAULT_LAUNCHPAD_NAME,
    DEFAULT_MISSILE_RANGE_M,
    DEFAULT_MISSILE_SPEED_MPS,
    DEFAULT_MISSILE_SPEED,
    DEFAULT_LAUNCH_RANGE,
    DEFAULT_MISSILE_LIFETIME,
)


class TestConstants:
    """Test that constants are properly defined."""

    def test_speed_of_sound(self):
        assert SPEED_OF_SOUND_MPS == 340.0

    def test_meters_per_pixel(self):
        assert METERS_PER_PIXEL == 500.0

    def test_max_simulation_duration(self):
        assert MAX_SIMULATION_DURATION_S == 1_000_000.0

    def test_animation_interval(self):
        assert ANIMATION_INTERVAL_MS == 16

    def test_default_playback_speed(self):
        assert DEFAULT_PLAYBACK_SPEED == 1.0


class TestConversionFunctions:
    """Test unit conversion functions."""

    def test_meters_to_pixels_zero(self):
        assert meters_to_pixels(0) == 0.0

    def test_meters_to_pixels_positive(self):
        assert meters_to_pixels(500.0) == 1.0

    def test_meters_to_pixels_negative(self):
        assert meters_to_pixels(-500.0) == -1.0

    def test_meters_to_pixels_large_value(self):
        assert meters_to_pixels(1000.0) == 2.0

    def test_mps_to_pixels_per_second_zero(self):
        assert mps_to_pixels_per_second(0) == 0.0

    def test_mps_to_pixels_per_second_positive(self):
        assert mps_to_pixels_per_second(500.0) == 1.0

    def test_mps_to_pixels_per_second_sound_speed(self):
        expected = SPEED_OF_SOUND_MPS / METERS_PER_PIXEL
        assert mps_to_pixels_per_second(SPEED_OF_SOUND_MPS) == expected


class TestDefaultValues:
    """Test default value calculations."""

    def test_target_speed_conversion(self):
        # 3000 km/h = 3000/3.6 m/s
        expected = 3000.0 / 3.6
        assert DEFAULT_TARGET_SPEED_MPS == expected

    def test_trajectory_speed_calculation(self):
        expected = round(DEFAULT_TARGET_SPEED_MPS / METERS_PER_PIXEL, 2)
        assert DEFAULT_TRAJECTORY_SPEED == expected

    def test_radar_range_conversion(self):
        expected = round(DEFAULT_RADAR_RANGE_M / METERS_PER_PIXEL, 2)
        assert DEFAULT_RADAR_RANGE == expected

    def test_radar_rotation_speed(self):
        expected = round(360.0 / DEFAULT_RADAR_ROTATION_PERIOD_S, 2)
        assert DEFAULT_RADAR_ROTATION_SPEED == expected

    def test_missile_speed_conversion(self):
        expected = round(DEFAULT_MISSILE_SPEED_MPS / METERS_PER_PIXEL, 2)
        assert DEFAULT_MISSILE_SPEED == expected

    def test_missile_lifetime_calculation(self):
        expected = round(DEFAULT_MISSILE_RANGE_M / DEFAULT_MISSILE_SPEED_MPS, 1)
        assert DEFAULT_MISSILE_LIFETIME == expected

    def test_launch_range_conversion(self):
        expected = round(DEFAULT_MISSILE_RANGE_M / METERS_PER_PIXEL, 2)
        assert DEFAULT_LAUNCH_RANGE == expected


class TestDefaultNames:
    """Test default name constants."""

    def test_target_name(self):
        assert DEFAULT_TARGET_NAME == "МиГ-31БМ"

    def test_radar_name(self):
        assert DEFAULT_RADAR_NAME == 'Небо-СВ'

    def test_launchpad_name(self):
        assert DEFAULT_LAUNCHPAD_NAME == 'С-300ПМУ'
