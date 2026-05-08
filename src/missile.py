import math
from PyQt6.QtCore import QPointF


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
    def __init__(self, start_pos, target_traj, target_pos, speed, lifetime, creation_time):
        self.pos = QPointF(start_pos)
        self.target_traj = target_traj
        self.target_pos = QPointF(target_pos)
        self.speed = speed
        self.lifetime = lifetime
        self.creation_time = creation_time
        self.last_update_time = creation_time
        self.is_dead = False

    def update(self, dt, current_time, radars, trajectories):
        """Обновление состояния ракеты"""
        if self.is_dead:
            return

        if self.target_traj.is_destroyed:
            self.is_dead = True
            return

        current_target_pos = self.target_traj.get_position(current_time)
        if current_target_pos is None:
            self.is_dead = True
            return

        previous_time = max(self.creation_time, current_time - dt)
        target_visible = any(
            radar.contains_point_during_interval(current_target_pos, previous_time, current_time)
            for radar in radars
        )
        if target_visible:
            target_velocity = self.target_traj.get_velocity(current_time)
            self.target_pos, _ = predict_intercept_point(
                self.pos,
                self.speed,
                current_target_pos,
                target_velocity,
            )
            self.last_update_time = current_time
        elif current_time - self.last_update_time > self.lifetime:
            self.is_dead = True
            return

        dx = self.target_pos.x() - self.pos.x()
        dy = self.target_pos.y() - self.pos.y()
        dist = math.hypot(dx, dy)

        step = min(dt * self.speed, dist)
        if dist > 0:
            self.pos += QPointF(dx / dist * step, dy / dist * step)
