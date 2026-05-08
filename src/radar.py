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
        self.rotation_reference_time = 0.0
        self.current_angle = start_angle % 360.0
        self.tracked_target = None
        self.tracked_point = None

    def get_distance_to_point(self, point):
        """Расстояние от радара до точки"""
        dx = point.x() - self.center.x()
        dy = point.y() - self.center.y()
        return math.hypot(dx, dy)

    def get_current_angle(self, t):
        if self.tracked_target is not None:
            return self.current_angle
        return (self.start_angle + self.rotation_speed * (t - self.rotation_reference_time)) % 360.0

    def _point_angle(self, point):
        dx = point.x() - self.center.x()
        dy = point.y() - self.center.y()
        return math.degrees(math.atan2(-dy, dx)) % 360.0

    def _point_in_range(self, point):
        dx = point.x() - self.center.x()
        dy = point.y() - self.center.y()
        return math.hypot(dx, dy) <= self.max_range

    def can_track_point(self, point):
        return self._point_in_range(point)

    def start_tracking(self, target, point, t):
        self.current_angle = self._point_angle(point)
        self.rotation_reference_time = t
        self.tracked_target = target
        self.tracked_point = QPointF(point)

    def update_tracking(self, point, t):
        self.current_angle = self._point_angle(point)
        self.rotation_reference_time = t
        self.tracked_point = QPointF(point)

    def stop_tracking(self, t):
        current_angle = self.get_current_angle(t)
        self.tracked_target = None
        self.tracked_point = None
        self.current_angle = current_angle
        self.start_angle = current_angle
        self.rotation_reference_time = t

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

        if self.tracked_target is not None:
            return True

        interval_start = min(start_t, end_t)
        interval_end = max(start_t, end_t)

        if interval_start == interval_end or self.rotation_speed == 0:
            return self.contains_point(point, interval_end)

        point_angle = self._point_angle(point)
        start_angle = self.start_angle + self.rotation_speed * (
            interval_start - self.rotation_reference_time
        )
        end_angle = self.start_angle + self.rotation_speed * (
            interval_end - self.rotation_reference_time
        )
        sweep_span = abs(end_angle - start_angle) + self.view_angle
        if sweep_span >= 360.0:
            return True

        sweep_min = min(start_angle, end_angle) - self.view_angle / 2.0
        sweep_max = max(start_angle, end_angle) + self.view_angle / 2.0

        nearest_turn = round((sweep_min - point_angle) / 360.0)
        k_min = nearest_turn - 1
        k_max = nearest_turn + 2
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
    
