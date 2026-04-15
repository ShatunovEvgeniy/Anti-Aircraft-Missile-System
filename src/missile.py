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
        self.hit_target = False

    def update(self, dt, current_time, radars, trajectories):
        # Обновляем цель, если она видна
        target_visible = any(r.contains_point(self.target_pos, current_time) for r in radars)
        if target_visible:
            # Обновляем позицию цели
            self.target_pos = self.target_traj.get_position(current_time)
            self.last_update_time = current_time
        else:
            if current_time - self.last_update_time > self.lifetime:
                self.is_dead = True
                return

        # Движение к цели
        dx = self.target_pos.x() - self.pos.x()
        dy = self.target_pos.y() - self.pos.y()
        dist = math.hypot(dx, dy)
        if dist < 5:
            # Уничтожить цель и ракету
            if self.target_traj in trajectories:
                trajectories.remove(self.target_traj)
            self.hit_target = True
            self.is_dead = True
            return
        step = min(dt * self.speed, dist)
        if dist > 0:
            self.pos += QPointF(dx / dist * step, dy / dist * step)
