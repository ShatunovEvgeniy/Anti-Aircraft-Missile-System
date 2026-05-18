import hashlib
import math

from PyQt6.QtCore import QPointF


# Временные демонстрационные амплитуды, чтобы погрешность была заметна при масштабе 500 м/пикс.
TARGET_POSITION_ERROR_M = 1000.0
MISSILE_POSITION_ERROR_M = 500.0
TARGET_ERROR_PERIOD_S = 1.5
MISSILE_ERROR_PERIOD_S = 0.35


def _stable_noise_sample(seed_key, axis, index):
    payload = f"{seed_key}|{axis}|{index}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    value = int.from_bytes(digest, "big") / float((1 << 64) - 1)
    return value * 2.0 - 1.0


def _smoothstep(value):
    return value * value * (3.0 - 2.0 * value)


def _get_position_error(seed_key, sim_time, meters_per_pixel, max_error_m, period_s):
    if meters_per_pixel <= 0 or max_error_m <= 0 or period_s <= 0:
        return QPointF(0.0, 0.0)

    scaled_amplitude = max_error_m / meters_per_pixel
    local_time = max(0.0, sim_time) / period_s
    index = math.floor(local_time)
    blend = _smoothstep(local_time - index)

    x0 = _stable_noise_sample(seed_key, "x", index)
    x1 = _stable_noise_sample(seed_key, "x", index + 1)
    y0 = _stable_noise_sample(seed_key, "y", index)
    y1 = _stable_noise_sample(seed_key, "y", index + 1)

    return QPointF(
        (x0 + (x1 - x0) * blend) * scaled_amplitude,
        (y0 + (y1 - y0) * blend) * scaled_amplitude,
    )


def get_target_position_error(seed_key, sim_time, meters_per_pixel):
    return _get_position_error(
        seed_key,
        sim_time,
        meters_per_pixel,
        TARGET_POSITION_ERROR_M,
        TARGET_ERROR_PERIOD_S,
    )


def get_missile_position_error(seed_key, sim_time, meters_per_pixel):
    return _get_position_error(
        seed_key,
        sim_time,
        meters_per_pixel,
        MISSILE_POSITION_ERROR_M,
        MISSILE_ERROR_PERIOD_S,
    )
