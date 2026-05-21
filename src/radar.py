import math
from typing import Dict, List, Optional, Tuple
from PyQt6.QtCore import QPointF


class TrackedTarget:
    """Информация об отслеживаемой цели"""

    def __init__(self, target, point: QPointF, detection_time: float):
        self.target = target  # ссылка на объект Trajectory
        self.detection_points: List[Tuple[QPointF, float]] = [(point, detection_time)]
        self.color = None  # будет назначен позже
        self.last_seen_time = detection_time

    def add_detection(self, point: QPointF, detection_time: float):
        self.detection_points.append((point, detection_time))
        self.last_seen_time = detection_time


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
        self._initialized = True
        self._initialization_time = 0.0

        # Новые поля для множественного отслеживания
        self.tracked_targets: Dict[int, TrackedTarget] = {}  # id(traj) -> TrackedTarget
        self._next_color_index = 0
        self._color_palette = [
            (255, 70, 70),  # ярко-красный
            (70, 255, 70),  # ярко-зеленый
            (70, 70, 255),  # ярко-синий
            (255, 255, 70),  # желтый
            (255, 70, 255),  # пурпурный
            (70, 255, 255),  # голубой
            (255, 140, 70),  # оранжевый
            (140, 70, 255),  # фиолетовый
        ]

        # Для совместимости со старым кодом
        self.tracked_target = None
        self.tracked_point = None

    def set_initialization_time(self, t):
        """Устанавливаем время инициализации радара"""
        self._initialization_time = t
        self._initialized = False
        self._initialized = False

    def get_distance_to_point(self, point):
        """Расстояние от радара до точки"""
        dx = point.x() - self.center.x()
        dy = point.y() - self.center.y()
        return math.hypot(dx, dy)

    def get_current_angle(self, t):
        """Текущий угол поворота радара в момент времени t"""
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

    def _get_target_color(self, traj_id: int):
        """Получить или назначить цвет для цели"""
        tracked = self.tracked_targets.get(traj_id)
        if tracked and tracked.color:
            return tracked.color

        # Назначаем новый цвет
        color = self._color_palette[self._next_color_index % len(self._color_palette)]
        self._next_color_index += 1

        if tracked:
            tracked.color = color
        return color

    def get_detection_points(self, traj_id: int) -> List[Tuple[QPointF, float]]:
        """Получить все точки обнаружения для конкретной цели"""
        tracked = self.tracked_targets.get(traj_id)
        if tracked:
            return tracked.detection_points
        return []

    def get_all_detection_points(self) -> Dict[int, List[Tuple[QPointF, float]]]:
        """Получить точки обнаружения для всех целей"""
        return {
            traj_id: tracked.detection_points
            for traj_id, tracked in self.tracked_targets.items()
        }

    def record_detection(self, traj, point: QPointF, detection_time: float):
        """Записать факт обнаружения цели"""
        traj_id = id(traj)

        if traj_id not in self.tracked_targets:
            self.tracked_targets[traj_id] = TrackedTarget(traj, point, detection_time)
        else:
            # Проверяем, не слишком ли близко к предыдущей точке
            tracked = self.tracked_targets[traj_id]
            if tracked.detection_points:
                last_point, last_time = tracked.detection_points[-1]
                min_record_distance = 2.0  # минимальное расстояние между отметками в пикселях
                if (math.hypot(point.x() - last_point.x(), point.y() - last_point.y()) > min_record_distance):
                    tracked.add_detection(point, detection_time)
            else:
                tracked.add_detection(point, detection_time)

    def remove_target(self, traj_id: int):
        """Удалить цель из отслеживания"""
        if traj_id in self.tracked_targets:
            del self.tracked_targets[traj_id]

    def cleanup_dead_targets(self, current_time: float, timeout: float = 30.0):
        """Удалить цели, которые не видели дольше timeout секунд"""
        to_remove = []
        for traj_id, tracked in self.tracked_targets.items():
            if current_time - tracked.last_seen_time > timeout:
                to_remove.append(traj_id)
        for traj_id in to_remove:
            del self.tracked_targets[traj_id]

    def contains_point_during_interval(self, point, start_t, end_t):
        """Проверяет, попадает ли точка в сектор обзора в течение интервала времени"""
        if not self._point_in_range(point):
            return False

        interval_start = min(start_t, end_t)
        interval_end = max(start_t, end_t)

        # Защита от слишком маленьких интервалов (в которых радар почти не повернулся)
        if interval_end - interval_start < 0.01:
            return self.contains_point(point, interval_end)

        point_angle = self._point_angle(point)
        half_angle = self.view_angle / 2.0

        # Проверяем несколько моментов времени внутри интервала
        num_samples = max(3, int((interval_end - interval_start) * 10))  # 10 samples per second
        for i in range(num_samples + 1):
            t = interval_start + (interval_end - interval_start) * i / num_samples
            current_angle = self.get_current_angle(t)
            diff = abs(point_angle - current_angle)
            diff = min(diff, 360.0 - diff)
            if diff <= half_angle:
                return True

        return False

    def contains_point(self, point, t):
        """Проверяет, находится ли точка в зоне обзора радара в момент времени t"""
        if not self._point_in_range(point):
            return False
        angle = self._point_angle(point)
        current_angle = self.get_current_angle(t)
        diff = abs(angle - current_angle)
        diff = min(diff, 360.0 - diff)
        return diff <= self.view_angle / 2.0

    def get_tracked_targets_info(self):
        """Получить информацию о всех отслеживаемых целях"""
        return [
            {
                "name": tracked.target.name,
                "detection_count": len(tracked.detection_points),
                "last_seen": tracked.last_seen_time,
                "color": tracked.color or self._get_target_color(traj_id)
            }
            for traj_id, tracked in self.tracked_targets.items()
        ]

    def to_dict(self):
        return {
            "name": self.name,
            "center": (self.center.x(), self.center.y()),
            "max_range": self.max_range,
            "view_angle": self.view_angle,
            "rotation_speed": self.rotation_speed,
            "start_angle": self.start_angle,
            "tracked_targets_data": [
                {
                    "traj_name": tracked.target.name,
                    "points": [(p.x(), p.y()) for p, _ in tracked.detection_points],
                    "color": tracked.color
                }
                for tracked in self.tracked_targets.values()
            ] if self.tracked_targets else []
        }

    @classmethod
    def from_dict(cls, d):
        radar = cls(
            d["name"],
            d["center"],
            d["max_range"],
            d["view_angle"],
            d["rotation_speed"],
            d.get("start_angle", 0.0)
        )
        # Восстанавливаем данные об отслеживании (точки будут добавлены позже, когда появятся цели)
        # Так как цели могут еще не существовать, просто сохраняем данные в атрибут для отложенного восстановления
        radar._pending_tracked_data = d.get("tracked_targets_data", [])
        return radar

    def restore_tracked_points(self, trajectories):
        """Восстановить точки обнаружения после загрузки сцены"""
        if hasattr(self, '_pending_tracked_data') and self._pending_tracked_data:
            for track_data in self._pending_tracked_data:
                # Находим цель по имени
                for traj in trajectories:
                    if traj.name == track_data["traj_name"]:
                        traj_id = id(traj)
                        self.tracked_targets[traj_id] = TrackedTarget(traj, QPointF(0, 0), 0)
                        for px, py in track_data["points"]:
                            point = QPointF(px, py)
                            # Время восстановить сложно, ставим 0
                            self.tracked_targets[traj_id].detection_points.append((point, 0))
                        self.tracked_targets[traj_id].color = track_data.get("color")
                        break
            delattr(self, '_pending_tracked_data')