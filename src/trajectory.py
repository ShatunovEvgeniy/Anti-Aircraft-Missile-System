import random as r
import math

from PyQt6.QtGui import QColor
from PyQt6.QtCore import QPointF

from motion_errors import get_target_position_error


class Trajectory:
    def __init__(self, name="Траектория", color=None, speed=200.0):
        self.name = name
        self.points = []
        self.segments = []
        self.total_length = 0.0
        self.speed = speed
        self.travel_time = float('inf')
        self.is_destroyed = False
        self.motion_error_key = name
        if color is None:
            self.color = QColor(r.randint(0,255), r.randint(0,255), r.randint(0,255))
        else:
            self.color = color

    def _refresh_motion_error_key(self):
        point_signature = ";".join(f"{point.x():.3f}:{point.y():.3f}" for point in self.points)
        self.motion_error_key = f"{self.name}|{point_signature}|{self.speed:.6f}"

    def refresh_motion_error_key(self):
        self._refresh_motion_error_key()

    def compute_segments(self):
        self.segments.clear()
        self.total_length = 0.0
        if len(self.points) < 2:
            self.travel_time = float('inf')
            return
        for i in range(len(self.points)-1):
            start = QPointF(self.points[i])
            end = QPointF(self.points[i+1])
            dx = end.x()-start.x()
            dy = end.y()-start.y()
            length = math.hypot(dx, dy)
            self.segments.append((start, end, length))
            self.total_length += length
        if self.speed > 0:
            self.travel_time = self.total_length / self.speed
        else:
            self.travel_time = float('inf')
        self._refresh_motion_error_key()

    def _update_travel_time(self):
        if len(self.points) >= 2 and self.speed > 0:
            self.travel_time = self.total_length / self.speed
        else:
            self.travel_time = float('inf')

    def add_point(self, point):
        new_point = QPointF(point)
        if self.points:
            start = QPointF(self.points[-1])
            dx = new_point.x() - start.x()
            dy = new_point.y() - start.y()
            length = math.hypot(dx, dy)
            self.segments.append((start, new_point, length))
            self.total_length += length
        self.points.append(new_point)
        self._update_travel_time()
        self._refresh_motion_error_key()

    def remove_last_point(self):
        if not self.points:
            return None
        point = self.points.pop()
        if self.segments:
            _, _, length = self.segments.pop()
            self.total_length -= length
            if self.total_length < 0:
                self.total_length = 0.0
        self._update_travel_time()
        self._refresh_motion_error_key()
        return point

    def get_position(self, sim_time):
        if self.is_destroyed or not self.points:
            return None
        if sim_time <= 0:
            return QPointF(self.points[0])
        if sim_time > self.travel_time:
            return None
        t = sim_time / self.travel_time
        return self.get_position_by_t(t)

    def get_observed_position(self, sim_time, meters_per_pixel):
        true_position = self.get_position(sim_time)
        if true_position is None:
            return None
        error = get_target_position_error(self.motion_error_key, sim_time, meters_per_pixel)
        return QPointF(true_position.x() + error.x(), true_position.y() + error.y())

    def get_position_by_t(self, t):
        if not self.segments:
            return None
        if t <= 0:
            return QPointF(self.points[0])
        if t >= 1:
            return QPointF(self.points[-1])
        target = t * self.total_length
        cum = 0.0
        for start, end, length in self.segments:
            if target <= cum + length:
                local = (target - cum) / length
                dx = end.x()-start.x()
                dy = end.y()-start.y()
                return QPointF(start.x() + dx*local, start.y() + dy*local)
            cum += length
        return QPointF(self.points[-1])

    def get_velocity(self, sim_time):
        if self.is_destroyed or not self.segments or self.speed <= 0:
            return QPointF(0.0, 0.0)
        if sim_time >= self.travel_time:
            return QPointF(0.0, 0.0)

        if sim_time <= 0:
            target_distance = 0.0
        else:
            target_distance = min(sim_time * self.speed, self.total_length)

        cum = 0.0
        for start, end, length in self.segments:
            if length <= 0:
                cum += length
                continue
            if target_distance <= cum + length:
                dx = end.x() - start.x()
                dy = end.y() - start.y()
                return QPointF(dx / length * self.speed, dy / length * self.speed)
            cum += length

        start, end, length = self.segments[-1]
        if length <= 0:
            return QPointF(0.0, 0.0)
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        return QPointF(dx / length * self.speed, dy / length * self.speed)

    def set_speed(self, speed):
        self.speed = max(0.001, speed)
        self._update_travel_time()
        self._refresh_motion_error_key()

    def reset_simulation_state(self):
        self.is_destroyed = False

    def to_dict(self):
        return {
            "name": self.name,
            "color": {"r": self.color.red(), "g": self.color.green(), "b": self.color.blue()},
            "speed": self.speed,
            "points": [(p.x(), p.y()) for p in self.points]
        }

    @classmethod
    def from_dict(cls, d):
        name = d.get("name", "Unknown")
        points = [QPointF(float(x), float(y)) for x, y in d.get("points", [])]
        speed = d.get("speed", 200.0)
        c = d.get("color")
        if c:
            color = QColor(c["r"], c["g"], c["b"])
        else:
            color = None
        t = cls(name, color, speed)
        t.points = points
        t.compute_segments()
        return t
