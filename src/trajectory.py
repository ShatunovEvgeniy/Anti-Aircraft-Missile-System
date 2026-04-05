import random as r
import math

from PyQt6.QtGui import QColor
from PyQt6.QtCore import QPointF, QPoint


class Trajectory:
    def __init__(self, name="Траектория", color=None, speed=200.0):
        self.name = name
        self.points = []
        self.segments = []
        self.total_length = 0.0
        self.speed = speed
        self.travel_time = float('inf')
        if color is None:
            self.color = QColor(r.randint(0,255), r.randint(0,255), r.randint(0,255))
        else:
            self.color = color

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

    def get_position(self, sim_time):
        if not self.points:
            return None
        if sim_time <= 0:
            return QPointF(self.points[0])
        if sim_time >= self.travel_time:
            return QPointF(self.points[-1])
        t = sim_time / self.travel_time
        return self.get_position_by_t(t)

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

    def set_speed(self, speed):
        self.speed = max(0.001, speed)
        self.compute_segments()

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
        points = [QPoint(x,y) for x,y in d.get("points", [])]
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
