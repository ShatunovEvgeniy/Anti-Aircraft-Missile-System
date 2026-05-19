import math

from PyQt6.QtCore import QPointF


TARGET_CLASS_BANDS = [
    (0.03, "сверхмалая цель"),
    (0.3, "малая цель"),
    (2.0, "цель класса КР/БПЛА"),
    (8.0, "истребитель"),
    (20.0, "крупная воздушная цель"),
]


class Radar:
    def __init__(
        self,
        name,
        center,
        max_range,
        view_angle,
        rot_speed,
        start_angle=0.0,
        transmit_power_w=1.5e6,
        antenna_gain=4000.0,
        wavelength_m=0.1,
        system_losses=1.5,
    ):
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
        self.tracked_targets = {}
        self.transmit_power_w = max(1.0, float(transmit_power_w))
        self.antenna_gain = max(1.0, float(antenna_gain))
        self.wavelength_m = max(1e-6, float(wavelength_m))
        self.system_losses = max(1.0, float(system_losses))

    def get_distance_to_point(self, point):
        """Расстояние от радара до точки"""
        dx = point.x() - self.center.x()
        dy = point.y() - self.center.y()
        return math.hypot(dx, dy)

    def get_current_angle(self, t):
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
        target_id = id(target)
        tracked_point = QPointF(point)
        self.tracked_targets[target_id] = {
            "target": target,
            "point": tracked_point,
            "time": t,
        }
        self.tracked_target = target
        self.tracked_point = tracked_point

    def update_tracking(self, target, point, t):
        self.start_tracking(target, point, t)
        return True

    def is_tracking_target(self, target):
        return id(target) in self.tracked_targets

    def is_tracking_point(self, point, tolerance=1e-3):
        for tracked_data in self.tracked_targets.values():
            tracked_point = tracked_data["point"]
            if math.hypot(tracked_point.x() - point.x(), tracked_point.y() - point.y()) <= tolerance:
                return True
        return False

    def stop_tracking(self, t, target=None):
        if target is None:
            self.tracked_targets.clear()
            self.tracked_target = None
            self.tracked_point = None
            self.rotation_reference_time = t
            return

        self.tracked_targets.pop(id(target), None)
        if self.tracked_target is target:
            self.tracked_target = None
            self.tracked_point = None
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
        if self.is_tracking_point(point):
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

    def contains_point_during_interval_scan(self, point, start_t, end_t):
        if not self._point_in_range(point):
            return False

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

    def compute_received_power(self, target, point, meters_per_pixel):
        distance_m = max(self.get_distance_to_point(point) * meters_per_pixel, 1.0)
        sigma = max(0.001, getattr(target, "radar_cross_section_m2", 1.0))
        denominator = ((4.0 * math.pi) ** 3) * (distance_m ** 4) * self.system_losses
        numerator = self.transmit_power_w * (self.antenna_gain ** 2) * (self.wavelength_m ** 2) * sigma
        return numerator / denominator

    def estimate_target_rcs(self, received_power_w, point, meters_per_pixel):
        distance_m = max(self.get_distance_to_point(point) * meters_per_pixel, 1.0)
        numerator = received_power_w * ((4.0 * math.pi) ** 3) * (distance_m ** 4) * self.system_losses
        denominator = self.transmit_power_w * (self.antenna_gain ** 2) * (self.wavelength_m ** 2)
        if denominator <= 0:
            return 0.0
        return max(0.001, numerator / denominator)

    def classify_target_by_rcs(self, estimated_rcs_m2):
        sigma = max(0.001, float(estimated_rcs_m2))
        for upper_bound, label in TARGET_CLASS_BANDS:
            if sigma < upper_bound:
                return label
        return "особо крупная воздушная цель"

    def analyze_target(self, target, point, meters_per_pixel):
        received_power_w = self.compute_received_power(target, point, meters_per_pixel)
        estimated_rcs_m2 = self.estimate_target_rcs(received_power_w, point, meters_per_pixel)
        return {
            "received_power_w": received_power_w,
            "estimated_rcs_m2": estimated_rcs_m2,
            "target_class": self.classify_target_by_rcs(estimated_rcs_m2),
        }

    def to_dict(self):
        return {
            "name": self.name,
            "center": (self.center.x(), self.center.y()),
            "max_range": self.max_range,
            "view_angle": self.view_angle,
            "rotation_speed": self.rotation_speed,
            "start_angle": self.start_angle,
            "transmit_power_w": self.transmit_power_w,
            "antenna_gain": self.antenna_gain,
            "wavelength_m": self.wavelength_m,
            "system_losses": self.system_losses,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            d["name"],
            d["center"],
            d["max_range"],
            d["view_angle"],
            d["rotation_speed"],
            d.get("start_angle", 0.0),
            d.get("transmit_power_w", 1.5e6),
            d.get("antenna_gain", 4000.0),
            d.get("wavelength_m", 0.1),
            d.get("system_losses", 1.5),
        )
