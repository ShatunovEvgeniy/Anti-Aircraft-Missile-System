"""Real-world inspired defaults mapped to screen-space units.

The canvas stores geometry in pixels, so all motion inside the simulator is
expressed in pixels per second. ``METERS_PER_PIXEL`` defines how real-world
distances map onto the scene.
"""

SPEED_OF_SOUND_MPS = 340.0
METERS_PER_PIXEL = 500.0
MAX_SIMULATION_DURATION_S = 1_000_000.0
ANIMATION_INTERVAL_MS = 16
DEFAULT_PLAYBACK_SPEED = 1.0


def meters_to_pixels(distance_m):
    return distance_m / METERS_PER_PIXEL


def mps_to_pixels_per_second(speed_mps):
    return speed_mps / METERS_PER_PIXEL


DEFAULT_TARGET_NAME = "МиГ-31БМ"
# Source: Rostec article "МиГ-31БМ: птица высокого полета" lists 3000 km/h.
DEFAULT_TARGET_SPEED_KMH = 3_000.0
DEFAULT_TARGET_SPEED_MPS = DEFAULT_TARGET_SPEED_KMH / 3.6
DEFAULT_TRAJECTORY_SPEED = round(mps_to_pixels_per_second(DEFAULT_TARGET_SPEED_MPS), 2)

DEFAULT_RADAR_NAME = 'Небо-СВ'
DEFAULT_RADAR_RANGE_M = 350_000.0
DEFAULT_RADAR_RANGE = round(meters_to_pixels(DEFAULT_RADAR_RANGE_M), 2)
# Source: rusarmy.com page for the 2D duty radar "Небо-СВ".
DEFAULT_RADAR_ROTATION_PERIOD_S = 10.0
DEFAULT_RADAR_ROTATION_SPEED = round(360.0 / DEFAULT_RADAR_ROTATION_PERIOD_S, 2)
# The page lists azimuth beam width as 6 degrees.
DEFAULT_RADAR_VIEW_ANGLE = 6.0

DEFAULT_LAUNCHPAD_NAME = 'С-300ПМУ'
DEFAULT_MISSILE_RANGE_M = 150_000.0
# The cited S-300 article reports up to 2000 m/s missile speed for this family.
DEFAULT_MISSILE_SPEED_MPS = 2_000.0
DEFAULT_MISSILE_SPEED = round(mps_to_pixels_per_second(DEFAULT_MISSILE_SPEED_MPS), 2)
DEFAULT_LAUNCH_RANGE = round(meters_to_pixels(DEFAULT_MISSILE_RANGE_M), 2)
DEFAULT_MISSILE_LIFETIME = round(DEFAULT_MISSILE_RANGE_M / DEFAULT_MISSILE_SPEED_MPS, 1)
