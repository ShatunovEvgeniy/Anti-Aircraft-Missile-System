import math
from PyQt6.QtCore import QPointF

from missile import Missile


class LaunchPad:
    def __init__(self, name, center, missile_speed=200.0, launch_range=200.0, missile_lifetime=5.0):
        self.name = name
        if isinstance(center, (list, tuple)) and len(center) >= 2:
            self.center = QPointF(center[0], center[1])
        else:
            self.center = QPointF(center)
        self.missile_speed = missile_speed
        self.launch_range = launch_range
        self.missile_lifetime = missile_lifetime
        self.missiles = []

    @staticmethod
    def get_distance(p1, p2):
        """Вычисление расстояния между двумя точками"""
        dx = p1.x() - p2.x()
        dy = p1.y() - p2.y()
        return math.hypot(dx, dy)

    def can_launch(self, target_pos):
        return math.hypot(target_pos.x()-self.center.x(), target_pos.y()-self.center.y()) <= self.launch_range

    def launch_missile(self, target_traj, target_pos, current_time):
        missile = Missile(self.center, target_traj, target_pos, self.missile_speed, self.missile_lifetime, current_time)
        self.missiles.append(missile)


    def update_missiles(self, dt, current_time, radars, trajectories):
        events = []
        for missile in self.missiles[:]:
            missile.update(dt, current_time, radars, trajectories)
            if missile.is_dead:
                if missile.hit_target:
                    events.append(("target_destroyed", self.name, missile.target_traj.name))
                elif current_time - missile.last_update_time > self.missile_lifetime:
                    events.append(("missile_expired", self.name, missile.target_traj.name))
                if missile in self.missiles:
                    self.missiles.remove(missile)
        return events

    def reset_simulation_state(self):
        self.missiles.clear()

    def to_dict(self):
        return {
            "name": self.name,
            "center": (self.center.x(), self.center.y()),
            "missile_speed": self.missile_speed,
            "launch_range": self.launch_range,
            "missile_lifetime": self.missile_lifetime
        }

    @classmethod
    def from_dict(cls, d):
        return cls(d["name"], d["center"], d["missile_speed"], d["launch_range"], d["missile_lifetime"])
