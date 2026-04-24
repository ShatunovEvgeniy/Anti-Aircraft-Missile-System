import json
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                             QPushButton, QStatusBar, QSlider, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QInputDialog, QFileDialog,
                             QMenu, QDoubleSpinBox, QToolBar, QTabWidget, QTextEdit,
                             QGroupBox, QFormLayout, QLineEdit, QSplitter, QMessageBox,
                             QDialog, QDialogButtonBox)
from PyQt6.QtCore import Qt, QPointF, QTimer, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QBrush, QColor, QPen, QAction, QPixmap, QIcon, QPainterPath, QPolygonF
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from event_logger import EventLogger
from trajectory import Trajectory
from radar import Radar
from launchpad import LaunchPad
from radar import Radar
from simulation_defaults import (
    ANIMATION_INTERVAL_MS,
    DEFAULT_LAUNCHPAD_NAME,
    DEFAULT_MISSILE_LIFETIME,
    DEFAULT_MISSILE_RANGE_M,
    DEFAULT_MISSILE_SPEED_MPS,
    DEFAULT_PLAYBACK_SPEED,
    DEFAULT_RADAR_NAME,
    DEFAULT_RADAR_RANGE_M,
    DEFAULT_RADAR_ROTATION_SPEED,
    DEFAULT_RADAR_VIEW_ANGLE,
    DEFAULT_TARGET_NAME,
    DEFAULT_TARGET_SPEED_MPS,
    MAX_SIMULATION_DURATION_S,
    METERS_PER_PIXEL,
)
from trajectory import Trajectory


