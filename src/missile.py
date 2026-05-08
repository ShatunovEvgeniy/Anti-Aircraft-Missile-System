import math
from PyQt6.QtCore import QPointF


class Missile:
    HIT_RADIUS = 5.0

    def __init__(self, start_pos, target_traj, target_pos, speed, lifetime, creation_time):
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
            self.target_pos = current_target_pos
            self.last_update_time = current_time
        elif current_time - self.last_update_time > self.lifetime:
            self.is_dead = True
            return

        dx = self.target_pos.x() - self.pos.x()
        dy = self.target_pos.y() - self.pos.y()
        dist = math.hypot(dx, dy)

        previous_pos = QPointF(self.pos)
        step = min(dt * self.speed, dist)
        if dist > 0:
            self.pos += QPointF(dx / dist * step, dy / dist * step)

        if self._hit_current_target(previous_pos, self.pos, current_target_pos):
            self.target_traj.is_destroyed = True
            self.hit_target = True
            self.is_dead = True
        elif self._distance(self.pos, self.target_pos) <= self.HIT_RADIUS:
            self.missed_target = True
            self.miss_pos = QPointF(self.target_pos)
            self.is_dead = True

    def _hit_current_target(self, start_pos, end_pos, target_pos):
        segment_dx = end_pos.x() - start_pos.x()
        segment_dy = end_pos.y() - start_pos.y()
        segment_len_sq = segment_dx * segment_dx + segment_dy * segment_dy
        if segment_len_sq == 0:
            return self._distance(end_pos, target_pos) <= self.HIT_RADIUS

        target_dx = target_pos.x() - start_pos.x()
        target_dy = target_pos.y() - start_pos.y()
        projection = (target_dx * segment_dx + target_dy * segment_dy) / segment_len_sq
        projection = max(0.0, min(1.0, projection))
        closest = QPointF(
            start_pos.x() + segment_dx * projection,
            start_pos.y() + segment_dy * projection,
        )
        return self._distance(closest, target_pos) <= self.HIT_RADIUS

    @staticmethod
    def _distance(a, b):
        return math.hypot(a.x() - b.x(), a.y() - b.y())
