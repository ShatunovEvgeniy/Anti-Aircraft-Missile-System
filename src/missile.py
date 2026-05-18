import math

from PyQt6.QtCore import QPointF

from motion_errors import get_missile_position_error


def _distance(p1, p2):
    return math.hypot(p2.x() - p1.x(), p2.y() - p1.y())


def _solve_intercept_time(missile_pos, missile_speed, target_pos, target_velocity):
    if missile_speed <= 0:
        return None

    rx = target_pos.x() - missile_pos.x()
    ry = target_pos.y() - missile_pos.y()
    vx = target_velocity.x()
    vy = target_velocity.y()

    a = vx * vx + vy * vy - missile_speed * missile_speed
    b = 2.0 * (rx * vx + ry * vy)
    c = rx * rx + ry * ry

    if c == 0:
        return 0.0

    if abs(a) < 1e-9:
        if abs(b) < 1e-9:
            return None
        t = -c / b
        return t if t >= 0 else None

    discriminant = b * b - 4.0 * a * c
    if discriminant < 0:
        return None

    sqrt_discriminant = math.sqrt(discriminant)
    candidates = [
        (-b - sqrt_discriminant) / (2.0 * a),
        (-b + sqrt_discriminant) / (2.0 * a),
    ]
    positive_times = [t for t in candidates if t >= 0]
    if not positive_times:
        return None
    return min(positive_times)


def predict_intercept_point(
    missile_pos,
    missile_speed,
    target_pos,
    target_velocity,
    max_iterations=3,
):
    intercept_time = _solve_intercept_time(missile_pos, missile_speed, target_pos, target_velocity)
    if intercept_time is None:
        intercept_time = _distance(missile_pos, target_pos) / missile_speed if missile_speed > 0 else 0.0

    intercept_time = max(0.0, intercept_time)
    predicted_pos = QPointF(target_pos)

    for _ in range(max_iterations):
        predicted_pos = QPointF(
            target_pos.x() + target_velocity.x() * intercept_time,
            target_pos.y() + target_velocity.y() * intercept_time,
        )

        if missile_speed <= 0:
            break

        new_intercept_time = _distance(missile_pos, predicted_pos) / missile_speed
        if abs(new_intercept_time - intercept_time) < 1e-3:
            intercept_time = new_intercept_time
            break
        intercept_time = new_intercept_time

    return QPointF(predicted_pos), intercept_time


class Missile:
    HIT_RADIUS = 5.0
    PROXIMITY_FUSE_RADIUS = 10.0

    def __init__(
        self,
        start_pos,
        target_traj,
        target_pos,
        speed,
        lifetime,
        creation_time,
        target_velocity=None,
        meters_per_pixel=1.0,
    ):
        self.pos = QPointF(start_pos)
        self.target_traj = target_traj
        self.target_pos = QPointF(target_pos)
        self.speed = speed
        self.lifetime = lifetime
        self.creation_time = creation_time
        self.last_update_time = creation_time
        self.is_dead = False
        self.hit_target = False
        self.missed_target = False
        self.miss_pos = None
        self.last_known_target_pos = QPointF(target_pos)
        self.last_known_target_velocity = (
            QPointF(target_velocity) if target_velocity is not None else QPointF(0.0, 0.0)
        )
        self.meters_per_pixel = max(0.1, meters_per_pixel)
        self.motion_error_key = (
            f"{self.target_traj.name}|{creation_time:.6f}|"
            f"{start_pos.x():.3f}:{start_pos.y():.3f}|{speed:.6f}"
        )
        self.last_motion_error = get_missile_position_error(
            self.motion_error_key,
            creation_time,
            self.meters_per_pixel,
        )

    def update(self, dt, current_time, radars, trajectories):
        if self.is_dead:
            return

        if self.target_traj.is_destroyed:
            self.is_dead = True
            return

        previous_time = max(self.creation_time, current_time - dt)
        current_target_pos = self.target_traj.get_position(current_time)
        previous_target_pos = self.target_traj.get_position(previous_time)
        observed_target_pos = self.target_traj.get_observed_position(current_time, self.meters_per_pixel)

        target_visible = False
        if observed_target_pos is not None:
            target_visible = any(
                radar.contains_point_during_interval(observed_target_pos, previous_time, current_time)
                for radar in radars
            )

        if target_visible:
            self.last_known_target_pos = QPointF(observed_target_pos)
            self.last_known_target_velocity = QPointF(self.target_traj.get_velocity(current_time))
            self.last_update_time = current_time
        elif current_time - self.last_update_time > self.lifetime:
            self.is_dead = True
            return

        time_since_last_update = max(0.0, current_time - self.last_update_time)
        estimated_target_pos = QPointF(
            self.last_known_target_pos.x() + self.last_known_target_velocity.x() * time_since_last_update,
            self.last_known_target_pos.y() + self.last_known_target_velocity.y() * time_since_last_update,
        )
        self.target_pos, _ = predict_intercept_point(
            self.pos,
            self.speed,
            estimated_target_pos,
            self.last_known_target_velocity,
        )

        dx = self.target_pos.x() - self.pos.x()
        dy = self.target_pos.y() - self.pos.y()
        dist = math.hypot(dx, dy)

        previous_pos = QPointF(self.pos)
        step = min(dt * self.speed, dist)
        if dist > 0:
            self.pos += QPointF(dx / dist * step, dy / dist * step)

        current_motion_error = get_missile_position_error(
            self.motion_error_key,
            current_time,
            self.meters_per_pixel,
        )
        self.pos += QPointF(
            current_motion_error.x() - self.last_motion_error.x(),
            current_motion_error.y() - self.last_motion_error.y(),
        )
        self.last_motion_error = current_motion_error

        if current_target_pos is not None and self._hit_current_target(
            previous_pos,
            self.pos,
            previous_target_pos if previous_target_pos is not None else current_target_pos,
            current_target_pos,
        ):
            self.target_traj.is_destroyed = True
            self.hit_target = True
            self.is_dead = True

    def _hit_current_target(self, missile_start, missile_end, target_start, target_end):
        relative_start = QPointF(
            missile_start.x() - target_start.x(),
            missile_start.y() - target_start.y(),
        )
        relative_velocity = QPointF(
            (missile_end.x() - missile_start.x()) - (target_end.x() - target_start.x()),
            (missile_end.y() - missile_start.y()) - (target_end.y() - target_start.y()),
        )
        relative_speed_sq = (
            relative_velocity.x() * relative_velocity.x()
            + relative_velocity.y() * relative_velocity.y()
        )
        if relative_speed_sq == 0:
            return self._distance(missile_end, target_end) <= self.PROXIMITY_FUSE_RADIUS

        closest_time = -(
            relative_start.x() * relative_velocity.x()
            + relative_start.y() * relative_velocity.y()
        ) / relative_speed_sq
        closest_time = max(0.0, min(1.0, closest_time))
        closest_relative = QPointF(
            relative_start.x() + relative_velocity.x() * closest_time,
            relative_start.y() + relative_velocity.y() * closest_time,
        )
        return math.hypot(closest_relative.x(), closest_relative.y()) <= self.PROXIMITY_FUSE_RADIUS

    @staticmethod
    def _distance(a, b):
        return math.hypot(a.x() - b.x(), a.y() - b.y())