class ScaleDialog(QDialog):
    def __init__(self, current_scale=METERS_PER_PIXEL, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Масштаб карты")

        layout = QFormLayout(self)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.1, 100000.0)
        self.scale_spin.setDecimals(2)
        self.scale_spin.setValue(current_scale)
        self.scale_spin.setSuffix(" м/пикс")
        layout.addRow("Масштаб:", self.scale_spin)

        info_label = QLabel("Пример: 500 м/пикс -> 1 км = 2 пикселя")
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addRow(info_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_scale(self):
        return self.scale_spin.value()


class ObjectCreationDialog(QDialog):
    def __init__(self, title, fields, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.setModal(True)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Введите имя объекта")
        form.addRow("Имя:", self.name_edit)

        self.spin_boxes = {}
        for field in fields:
            spin = QDoubleSpinBox()
            spin.setRange(field["min"], field["max"])
            spin.setValue(field["value"])
            spin.setDecimals(field.get("decimals", 1))
            if "suffix" in field:
                spin.setSuffix(field["suffix"])
            if "step" in field:
                spin.setSingleStep(field["step"])
            form.addRow(field["label"], spin)
            self.spin_boxes[field["key"]] = spin

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        data = {"name": self.name_edit.text().strip()}
        for key, spin in self.spin_boxes.items():
            data[key] = spin.value()
        return data


class PointCanvas(QWidget):
    event_signal = pyqtSignal(str)
    target_detected = pyqtSignal(object, QPointF)  # (trajectory, position)
    radar_list_changed = pyqtSignal()
    trajectory_list_changed = pyqtSignal()
    launchpad_list_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(700, 500)
        self.setStyleSheet("background-color: white;")
        self.setMouseTracking(True)

        self.zoom_level = 1.0
        self.min_zoom = 0.3
        self.max_zoom = 5.0
        self.zoom_factor = 1.1
        self.view_offset = QPointF(0.0, 0.0)
        self.drag_start = None

        self.map_scale = METERS_PER_PIXEL
        self.show_grid = True
        self.grid_color = QColor(200, 200, 200)
        self.last_scale_bar_values = None
        self.last_scale_bar_data = None

        self.trajectories = []
        self.active_index = -1
        self.radars = []
        self.launch_pads = []
        self._active_detections = set()

        self.simulation_time = 0.0
        self.auto_max_time = 0.0
        self.max_time = 0.0
        self.simulation_duration_override = 0.0

        self.animation_timer = QTimer()
        self.animation_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.animation_timer.timeout.connect(self.update_animation)
        self.is_animating = False
        self.last_time = 0.0
        self.progress_slider = None
        self.time_label = None
        self.playback_speed = DEFAULT_PLAYBACK_SPEED

        self.drawing_mode = "trajectory"

        self.background_image = None
        self.background_opacity = 0.7
        self.background_path = None

        self.drawing_mode = "trajectory"  # trajectory, radar, launchpad
        self.detected_pairs = set()

    # ========== Траектории ==========
    def add_trajectory(self, name=None, points=None, speed=None, color=None):
        if name is None:
            if self.trajectories:
                name = f"{DEFAULT_TARGET_NAME} {len(self.trajectories)+1}"
            else:
                name = DEFAULT_TARGET_NAME
        if speed is None:
            speed = self.mps_to_world_speed(DEFAULT_TARGET_SPEED_MPS)
        traj = Trajectory(name, color, speed)
        if points:
            traj.points = points
            traj.compute_segments()
        self.trajectories.append(traj)
        self.active_index = len(self.trajectories) - 1
        self.stop_animation()
        self._recalc_max_time()
        self._update_all_positions()
        self.trajectory_list_changed.emit()
        self.event_signal.emit(f"Создана цель {name}")
        self.update()
        return traj

    def remove_trajectory(self, idx):
        if 0 <= idx < len(self.trajectories):
            traj = self.trajectories[idx]
            del self.trajectories[idx]
            self.detected_pairs = {pair for pair in self.detected_pairs if pair[1] is not traj}
            if self.trajectories:
                self.active_index = min(idx, len(self.trajectories) - 1)
            else:
                self.active_index = -1
            self.stop_animation()
            self._recalc_max_time()
            self._update_all_positions()
            self.trajectory_list_changed.emit()
            self.event_signal.emit(f"Удалена цель {traj.name}")
            self.update()

    def set_active_trajectory(self, idx):
        if 0 <= idx < len(self.trajectories):
            self.active_index = idx

    def set_trajectory_speed(self, idx, speed_world):
        if 0 <= idx < len(self.trajectories):
            self.trajectories[idx].set_speed(speed_world)
            self._recalc_max_time()
            self._update_all_positions()
            self.update()

    # ========== Радары ==========
    def add_radar(self, name, center, max_range, view_angle, rot_speed):
        radar = Radar(name, center, max_range, view_angle, rot_speed)
        self.radars.append(radar)
        self.stop_animation()
        self._recalc_max_time()
        self._update_all_positions()
        self.radar_list_changed.emit()
        self.event_signal.emit(f"Создан радар {name} в точке ({center.x():.0f}, {center.y():.0f})")
        self.update()

    def remove_radar(self, idx):
        if 0 <= idx < len(self.radars):
            radar = self.radars[idx]
            del self.radars[idx]
            self.detected_pairs = {pair for pair in self.detected_pairs if pair[0] is not radar}
            self.radar_list_changed.emit()
            self.event_signal.emit(f"Удалён радар {radar.name}")
            self.update()

    def update_radar(self, idx, name, max_range, view_angle, rot_speed):
        if 0 <= idx < len(self.radars):
            radar = self.radars[idx]
            radar.name = name
            radar.max_range = max_range
            radar.view_angle = view_angle
            radar.rotation_speed = rot_speed
            self.stop_animation()
            self._recalc_max_time()
            self._update_all_positions()
            self.radar_list_changed.emit()
            self.update()

    # ========== Пусковые установки ==========
    def add_launch_pad(self, name, center, missile_speed, launch_range, missile_lifetime):
        pad = LaunchPad(name, center, missile_speed, launch_range, missile_lifetime)
        self.launch_pads.append(pad)
        self.stop_animation()
        self._recalc_max_time()
        self._update_all_positions()
        self.launchpad_list_changed.emit()
        self.event_signal.emit(f"Создана пусковая установка {name} в точке ({center.x():.0f}, {center.y():.0f})")
        self.update()

    def remove_launch_pad(self, idx):
        if 0 <= idx < len(self.launch_pads):
            pad = self.launch_pads[idx]
            del self.launch_pads[idx]
            self.stop_animation()
            self._recalc_max_time()
            self._update_all_positions()
            self.launchpad_list_changed.emit()
            self.event_signal.emit(f"Удалена пусковая установка {pad.name}")
            self.update()

    def update_launch_pad(self, idx, name, missile_speed, launch_range, missile_lifetime):
        if 0 <= idx < len(self.launch_pads):
            pad = self.launch_pads[idx]
            pad.name = name
            pad.missile_speed = missile_speed
            pad.launch_range = launch_range
            pad.missile_lifetime = missile_lifetime
            self.stop_animation()
            self._recalc_max_time()
            self._update_all_positions()
            self.launchpad_list_changed.emit()
            self.update()

    # ========== Обновления ==========
    def _get_auto_max_time(self):
        trajectory_times = [t.travel_time for t in self.trajectories if t.travel_time != float("inf")]
        base_time = max(trajectory_times) if trajectory_times else 0.0

        radar_buffer = 0.0
        radar_periods = [360.0 / radar.rotation_speed for radar in self.radars if radar.rotation_speed > 0]
        if radar_periods:
            radar_buffer = max(radar_periods)

        missile_buffer = 0.0
        missile_times = [
            (pad.launch_range / pad.missile_speed) + pad.missile_lifetime
            for pad in self.launch_pads
            if pad.missile_speed > 0
        ]
        if missile_times:
            missile_buffer = max(missile_times)

        return base_time + radar_buffer + missile_buffer

    def _reset_simulation_entities(self):
        self._active_detections.clear()
        for traj in self.trajectories:
            traj.reset_simulation_state()
        for pad in self.launch_pads:
            pad.reset_simulation_state()

    def _update_time_display(self):
        if self.time_label:
            self.time_label.setText(f"{self.simulation_time:.1f} / {self.max_time:.1f} c")

    def set_simulation_duration_override(self, duration):
        self.simulation_duration_override = max(0.0, duration)
        self.stop_animation()
        self._recalc_max_time()

    def set_playback_speed(self, speed):
        self.playback_speed = max(0.1, speed)

    def _recalc_max_time(self):
        self.auto_max_time = self._get_auto_max_time()
        self.max_time = (
            self.simulation_duration_override
            if self.simulation_duration_override > 0
            else self.auto_max_time
        )
        if self.progress_slider:
            self.progress_slider.blockSignals(True)
            self.progress_slider.setRange(0, int(self.max_time * 1000) if self.max_time > 0 else 1000)
            self.progress_slider.blockSignals(False)
            if self.simulation_time > self.max_time:
                self.set_simulation_time(self.max_time)
            else:
                self.set_simulation_time(self.simulation_time)

    def _update_all_positions(self):
        if self.progress_slider:
            self.progress_slider.blockSignals(True)
            if self.max_time > 0:
                value = int(self.simulation_time / self.max_time * self.progress_slider.maximum())
            else:
                value = 0
            self.progress_slider.setValue(value)
            self.progress_slider.blockSignals(False)
        self._update_time_display()
        self.update()
        self.check_detections(self.simulation_time, self.simulation_time)

    def check_detections(self):
        current_pairs = set()
        for radar in self.radars:
            for traj in self.trajectories:
                pos = traj.get_position(self.simulation_time)
                if pos and radar.contains_point(pos, self.simulation_time):
                    pair = (radar, traj)
                    current_pairs.add(pair)
                    if pair not in self.detected_pairs:
                        self.event_signal.emit(f"Радар {radar.name} захватил цель {traj.name}")
                        self.target_detected.emit(traj, pos)
        lost_pairs = self.detected_pairs - current_pairs
        for radar, traj in lost_pairs:
            if radar in self.radars and traj in self.trajectories:
                self.event_signal.emit(f"Радар {radar.name} потерял из виду цель {traj.name}")
        self.detected_pairs = current_pairs

    def update_missiles(self, dt):
        destroyed_any = False
        for pad in self.launch_pads:
            events = pad.update_missiles(dt, self.simulation_time, self.radars, self.trajectories)
            for event_type, launcher_name, target_name in events:
                if event_type == "target_destroyed":
                    destroyed_any = True
                    self.event_signal.emit(f"Цель {target_name} была сбита установкой {launcher_name}")
                elif event_type == "missile_expired":
                    self.event_signal.emit(f"Ракета установки {launcher_name} самоликвидировалась: цель {target_name} потеряна")
        if destroyed_any:
            self.detected_pairs = {pair for pair in self.detected_pairs if pair[1] in self.trajectories}
            if self.active_index >= len(self.trajectories):
                self.active_index = len(self.trajectories) - 1
            self._recalc_max_time()
            self.trajectory_list_changed.emit()

    # ========== Анимация и время ==========
    def set_simulation_time(self, t, dt=0):
        old = self.simulation_time
        bounded_time = max(0.0, min(t, self.max_time))
        if bounded_time <= 0.0 or bounded_time < old:
            self._reset_simulation_entities()
        self.simulation_time = bounded_time
        if self.progress_slider:
            self.progress_slider.blockSignals(True)
            if self.max_time > 0:
                value = int(self.simulation_time / self.max_time * self.progress_slider.maximum())
            else:
                value = 0
            self.progress_slider.setValue(value)
            self.progress_slider.blockSignals(False)
        # При перемотке назад ракеты не пересчитываем ретроспективно.
        dt_actual = self.simulation_time - old
        if dt_actual > 0:
            self.update_missiles(dt_actual)
        self.update()
        if dt_actual >= 0:
            self.check_detections(old, self.simulation_time)
        else:
            self.check_detections(self.simulation_time, self.simulation_time)

    def reset_all(self):
        self.stop_animation()
        self._reset_simulation_entities()
        self.set_simulation_time(0.0)

    def start_animation(self):
        if len(self.trajectories) == 0 or not any(len(traj.points) >= 2 for traj in self.trajectories):
            self._show_status("Нет готовых траекторий")
            return
        if self.max_time <= 0:
            self._show_status("Нет данных для анимации")
            return
        if self.is_animating:
            self.stop_animation()
        if self.simulation_time <= 0:
            self._reset_simulation_entities()
        if self.simulation_time >= self.max_time:
            self.set_simulation_time(0.0)
        self.is_animating = True
        self.last_time = time.perf_counter()
        self.animation_timer.start(ANIMATION_INTERVAL_MS)
        self._show_status("Анимация запущена")

    def update_animation(self):
        if not self.is_animating:
            return
        now = time.perf_counter()
        dt = (now - self.last_time) * self.playback_speed
        self.last_time = now
        new_time = self.simulation_time + dt
        if new_time >= self.max_time:
            self.set_simulation_time(self.max_time)
            self.stop_animation()
            self._show_status("Анимация завершена")
        else:
            self.set_simulation_time(new_time)

    def stop_animation(self):
        if self.animation_timer.isActive():
            self.animation_timer.stop()
        self.is_animating = False
        if self.simulation_time >= self.max_time > 0:
            self._reset_simulation_entities()
            self.update()

    def simulate(self):
        if self.is_animating:
            self.stop_animation()
        else:
            self.start_animation()

    def set_progress_slider(self, slider):
        self.progress_slider = slider
        self.progress_slider.valueChanged.connect(self.on_slider_moved)
        self._recalc_max_time()
        self.set_simulation_time(0.0)

    def set_time_label(self, label):
        self.time_label = label
        self._update_time_display()

    def on_slider_moved(self, value):
        if self.is_animating:
            self.stop_animation()
        if self.max_time > 0:
            sim_time = value / self.progress_slider.maximum() * self.max_time
        else:
            sim_time = 0.0
        self.set_simulation_time(sim_time)

    def clear_active_points(self):
        if self.active_index >= 0:
            self.trajectories[self.active_index].points.clear()
            self.trajectories[self.active_index].compute_segments()
            self._recalc_max_time()
            self._update_all_positions()

    # ========== Мышь ==========
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.drag_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if self.is_animating:
            return

        world_pos = self.screen_to_world(event.position())

        if self.drawing_mode == "radar" and event.button() == Qt.MouseButton.LeftButton:
            self._add_radar_at(world_pos)
            return
        if self.drawing_mode == "launchpad" and event.button() == Qt.MouseButton.LeftButton:
            self._add_launchpad_at(world_pos)
            return
        if self.drawing_mode == "trajectory":
            if event.button() == Qt.MouseButton.LeftButton:
                if self.active_index < 0:
                    return
                traj = self.trajectories[self.active_index]
                traj.points.append(world_pos)
                traj.compute_segments()
                self._recalc_max_time()
                self.update()
                self._update_all_positions()
            elif event.button() == Qt.MouseButton.RightButton:
                if self.active_index < 0:
                    return
                traj = self.trajectories[self.active_index]
                if traj.points:
                    traj.points.pop()
                    traj.compute_segments()
                    self._recalc_max_time()
                    self.update()
                    self._update_all_positions()

    def _add_radar_at(self, pos):
        dialog = ObjectCreationDialog(
            "Новый радар",
            [
                {"key": "max_range", "label": "Макс. дальность (пикс):", "value": 100, "min": 1, "max": 1000},
                {"key": "view_angle", "label": "Угол обзора (градусы):", "value": 90, "min": 1, "max": 360},
                {"key": "rot_speed", "label": "Скорость вращения (град/сек):", "value": 45, "min": 1, "max": 360},
            ],
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values["name"]:
            return
        self.add_radar(values["name"], pos, values["max_range"], values["view_angle"], values["rot_speed"])

    def _add_launchpad_at(self, pos):
        dialog = ObjectCreationDialog(
            "Новая пусковая установка",
            [
                {"key": "missile_speed", "label": "Скорость ракеты (пикс/сек):", "value": 200, "min": 1, "max": 1000},
                {"key": "launch_range", "label": "Дальность пуска (пикс):", "value": 200, "min": 1, "max": 1000},
                {"key": "missile_lifetime", "label": "Время жизни без цели (сек):", "value": 5, "min": 0.5, "max": 30, "step": 0.5},
            ],
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values["name"]:
            return
        self.add_launch_pad(
            values["name"],
            pos,
            values["missile_speed"],
            values["launch_range"],
            values["missile_lifetime"],
        )

    # ========== Отрисовка ==========
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.save()
        painter.translate(self.view_offset)
        painter.scale(self.zoom_level, self.zoom_level)

        if self.background_image and not self.background_image.isNull():
            painter.setOpacity(self.background_opacity)
            painter.drawPixmap(0, 0, self.background_image)
            painter.setOpacity(1.0)

        painter.restore()
        self.draw_grid(painter)

        painter.save()
        painter.translate(self.view_offset)
        painter.scale(self.zoom_level, self.zoom_level)

        for index, traj in enumerate(self.trajectories):
            if traj.points:
                painter.setPen(QPen(traj.color, 1 / self.zoom_level))
                painter.setBrush(QBrush(traj.color))
                for point in traj.points:
                    painter.drawEllipse(point, 5 / self.zoom_level, 5 / self.zoom_level)
                for point_index in range(1, len(traj.points)):
                    painter.drawLine(traj.points[point_index - 1], traj.points[point_index])

            pos = traj.get_position(self.simulation_time)
            if pos:
                if self.is_target_visible_by_any_radar(pos):
                    color = QColor(255, 0, 0)
                else:
                    color = QColor(0, 255, 0) if index == self.active_index else QColor(0, 200, 0)
                painter.setPen(QPen(color, 2 / self.zoom_level))
                painter.setBrush(QBrush(color))
                painter.drawEllipse(pos, 6 / self.zoom_level, 6 / self.zoom_level)

        for radar in self.radars:
            painter.setPen(QPen(Qt.GlobalColor.blue, 2 / self.zoom_level))
            painter.setBrush(QBrush(Qt.GlobalColor.blue))
            painter.drawEllipse(radar.center, 5 / self.zoom_level, 5 / self.zoom_level)
            painter.setPen(
                QPen(Qt.GlobalColor.darkBlue, 1 / self.zoom_level, Qt.PenStyle.DashLine)
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(radar.center, radar.max_range, radar.max_range)

            current_angle = radar.get_current_angle(self.simulation_time)
            half = radar.view_angle / 2.0
            start = current_angle - half
            path = QPainterPath()
            path.moveTo(radar.center)
            rect = QRectF(
                radar.center.x() - radar.max_range,
                radar.center.y() - radar.max_range,
                2 * radar.max_range,
                2 * radar.max_range,
            )
            path.arcTo(rect, start, radar.view_angle)
            path.closeSubpath()
            painter.fillPath(path, QColor(255, 255, 0, 80))
            painter.setPen(QPen(Qt.GlobalColor.yellow, 1 / self.zoom_level))
            painter.drawPath(path)

        for pad in self.launch_pads:
            painter.setPen(
                QPen(Qt.GlobalColor.darkMagenta, 1 / self.zoom_level, Qt.PenStyle.DashLine)
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(pad.center, pad.launch_range, pad.launch_range)

            painter.setPen(QPen(Qt.GlobalColor.magenta, 2 / self.zoom_level))
            painter.setBrush(QBrush(Qt.GlobalColor.magenta))
            size = 10 / self.zoom_level
            painter.drawRect(
                QRectF(
                    pad.center.x() - size / 2,
                    pad.center.y() - size / 2,
                    size,
                    size,
                )
            )

        for pad in self.launch_pads:
            for missile in pad.missiles:
                size = 8 / self.zoom_level
                points = [
                    QPointF(missile.pos.x(), missile.pos.y() - size),
                    QPointF(missile.pos.x() - size * 0.7, missile.pos.y() + size * 0.5),
                    QPointF(missile.pos.x() + size * 0.7, missile.pos.y() + size * 0.5),
                ]
                painter.setBrush(QBrush(QColor(255, 165, 0)))
                painter.setPen(QPen(Qt.GlobalColor.black, 1 / self.zoom_level))
                painter.drawPolygon(QPolygonF(points))

        painter.restore()

    # ========== Сохранение/загрузка сценария ==========
    def save_scene(self, path):
        data = {
            "version": 3,
            "map_scale": self.map_scale,
            "show_grid": self.show_grid,
            "background": {
                "path": self.background_path,
                "opacity": self.background_opacity,
            }
            if self.background_path
            else None,
            "trajectories": [traj.to_dict() for traj in self.trajectories],
            "radars": [radar.to_dict() for radar in self.radars],
            "launchpads": [pad.to_dict() for pad in self.launch_pads],
        }
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            self._show_status(f"Сценарий сохранён в {path}")
        except Exception as error:
            self._show_status(f"Ошибка сохранения: {error}")

    def load_scene(self, path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except Exception as error:
            self._show_status(f"Ошибка загрузки: {error}")
            return

        self.stop_animation()
        self.trajectories.clear()
        self.radars.clear()
        self.launch_pads.clear()
        self.detected_pairs.clear()
        for td in data.get("trajectories", []):
            self.trajectories.append(Trajectory.from_dict(td))
        for rd in data.get("radars", []):
            self.radars.append(Radar.from_dict(rd))
        for pd in data.get("launchpads", []):
            self.launch_pads.append(LaunchPad.from_dict(pd))
        self.active_index = 0 if self.trajectories else -1
        self._recalc_max_time()
        self.set_simulation_time(0.0)
        self.trajectory_list_changed.emit()
        self.radar_list_changed.emit()
        self.launchpad_list_changed.emit()
        self.update()
        self._show_status(f"Сценарий загружен из {path}")

    def _show_status(self, msg):
        if self.parent() and hasattr(self.parent(), "statusBar"):
            self.parent().statusBar.showMessage(msg, 2000)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Симуляция траекторий, радаров и пусковых установок")
        self.setGeometry(100,100,1300,750)

        self.changes_made = False
        self.logger = EventLogger("logs/simulation.log")

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = PointCanvas(self)

        view_group = QWidget()
        view_layout = QHBoxLayout(view_group)
        view_layout.setContentsMargins(0, 0, 0, 0)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(32, 28)
        zoom_in_btn.setToolTip("Приблизить")
        zoom_in_btn.clicked.connect(self.canvas.zoom_in)
        view_layout.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setFixedSize(32, 28)
        zoom_out_btn.setToolTip("Отдалить")
        zoom_out_btn.clicked.connect(self.canvas.zoom_out)
        view_layout.addWidget(zoom_out_btn)

        reset_view_btn = QPushButton("Сброс вида")
        reset_view_btn.clicked.connect(self.canvas.reset_view)
        view_layout.addWidget(reset_view_btn)

        self.zoom_label = QLabel("Масштаб: 100%")
        view_layout.addWidget(self.zoom_label)
        top_layout.addWidget(view_group)

        top_layout.addWidget(QLabel("|"))

        scale_group = QWidget()
        scale_layout = QHBoxLayout(scale_group)
        scale_layout.setContentsMargins(0, 0, 0, 0)
        scale_layout.addWidget(QLabel("Масштаб карты:"))

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.1, 100000.0)
        self.scale_spin.setDecimals(1)
        self.scale_spin.setValue(METERS_PER_PIXEL)
        self.scale_spin.setSuffix(" м/пикс")
        self.scale_spin.setToolTip("Сколько метров соответствует одному пикселю карты")
        self.scale_spin.valueChanged.connect(self.on_scale_changed)
        scale_layout.addWidget(self.scale_spin)
        top_layout.addWidget(scale_group)

        top_layout.addWidget(QLabel("|"))

        sim_group = QWidget()
        sim_layout = QHBoxLayout(sim_group)
        sim_layout.setContentsMargins(0, 0, 0, 0)

        self.reset_btn = QPushButton("Сбросить всё")
        self.reset_btn.clicked.connect(self.canvas.reset_all)
        sim_layout.addWidget(self.reset_btn)

        self.sim_btn = QPushButton("Симулировать")
        self.sim_btn.clicked.connect(self.canvas.simulate)
        sim_layout.addWidget(self.sim_btn)

        sim_layout.addWidget(QLabel("Лимит (с):"))
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0, MAX_SIMULATION_DURATION_S)
        self.duration_spin.setDecimals(1)
        self.duration_spin.setSingleStep(10.0)
        self.duration_spin.setSpecialValueText("Авто")
        self.duration_spin.setToolTip(
            "0 = авто по сцене. Любое значение больше 0 задаёт точную длительность симуляции."
        )
        self.duration_spin.setValue(0.0)
        self.duration_spin.valueChanged.connect(self.canvas.set_simulation_duration_override)
        sim_layout.addWidget(self.duration_spin)

        sim_layout.addWidget(QLabel("Скорость:"))
        self.playback_speed_spin = QDoubleSpinBox()
        self.playback_speed_spin.setRange(0.1, 100.0)
        self.playback_speed_spin.setDecimals(1)
        self.playback_speed_spin.setSingleStep(1.0)
        self.playback_speed_spin.setSuffix("x")
        self.playback_speed_spin.setValue(DEFAULT_PLAYBACK_SPEED)
        self.playback_speed_spin.setToolTip(
            "Во сколько раз быстрее идёт симуляционное время относительно реального."
        )
        self.playback_speed_spin.valueChanged.connect(self.canvas.set_playback_speed)
        sim_layout.addWidget(self.playback_speed_spin)
        top_layout.addWidget(sim_group)

        top_layout.addWidget(QLabel("Время:"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setValue(0)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setToolTip("Временная шкала")
        top_layout.addWidget(self.slider)

        self.time_value_label = QLabel("0.0 / 0.0 c")
        self.time_value_label.setMinimumWidth(110)
        top_layout.addWidget(self.time_value_label)

        main_layout.addWidget(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.canvas)

        tabs = QTabWidget()
        tabs.setMaximumWidth(380)

        traj_widget = QWidget()
        traj_layout = QVBoxLayout(traj_widget)

        self.traj_list = QListWidget()
        self.traj_list.itemClicked.connect(self.on_trajectory_selected)
        self.traj_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.traj_list.customContextMenuRequested.connect(self.show_trajectory_menu)
        traj_layout.addWidget(QLabel("Траектории:"))
        traj_layout.addWidget(self.traj_list)

        traj_buttons = QHBoxLayout()
        btn_new_traj = QPushButton("Новая")
        btn_new_traj.clicked.connect(self.add_trajectory)
        traj_buttons.addWidget(btn_new_traj)
        btn_remove_traj = QPushButton("Удалить")
        btn_remove_traj.clicked.connect(self.remove_trajectory)
        traj_buttons.addWidget(btn_remove_traj)
        btn_clear_traj = QPushButton("Очистить точки")
        btn_clear_traj.clicked.connect(self.canvas.clear_active_points)
        traj_buttons.addWidget(btn_clear_traj)
        traj_layout.addLayout(traj_buttons)

        grp_speed = QGroupBox("Параметры активной траектории")
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Скорость (м/с):"))
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.1, 10000.0)
        self.speed_spin.setDecimals(1)
        self.speed_spin.setValue(DEFAULT_TARGET_SPEED_MPS)
        speed_layout.addWidget(self.speed_spin)
        btn_apply_speed = QPushButton("Применить")
        btn_apply_speed.clicked.connect(self.apply_speed)
        speed_layout.addWidget(btn_apply_speed)
        grp_speed.setLayout(speed_layout)
        traj_layout.addWidget(grp_speed)

        tabs.addTab(traj_widget, "Траектории")

        radar_widget = QWidget()
        radar_layout = QVBoxLayout(radar_widget)

        self.radar_list = QListWidget()
        self.radar_list.itemClicked.connect(self.on_radar_selected)
        radar_layout.addWidget(QLabel("Радары:"))
        radar_layout.addWidget(self.radar_list)

        radar_buttons = QHBoxLayout()
        btn_remove_radar = QPushButton("Удалить")
        btn_remove_radar.clicked.connect(self.remove_radar)
        radar_buttons.addWidget(btn_remove_radar)
        radar_layout.addLayout(radar_buttons)

        grp_radar = QGroupBox("Параметры радара")
        form_radar = QFormLayout()
        self.radar_name = QLineEdit()
        self.radar_name.setPlaceholderText(DEFAULT_RADAR_NAME)
        self.radar_range = QDoubleSpinBox()
        self.radar_range.setRange(1.0, 2000000.0)
        self.radar_range.setDecimals(1)
        self.radar_range.setSuffix(" м")
        self.radar_range.setValue(DEFAULT_RADAR_RANGE_M)
        self.radar_angle = QDoubleSpinBox()
        self.radar_angle.setRange(1.0, 360.0)
        self.radar_angle.setDecimals(1)
        self.radar_angle.setSuffix(" °")
        self.radar_angle.setValue(DEFAULT_RADAR_VIEW_ANGLE)
        self.radar_speed = QDoubleSpinBox()
        self.radar_speed.setRange(0.1, 360.0)
        self.radar_speed.setDecimals(1)
        self.radar_speed.setValue(DEFAULT_RADAR_ROTATION_SPEED)
        self.radar_speed.setSuffix(" °/с")
        btn_apply_radar = QPushButton("Применить")
        btn_apply_radar.clicked.connect(self.apply_radar)
        form_radar.addRow("Имя:", self.radar_name)
        form_radar.addRow("Дальность:", self.radar_range)
        form_radar.addRow("Угол обзора:", self.radar_angle)
        form_radar.addRow("Скорость вращения:", self.radar_speed)
        form_radar.addRow(btn_apply_radar)
        grp_radar.setLayout(form_radar)
        radar_layout.addWidget(grp_radar)

        log_group = QGroupBox("Лог обнаружений")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        btn_clear_log = QPushButton("Очистить лог")
        btn_clear_log.clicked.connect(self.clear_log)
        log_layout.addWidget(btn_clear_log)
        log_group.setLayout(log_layout)
        radar_layout.addWidget(log_group)

        tabs.addTab(radar_widget, "Радары")

        launch_widget = QWidget()
        launch_layout = QVBoxLayout(launch_widget)

        self.launch_list = QListWidget()
        self.launch_list.itemClicked.connect(self.on_launch_selected)
        launch_layout.addWidget(QLabel("Пусковые установки:"))
        launch_layout.addWidget(self.launch_list)

        launch_buttons = QHBoxLayout()
        btn_remove_launch = QPushButton("Удалить")
        btn_remove_launch.clicked.connect(self.remove_launch)
        launch_buttons.addWidget(btn_remove_launch)
        launch_layout.addLayout(launch_buttons)

        grp_launch = QGroupBox("Параметры пусковой установки")
        form_launch = QFormLayout()
        self.launch_name = QLineEdit()
        self.launch_name.setPlaceholderText(DEFAULT_LAUNCHPAD_NAME)
        self.launch_missile_speed = QDoubleSpinBox()
        self.launch_missile_speed.setRange(1.0, 10000.0)
        self.launch_missile_speed.setDecimals(1)
        self.launch_missile_speed.setValue(DEFAULT_MISSILE_SPEED_MPS)
        self.launch_missile_speed.setSuffix(" м/с")
        self.launch_range = QDoubleSpinBox()
        self.launch_range.setRange(1.0, 1000000.0)
        self.launch_range.setDecimals(1)
        self.launch_range.setValue(DEFAULT_MISSILE_RANGE_M)
        self.launch_range.setSuffix(" м")
        self.launch_lifetime = QDoubleSpinBox()
        self.launch_lifetime.setRange(0.5, 3600.0)
        self.launch_lifetime.setDecimals(1)
        self.launch_lifetime.setValue(DEFAULT_MISSILE_LIFETIME)
        self.launch_lifetime.setSuffix(" с")
        btn_apply_launch = QPushButton("Применить")
        btn_apply_launch.clicked.connect(self.apply_launch)
        form_launch.addRow("Имя:", self.launch_name)
        form_launch.addRow("Скорость ракеты:", self.launch_missile_speed)
        form_launch.addRow("Дальность пуска:", self.launch_range)
        form_launch.addRow("Время жизни:", self.launch_lifetime)
        form_launch.addRow(btn_apply_launch)
        grp_launch.setLayout(form_launch)
        launch_layout.addWidget(grp_launch)

        tabs.addTab(launch_widget, "Пусковые установки")

        splitter.addWidget(tabs)
        splitter.setSizes([950, 420])
        main_layout.addWidget(splitter)

        toolbar = QToolBar("Файл")
        self.addToolBar(toolbar)
        toolbar.setMovable(False)

        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self.save_scene)
        toolbar.addWidget(btn_save)

        btn_load = QPushButton("Загрузить")
        btn_load.clicked.connect(self.load_scene)
        toolbar.addWidget(btn_load)

        btn_new = QPushButton("Новый сценарий")
        btn_new.clicked.connect(self.create_new_scenario)
        toolbar.addWidget(btn_new)

        toolbar.addSeparator()

        btn_set_bg = QPushButton("Установить фон")
        btn_set_bg.clicked.connect(self.set_background)
        toolbar.addWidget(btn_set_bg)

        btn_remove_bg = QPushButton("Удалить фон")
        btn_remove_bg.clicked.connect(self.remove_background)
        toolbar.addWidget(btn_remove_bg)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        # Сигналы
        self.canvas.event_signal.connect(self.log_event)
        self.canvas.target_detected.connect(self.on_target_detected)
        self.canvas.trajectory_list_changed.connect(self.refresh_trajectory_list)
        self.canvas.radar_list_changed.connect(self.refresh_radar_list)
        self.canvas.launchpad_list_changed.connect(self.refresh_launch_list)
        self.canvas.trajectory_list_changed.connect(self.on_data_changed)
        self.canvas.radar_list_changed.connect(self.on_data_changed)
        self.canvas.launchpad_list_changed.connect(self.on_data_changed)

        self.canvas.add_trajectory(DEFAULT_TARGET_NAME)
        self.canvas.set_progress_slider(self.slider)
        self.canvas.set_time_label(self.time_value_label)

        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(self.canvas.zoom_in)
        self.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(self.canvas.zoom_out)
        self.addAction(zoom_out_action)

        reset_view_action = QAction("Reset View", self)
        reset_view_action.setShortcut("Ctrl+0")
        reset_view_action.triggered.connect(self.canvas.reset_view)
        self.addAction(reset_view_action)

        tabs.currentChanged.connect(self.on_tab_changed)

        self.refresh_trajectory_list()
        self.refresh_radar_list()
        self.refresh_launch_list()
        self.on_tab_changed(0)

        self.zoom_update_timer = QTimer()
        self.zoom_update_timer.timeout.connect(self.update_zoom_display)
        self.zoom_update_timer.start(100)

        self.statusBar.showMessage(
            "Готово. Колесо мыши — масштаб, средняя кнопка — перемещение карты."
        )

    # ========== Обработчики вкладок ==========
    def on_tab_changed(self, idx):
        if idx == 0:
            self.canvas.drawing_mode = "trajectory"
            self.statusBar.showMessage(
                "Режим: Траектория. ЛКМ — точка, ПКМ — удалить. Средняя кнопка — перемещение карты."
            )
        elif idx == 1:
            self.canvas.drawing_mode = "radar"
            self.statusBar.showMessage("Режим: Радар. ЛКМ — установить радар.")
        else:
            self.canvas.drawing_mode = "launchpad"
            self.statusBar.showMessage("Режим: Пусковая установка. ЛКМ — установить пусковую.")

    # ========== Траектории ==========
    def refresh_trajectory_list(self):
        self.traj_list.clear()
        for index, traj in enumerate(self.canvas.trajectories):
            pixmap = QPixmap(16, 16)
            pixmap.fill(traj.color)
            icon = QIcon(pixmap)
            speed_mps = self.canvas.world_to_mps_speed(traj.speed)
            item = QListWidgetItem(icon, f"{traj.name} (скорость: {speed_mps:.0f} м/с)")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.traj_list.addItem(item)
        if self.canvas.active_index >= 0:
            self.traj_list.setCurrentRow(self.canvas.active_index)
            speed_mps = self.canvas.world_to_mps_speed(
                self.canvas.trajectories[self.canvas.active_index].speed
            )
            self.speed_spin.setValue(speed_mps)

    def on_trajectory_selected(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        self.canvas.set_active_trajectory(idx)
        self.speed_spin.setValue(self.canvas.world_to_mps_speed(self.canvas.trajectories[idx].speed))
        self.refresh_trajectory_list()

    def show_trajectory_menu(self, pos):
        item = self.traj_list.itemAt(pos)
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu()
        act_rename = QAction("Переименовать", self)
        act_rename.triggered.connect(lambda: self.rename_trajectory(item))
        act_remove = QAction("Удалить", self)
        act_remove.triggered.connect(lambda: self.canvas.remove_trajectory(idx))
        menu.addAction(act_rename)
        menu.addAction(act_remove)
        menu.exec(self.traj_list.mapToGlobal(pos))

    def add_trajectory(self):
        default_name = (
            f"{DEFAULT_TARGET_NAME} {len(self.canvas.trajectories)+1}"
            if self.canvas.trajectories
            else DEFAULT_TARGET_NAME
        )
        name, ok = QInputDialog.getText(self, "Новая траектория", "Имя:", text=default_name)
        if not ok:
            name = None
        self.canvas.add_trajectory(name)

    def remove_trajectory(self):
        current = self.traj_list.currentRow()
        if current >= 0:
            self.canvas.remove_trajectory(current)

    def rename_trajectory(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        traj = self.canvas.trajectories[idx]
        new_name, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=traj.name)
        if ok and new_name:
            traj.name = new_name
            self.refresh_trajectory_list()

    def apply_speed(self):
        if self.canvas.active_index >= 0:
            self.canvas.set_trajectory_speed(
                self.canvas.active_index,
                self.canvas.mps_to_world_speed(self.speed_spin.value()),
            )
            self.refresh_trajectory_list()

    # ========== Радары ==========
    def refresh_radar_list(self):
        self.radar_list.clear()
        for index, radar in enumerate(self.canvas.radars):
            range_km = self.canvas.world_to_meters_distance(radar.max_range) / 1000.0
            item = QListWidgetItem(f"{radar.name} (R={range_km:.0f} км, α={radar.view_angle:.1f}°)")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.radar_list.addItem(item)

    def on_radar_selected(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        radar = self.canvas.radars[idx]
        self.radar_name.setText(radar.name)
        self.radar_range.setValue(self.canvas.world_to_meters_distance(radar.max_range))
        self.radar_angle.setValue(radar.view_angle)
        self.radar_speed.setValue(radar.rotation_speed)

    def remove_radar(self):
        current = self.radar_list.currentRow()
        if current >= 0:
            self.canvas.remove_radar(current)
            self.radar_name.clear()
            self.radar_range.setValue(DEFAULT_RADAR_RANGE_M)
            self.radar_angle.setValue(DEFAULT_RADAR_VIEW_ANGLE)
            self.radar_speed.setValue(DEFAULT_RADAR_ROTATION_SPEED)

    def apply_radar(self):
        current = self.radar_list.currentRow()
        if current >= 0:
            name = self.radar_name.text() or DEFAULT_RADAR_NAME
            self.canvas.update_radar(
                current,
                name,
                self.canvas.meters_to_world_distance(self.radar_range.value()),
                self.radar_angle.value(),
                self.radar_speed.value(),
            )
            self.refresh_radar_list()

    # ========== Пусковые установки ==========
    def refresh_launch_list(self):
        self.launch_list.clear()
        for index, pad in enumerate(self.canvas.launch_pads):
            range_km = self.canvas.world_to_meters_distance(pad.launch_range) / 1000.0
            speed_mps = self.canvas.world_to_mps_speed(pad.missile_speed)
            item = QListWidgetItem(f"{pad.name} (R={range_km:.0f} км, v={speed_mps:.0f} м/с)")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.launch_list.addItem(item)

    def on_launch_selected(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        pad = self.canvas.launch_pads[idx]
        self.launch_name.setText(pad.name)
        self.launch_missile_speed.setValue(self.canvas.world_to_mps_speed(pad.missile_speed))
        self.launch_range.setValue(self.canvas.world_to_meters_distance(pad.launch_range))
        self.launch_lifetime.setValue(pad.missile_lifetime)

    def remove_launch(self):
        current = self.launch_list.currentRow()
        if current >= 0:
            self.canvas.remove_launch_pad(current)
            self.launch_name.clear()
            self.launch_missile_speed.setValue(DEFAULT_MISSILE_SPEED_MPS)
            self.launch_range.setValue(DEFAULT_MISSILE_RANGE_M)
            self.launch_lifetime.setValue(DEFAULT_MISSILE_LIFETIME)

    def apply_launch(self):
        current = self.launch_list.currentRow()
        if current >= 0:
            name = self.launch_name.text() or DEFAULT_LAUNCHPAD_NAME
            self.canvas.update_launch_pad(
                current,
                name,
                self.canvas.mps_to_world_speed(self.launch_missile_speed.value()),
                self.canvas.meters_to_world_distance(self.launch_range.value()),
                self.launch_lifetime.value(),
            )
            self.refresh_launch_list()

    # ========== Обнаружение целей и запуск ракет ==========
    def on_target_detected(self, traj, pos):
        for pad in self.canvas.launch_pads:
            if pad.can_launch(pos):
                already = any(missile.target_traj == traj for missile in pad.missiles)
                if not already:
                    self.log_event(f"Командный центр отправил команду установке {pad.name} сбить цель {traj.name}")
                    pad.launch_missile(traj, pos, self.canvas.simulation_time)
                    self.statusBar.showMessage(
                        f"Пусковая установка '{pad.name}' запустила ракету по '{traj.name}'",
                        2000,
                    )

    # ========== Лог ==========
    def log_event(self, msg):
        entry = self.logger.log(msg)
        self.log_text.append(entry)
        self.log_text.ensureCursorVisible()

    def clear_log(self):
        self.log_text.clear()
        self.statusBar.showMessage("Лог в окне очищен. Файл логов сохранён.", 2000)

    # ========== Сохранение/загрузка ==========
    def save_scene(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить сценарий", "scene.json", "JSON (*.json)")
        if path:
            self.canvas.save_scene(path)
            self.changes_made = False
            self.statusBar.showMessage(f"Сценарий сохранён в {path}", 2000)
            return True
        return False

    def load_scene(self):
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить сценарий", "", "JSON (*.json)")
        if path:
            self.canvas.load_scene(path)
            self.changes_made = False
            self.scale_spin.blockSignals(True)
            self.scale_spin.setValue(self.canvas.map_scale)
            self.scale_spin.blockSignals(False)
            self.refresh_trajectory_list()
            self.refresh_radar_list()
            self.refresh_launch_list()
            self.statusBar.showMessage(f"Сценарий загружен из {path}", 2000)

    # ========== Новый сценарий ==========
    def on_data_changed(self):
        self.changes_made = True

    def clear_current_scenario(self):
        self.canvas.stop_animation()
        self.canvas.trajectories.clear()
        self.canvas.radars.clear()
        self.canvas.launch_pads.clear()
        self.canvas.detected_pairs.clear()
        self.canvas.active_index = -1
        self.canvas.remove_background()
        self.canvas.set_map_scale(METERS_PER_PIXEL, rescale_objects=False)
        self.scale_spin.blockSignals(True)
        self.scale_spin.setValue(METERS_PER_PIXEL)
        self.scale_spin.blockSignals(False)
        self.canvas._recalc_max_time()
        self.canvas.set_simulation_time(0.0)
        self.canvas.trajectory_list_changed.emit()
        self.canvas.radar_list_changed.emit()
        self.canvas.launchpad_list_changed.emit()
        self.canvas.update()
        self.changes_made = False
        self.log_event("Создан новый сценарий")
        self.statusBar.showMessage("Создан новый сценарий", 2000)

    def prompt_save_changes(self):
        reply = QMessageBox.question(
            self,
            "Новый сценарий",
            "У вас есть несохранённые изменения. Сохранить их перед созданием нового сценария?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if reply == QMessageBox.StandardButton.Save:
            if self.save_scene():
                self.clear_current_scenario()
        elif reply == QMessageBox.StandardButton.Discard:
            self.clear_current_scenario()

    def create_new_scenario(self):
        if self.changes_made:
            self.prompt_save_changes()
        else:
            self.clear_current_scenario()

    # ========== Масштаб ==========
    def on_scale_changed(self, value):
        self.canvas.set_map_scale(value)
        self.refresh_trajectory_list()
        self.refresh_radar_list()
        self.refresh_launch_list()

        if self.canvas.active_index >= 0:
            self.speed_spin.setValue(
                self.canvas.world_to_mps_speed(self.canvas.trajectories[self.canvas.active_index].speed)
            )
        radar_row = self.radar_list.currentRow()
        if radar_row >= 0 and radar_row < len(self.canvas.radars):
            radar = self.canvas.radars[radar_row]
            self.radar_range.setValue(self.canvas.world_to_meters_distance(radar.max_range))
        launch_row = self.launch_list.currentRow()
        if launch_row >= 0 and launch_row < len(self.canvas.launch_pads):
            pad = self.canvas.launch_pads[launch_row]
            self.launch_missile_speed.setValue(self.canvas.world_to_mps_speed(pad.missile_speed))
            self.launch_range.setValue(self.canvas.world_to_meters_distance(pad.launch_range))

    def update_zoom_display(self):
        zoom_percent = int(self.canvas.zoom_level * 100)
        self.zoom_label.setText(f"Масштаб: {zoom_percent}%")

    # ========== Карта ==========
    def set_background(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите фоновое изображение",
            "",
            "Изображения (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        if file_path:
            dialog = ScaleDialog(self.canvas.map_scale, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                scale = dialog.get_scale()
                self.scale_spin.blockSignals(True)
                self.scale_spin.setValue(scale)
                self.scale_spin.blockSignals(False)
                self.canvas.set_map_scale(scale)
                self.canvas.set_background_image(file_path)
                self.refresh_trajectory_list()
                self.refresh_radar_list()
                self.refresh_launch_list()

    def remove_background(self):
        self.canvas.remove_background()
