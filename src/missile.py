import math
from PyQt6.QtCore import QPointF


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
            self.target_pos = current_target_pos
            self.last_update_time = current_time
        elif current_time - self.last_update_time > self.lifetime:
            self.is_dead = True
            return

        dx = self.target_pos.x() - self.pos.x()
        dy = self.target_pos.y() - self.pos.y()
        dist = math.hypot(dx, dy)

        if dist < 5:
            self.target_traj.is_destroyed = True
            self.is_dead = True
            return

        step = min(dt * self.speed, dist)
        if dist > 0:
            self.pos += QPointF(dx / dist * step, dy / dist * step)
