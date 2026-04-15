import math

from PyQt6.QtCore import QPointF


class Radar:
    def __init__(self, name, center, max_range, view_angle, rot_speed, start_angle=0.0):
        self.name = name
        if isinstance(center, (list, tuple)) and len(center) >= 2:
            self.center = QPointF(center[0], center[1])
        else:
            self.center = QPointF(center)
        self.max_range = max_range
        self.view_angle = view_angle
        self.rotation_speed = rot_speed
        self.start_angle = start_angle

    def get_current_angle(self, t):
        return (self.start_angle + self.rotation_speed * t) % 360.0

    def contains_point(self, point, t):
        dx = point.x() - self.center.x()
        dy = point.y() - self.center.y()
        dist = math.hypot(dx, dy)
        if dist > self.max_range:
            return False
        angle = math.degrees(math.atan2(-dy, dx)) % 360.0
        current = self.get_current_angle(t)
        diff = abs(angle - current)
        diff = min(diff, 360.0 - diff)
        return diff <= self.view_angle / 2.0

    def to_dict(self):
        return {
            "name": self.name,
            "center": (self.center.x(), self.center.y()),
            "max_range": self.max_range,
            "view_angle": self.view_angle,
            "rotation_speed": self.rotation_speed,
            "start_angle": self.start_angle
        }

    @classmethod
    def from_dict(cls, d):
        return cls(d["name"], d["center"], d["max_range"], d["view_angle"], d["rotation_speed"], d.get("start_angle", 0.0))
    
