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

    def get_distance_to_point(self, point):
        """Расстояние от радара до точки"""
        dx = point.x() - self.center.x()
        dy = point.y() - self.center.y()
        return math.hypot(dx, dy)

    def get_current_angle(self, t):
        return (self.start_angle + self.rotation_speed * t) % 360.0

    def _point_angle(self, point):
        dx = point.x() - self.center.x()
        dy = point.y() - self.center.y()
        return math.degrees(math.atan2(-dy, dx)) % 360.0

    def _point_in_range(self, point):
        dx = point.x() - self.center.x()
        dy = point.y() - self.center.y()
        return math.hypot(dx, dy) <= self.max_range

    def _angle_inside_sector(self, angle, sector_center):
        diff = abs(angle - sector_center)
        diff = min(diff, 360.0 - diff)
        return diff <= self.view_angle / 2.0

    def contains_point(self, point, t):
        if not self._point_in_range(point):
            return False
        angle = self._point_angle(point)
        return self._angle_inside_sector(angle, self.get_current_angle(t))

    def contains_point_during_interval(self, point, start_t, end_t):
        if not self._point_in_range(point):
            return False

        interval_start = min(start_t, end_t)
        interval_end = max(start_t, end_t)

        if interval_start == interval_end or self.rotation_speed == 0:
            return self.contains_point(point, interval_end)

        point_angle = self._point_angle(point)
        start_angle = self.start_angle + self.rotation_speed * interval_start
        end_angle = self.start_angle + self.rotation_speed * interval_end
        sweep_min = min(start_angle, end_angle) - self.view_angle / 2.0
        sweep_max = max(start_angle, end_angle) + self.view_angle / 2.0

        k_min = math.floor((sweep_min - point_angle) / 360.0) - 1
        k_max = math.ceil((sweep_max - point_angle) / 360.0) + 1
        for k in range(k_min, k_max + 1):
            unwrapped_angle = point_angle + 360.0 * k
            if sweep_min <= unwrapped_angle <= sweep_max:
                return True
        return False

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
    
