import time
import json
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                             QPushButton, QStatusBar, QSlider, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QInputDialog, QFileDialog,
                             QMenu, QDoubleSpinBox, QToolBar, QTabWidget, QTextEdit,
                             QGroupBox, QFormLayout, QLineEdit, QSplitter, QMessageBox,
                             QDialog, QDialogButtonBox)
from PyQt6.QtCore import Qt, QPointF, QTimer, pyqtSignal, QRectF, QPoint
from PyQt6.QtGui import QPainter, QBrush, QColor, QPen, QAction, QPixmap, QIcon, QPainterPath, QPolygonF, QTransform

from trajectory import Trajectory
from radar import Radar
from launchpad import LaunchPad

import math
import os


class ScaleDialog(QDialog):
    """Диалог для ввода масштаба карты"""

    def __init__(self, current_scale=100, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Масштаб карты")
        layout = QFormLayout(self)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(1, 100000)
        self.scale_spin.setValue(current_scale)
        self.scale_spin.setSuffix(" м/пикс")
        self.scale_spin.setDecimals(2)
        layout.addRow("Масштаб (метров в пикселе):", self.scale_spin)

        self.info_label = QLabel("Пример: 100 м/пикс = 1 км = 10 пикселей")
        self.info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addRow(self.info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_scale(self):
        return self.scale_spin.value()


class PointCanvas(QWidget):
    detection_signal = pyqtSignal(str)
    target_detected = pyqtSignal(object, QPointF)  # (trajectory, position)
    radar_list_changed = pyqtSignal()
    trajectory_list_changed = pyqtSignal()
    launchpad_list_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(1100, 650)
        self.setMinimumSize(1100, 650)
        self.setStyleSheet("background-color: white;")

        # Масштабирование
        self.zoom_level = 1.0
        self.min_zoom = 0.3
        self.max_zoom = 5.0
        self.zoom_factor = 1.1
        self.view_offset = QPointF(0, 0)  # Смещение вида
        self.drag_start = None  # Начальная точка перетаскивания

        # Масштаб карты (метры на пиксель)
        self.map_scale = 100.0  # 100 метров в 1 пикселе
        self.grid_spacing_meters = 500  # Шаг сетки в метрах
        self.show_grid = True
        self.grid_color = QColor(200, 200, 200)

        # Включение перетаскивания мышью для навигации
        self.setMouseTracking(True)

        self.trajectories = []
        self.active_index = -1
        self.radars = []
        self.launch_pads = []

        self.simulation_time = 0.0
        self.auto_max_time = 0.0
        self.max_time = 0.0
        self.simulation_duration_override = 0.0
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.is_animating = False
        self.last_time = 0.0
        self.progress_slider = None

        self.drawing_mode = "trajectory"  # trajectory, radar, launchpad

        self.background_image = None
        self.background_opacity = 0.7
        self.background_path = None

        self.last_scale_bar_values = None

    # ========== Методы масштабирования ==========
    def zoom_in(self):
        """Приблизить"""
        new_zoom = min(self.zoom_level * self.zoom_factor, self.max_zoom)
        if new_zoom != self.zoom_level:
            center = QPointF(self.width() / 2, self.height() / 2)
            self.view_offset = center - (center - self.view_offset) * (new_zoom / self.zoom_level)
            self.zoom_level = new_zoom
            self.last_scale_bar_values = None  # Сбрасываем кэш
            self.update()

    def zoom_out(self):
        """Отдалить"""
        new_zoom = max(self.zoom_level / self.zoom_factor, self.min_zoom)
        if new_zoom != self.zoom_level:
            center = QPointF(self.width() / 2, self.height() / 2)
            self.view_offset = center - (center - self.view_offset) * (new_zoom / self.zoom_level)
            self.zoom_level = new_zoom
            self.last_scale_bar_values = None  # Сбрасываем кэш
            self.update()

    def reset_view(self):
        """Сбросить масштаб и позицию"""
        self.zoom_level = 1.0
        self.view_offset = QPointF(0, 0)
        self.last_scale_bar_values = None  # Сбрасываем кэш
        self.update()

    def world_to_screen(self, point):
        """Преобразовать мировые координаты в экранные с учетом масштаба и смещения"""
        return QPointF(
            point.x() * self.zoom_level + self.view_offset.x(),
            point.y() * self.zoom_level + self.view_offset.y()
        )

    def resizeEvent(self, event):
        """Обработка изменения размера окна"""
        super().resizeEvent(event)
        self.last_scale_bar_values = None  # Сбрасываем кэш при изменении размера
        self.update()

    def screen_to_world(self, point):
        """Преобразовать экранные координаты в мировые"""
        return QPointF(
            (point.x() - self.view_offset.x()) / self.zoom_level,
            (point.y() - self.view_offset.y()) / self.zoom_level
        )

    def set_map_scale(self, meters_per_pixel):
        """Установить масштаб карты (метров в пикселе)"""
        self.map_scale = max(0.1, meters_per_pixel)
        self.last_scale_bar_values = None
        self.update()
        self._show_status(f"Масштаб карты: 1 пиксель = {self.map_scale:.1f} м")

    def set_grid_spacing(self, meters):
        """Установить шаг сетки в метрах"""
        self.grid_spacing_meters = max(10, meters)
        self.update()

    def toggle_grid(self):
        """Вкл/Выкл сетку"""
        self.show_grid = not self.show_grid
        self.update()

    def draw_grid(self, painter):
        """Отрисовать масштабную сетку с динамическим шагом"""
        if not self.show_grid:
            return

        # Получаем видимую область в мировых координатах
        top_left = self.screen_to_world(QPointF(0, 0))
        bottom_right = self.screen_to_world(QPointF(self.width(), self.height()))

        # Динамически подбираем шаг сетки
        screen_width_m = (bottom_right.x() - top_left.x()) * self.map_scale
        optimal_lines = 8  # Оптимальное количество линий на экране

        # Рассчитываем оптимальный шаг для текущего уровня масштаба
        if screen_width_m > 0:
            optimal_spacing_m = screen_width_m / optimal_lines
            # Выбираем красивый шаг
            magnitude = 10 ** int(math.log10(optimal_spacing_m))
            first_digit = optimal_spacing_m / magnitude

            if first_digit < 2:
                grid_spacing_m = magnitude
            elif first_digit < 5:
                grid_spacing_m = 2 * magnitude
            else:
                grid_spacing_m = 5 * magnitude
        else:
            grid_spacing_m = 500

        # Шаг сетки в пикселях
        grid_spacing_px = grid_spacing_m / self.map_scale

        # Если сетка слишком мелкая - не рисуем подписи
        show_labels = grid_spacing_px >= 40

        # Рисуем линии сетки (полупрозрачные, чтобы не забивать изображение)
        painter.setPen(QPen(self.grid_color, 1, Qt.PenStyle.SolidLine))
        painter.setOpacity(0.25)

        # Находим начальные координаты сетки
        start_x = int(top_left.x() / grid_spacing_px) * grid_spacing_px
        start_y = int(top_left.y() / grid_spacing_px) * grid_spacing_px

        # Вертикальные линии
        x = start_x
        while x <= bottom_right.x():
            screen_x = self.world_to_screen(QPointF(x, 0)).x()
            painter.drawLine(int(screen_x), 0, int(screen_x), self.height())
            x += grid_spacing_px

        # Горизонтальные линии
        y = start_y
        while y <= bottom_right.y():
            screen_y = self.world_to_screen(QPointF(0, y)).y()
            painter.drawLine(0, int(screen_y), self.width(), int(screen_y))
            y += grid_spacing_px

        painter.setOpacity(1.0)

        # Рисуем подписи к сетке
        if show_labels:
            # Увеличиваем шрифт
            font = painter.font()
            font.setPointSize(11)  # Увеличен с 8 до 11
            font.setBold(True)  # Жирный шрифт для лучшей читаемости
            painter.setFont(font)

            # Подписи для вертикальных линий
            x = start_x
            while x <= bottom_right.x():
                if abs(x) > 0.1 or x == 0:
                    screen_x = self.world_to_screen(QPointF(x, 0)).x()
                    distance_m = abs(x * self.map_scale)

                    # Форматируем расстояние
                    if distance_m >= 1000:
                        if distance_m >= 10000:
                            label = f"{distance_m / 1000:.0f} км"
                        else:
                            label = f"{distance_m / 1000:.1f} км"
                    else:
                        if distance_m >= 100:
                            label = f"{distance_m:.0f} м"
                        elif distance_m >= 10:
                            label = f"{distance_m:.0f} м"
                        else:
                            label = f"{distance_m:.0f} м"

                    # Рисуем текст с толстой обводкой
                    # Сначала рисуем черную тень/обводку
                    for offset_x, offset_y in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
                        painter.setPen(QPen(Qt.GlobalColor.black, 1))
                        painter.drawText(int(screen_x) + 5 + offset_x, 18 + offset_y, label)

                    # Затем рисуем белый текст
                    painter.setPen(QPen(Qt.GlobalColor.white, 1))
                    painter.drawText(int(screen_x) + 5, 18, label)
                x += grid_spacing_px

            # Подписи для горизонтальных линий
            y = start_y
            while y <= bottom_right.y():
                if abs(y) > 0.1 or y == 0:
                    screen_y = self.world_to_screen(QPointF(0, y)).y()
                    distance_m = abs(y * self.map_scale)

                    # Форматируем расстояние
                    if distance_m >= 1000:
                        if distance_m >= 10000:
                            label = f"{distance_m / 1000:.0f} км"
                        else:
                            label = f"{distance_m / 1000:.1f} км"
                    else:
                        if distance_m >= 100:
                            label = f"{distance_m:.0f} м"
                        elif distance_m >= 10:
                            label = f"{distance_m:.0f} м"
                        else:
                            label = f"{distance_m:.0f} м"

                    # Рисуем текст с обводкой
                    for offset_x, offset_y in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
                        painter.setPen(QPen(Qt.GlobalColor.black, 1))
                        painter.drawText(5 + offset_x, int(screen_y) - 5 + offset_y, label)

                    painter.setPen(QPen(Qt.GlobalColor.white, 1))
                    painter.drawText(5, int(screen_y) - 5, label)
                y += grid_spacing_px

        # Рисуем масштабную линейку
        self.draw_scale_bar(painter)

    def draw_scale_bar(self, painter):
        """Рисует масштабную линейку в левом нижнем углу (упрощенная версия)"""
        # Проверяем, нужно ли пересчитать значения
        current_values = (self.map_scale, self.zoom_level, self.width(), self.height())

        if self.last_scale_bar_values != current_values:
            # Пересчитываем значения для линейки
            bar_length_pixels = 150  # Длина в экранных пикселях

            # Реальная длина в метрах (с учетом масштаба карты и зума)
            bar_length_meters = bar_length_pixels * self.map_scale / self.zoom_level

            # Выбираем красивое значение для отображения
            if bar_length_meters >= 1000:
                if bar_length_meters >= 10000:
                    display_value = round(bar_length_meters / 1000)
                    unit = "км"
                else:
                    display_value = round(bar_length_meters / 1000, 1)
                    unit = "км"
                bar_length_meters_display = display_value * 1000
                bar_length_pixels_display = bar_length_meters_display * self.zoom_level / self.map_scale
            else:
                if bar_length_meters >= 100:
                    display_value = round(bar_length_meters / 100) * 100
                elif bar_length_meters >= 10:
                    display_value = round(bar_length_meters / 10) * 10
                else:
                    display_value = round(bar_length_meters)
                unit = "м"
                bar_length_meters_display = display_value
                bar_length_pixels_display = bar_length_meters_display * self.zoom_level / self.map_scale

            # Сохраняем рассчитанные значения
            self.last_scale_bar_values = current_values
            self.last_scale_bar_data = {
                'x': 20,
                'y': self.height() - 30,
                'length': bar_length_pixels_display,
                'display_value': display_value,
                'unit': unit
            }

        # Используем кэшированные значения
        data = self.last_scale_bar_data
        x = data['x']
        y = data['y']
        bar_length_pixels_display = data['length']
        display_value = data['display_value']
        unit = data['unit']

        # Обновляем позицию Y если изменился размер окна
        if y != self.height() - 30:
            y = self.height() - 30
            data['y'] = y

        # Рисуем белую линейку (без фона)
        painter.setOpacity(1.0)
        painter.setPen(QPen(Qt.GlobalColor.white, 3))

        # Основная линия
        painter.drawLine(int(x), int(y), int(x + bar_length_pixels_display), int(y))

        # Вертикальные насечки
        painter.drawLine(int(x), int(y - 8), int(x), int(y + 8))
        painter.drawLine(int(x + bar_length_pixels_display), int(y - 8),
                         int(x + bar_length_pixels_display), int(y + 8))

        # Средняя насечка
        if bar_length_pixels_display > 40:
            mid_x = int(x + bar_length_pixels_display / 2)
            painter.drawLine(mid_x, int(y - 5), mid_x, int(y + 5))

        # Черная обводка для линейки
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawLine(int(x), int(y), int(x + bar_length_pixels_display), int(y))
        painter.drawLine(int(x), int(y - 8), int(x), int(y + 8))
        painter.drawLine(int(x + bar_length_pixels_display), int(y - 8),
                         int(x + bar_length_pixels_display), int(y + 8))
        if bar_length_pixels_display > 40:
            mid_x = int(x + bar_length_pixels_display / 2)
            painter.drawLine(mid_x, int(y - 5), mid_x, int(y + 5))

        # Подпись
        font = painter.font()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)

        text = f"{display_value} {unit}"
        text_rect = painter.boundingRect(0, 0, 0, 0, Qt.TextFlag.TextSingleLine, text)
        text_x = int(x + bar_length_pixels_display / 2 - text_rect.width() / 2)

        # Черная обводка для текста
        for offset_x, offset_y in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            painter.drawText(text_x + offset_x, int(y - 10) + offset_y, text)

        # Белый текст поверх
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        painter.drawText(text_x, int(y - 10), text)

    def wheelEvent(self, event):
        """Обработка колесика мыши для масштабирования"""
        # Сохраняем позицию курсора в мировых координатах до масштабирования
        cursor_pos = event.position()
        world_pos_before = self.screen_to_world(cursor_pos)

        # Масштабируем
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()

        # Корректируем смещение чтобы точка под курсором осталась на месте
        world_pos_after = self.screen_to_world(cursor_pos)
        self.view_offset += (world_pos_after - world_pos_before) * self.zoom_level

        self.last_scale_bar_values = None  # Сбрасываем кэш
        self.update()

    def mouseMoveEvent(self, event):
        if self.drag_start is not None:
            # Перетаскивание вида
            delta = event.position() - self.drag_start
            self.view_offset += delta
            self.drag_start = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.drag_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

    # ========== Траектории ==========
    def add_trajectory(self, name=None, points=None, speed=200.0, color=None):
        if name is None:
            name = f"Траектория {len(self.trajectories)+1}"
        traj = Trajectory(name, color, speed)
        if points:
            traj.points = points
            traj.compute_segments()
        self.trajectories.append(traj)
        self.active_index = len(self.trajectories)-1
        self.stop_animation()
        self._recalc_max_time()
        self._update_all_positions()
        self.trajectory_list_changed.emit()
        self.update()
        return traj

    def remove_trajectory(self, idx):
        if 0 <= idx < len(self.trajectories):
            del self.trajectories[idx]
            if self.trajectories:
                self.active_index = min(idx, len(self.trajectories)-1)
            else:
                self.active_index = -1
            self.stop_animation()
            self._recalc_max_time()
            self._update_all_positions()
            self.trajectory_list_changed.emit()
            self.update()

    def set_active_trajectory(self, idx):
        if 0 <= idx < len(self.trajectories):
            self.active_index = idx

    def set_trajectory_speed(self, idx, speed):
        if 0 <= idx < len(self.trajectories):
            self.trajectories[idx].set_speed(speed)
            self._recalc_max_time()
            self._update_all_positions()
            self.update()

    # ========== Радары ==========
    def add_radar(self, name, center, max_range, view_angle, rot_speed):
        radar = Radar(name, center, max_range, view_angle, rot_speed)
        self.radars.append(radar)
        self.radar_list_changed.emit()
        self.update()

    def remove_radar(self, idx):
        if 0 <= idx < len(self.radars):
            del self.radars[idx]
            self.radar_list_changed.emit()
            self.update()

    def update_radar(self, idx, name, max_range, view_angle, rot_speed):
        if 0 <= idx < len(self.radars):
            r = self.radars[idx]
            r.name = name
            r.max_range = max_range
            r.view_angle = view_angle
            r.rotation_speed = rot_speed
            self.radar_list_changed.emit()
            self.update()

    # ========== Пусковые установки ==========
    def add_launch_pad(self, name, center, missile_speed, launch_range, missile_lifetime):
        pad = LaunchPad(name, center, missile_speed, launch_range, missile_lifetime)
        self.launch_pads.append(pad)
        self.launchpad_list_changed.emit()
        self.update()

    def remove_launch_pad(self, idx):
        if 0 <= idx < len(self.launch_pads):
            del self.launch_pads[idx]
            self.launchpad_list_changed.emit()
            self.update()

    def update_launch_pad(self, idx, name, missile_speed, launch_range, missile_lifetime):
        if 0 <= idx < len(self.launch_pads):
            p = self.launch_pads[idx]
            p.name = name
            p.missile_speed = missile_speed
            p.launch_range = launch_range
            p.missile_lifetime = missile_lifetime
            self.launchpad_list_changed.emit()
            self.update()

    # ========== Обновления ==========
    def _get_auto_max_time(self):
        trajectory_times = [t.travel_time for t in self.trajectories if t.travel_time != float('inf')]
        base_time = max(trajectory_times) if trajectory_times else 0.0

        radar_buffer = 0.0
        radar_periods = [360.0 / r.rotation_speed for r in self.radars if r.rotation_speed > 0]
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
        for traj in self.trajectories:
            traj.reset_simulation_state()
        for pad in self.launch_pads:
            pad.reset_simulation_state()

    def set_simulation_duration_override(self, duration):
        self.simulation_duration_override = max(0.0, duration)
        self.stop_animation()
        self._recalc_max_time()

    def _recalc_max_time(self):
        self.auto_max_time = self._get_auto_max_time()
        self.max_time = max(self.auto_max_time, self.simulation_duration_override)
        if self.progress_slider:
            self.progress_slider.blockSignals(True)
            self.progress_slider.setRange(0, int(self.max_time*1000) if self.max_time>0 else 1000)
            self.progress_slider.blockSignals(False)
            if self.simulation_time > self.max_time:
                self.set_simulation_time(self.max_time)
            else:
                self.set_simulation_time(self.simulation_time)

    def _update_all_positions(self):
        if self.progress_slider:
            self.progress_slider.blockSignals(True)
            if self.max_time > 0:
                val = int(self.simulation_time / self.max_time * self.progress_slider.maximum())
            else:
                val = 0
            self.progress_slider.setValue(val)
            self.progress_slider.blockSignals(False)
        self.update()
        self.check_detections()

    def check_detections(self):
        """Проверка обнаружения целей радарами"""
        for radar in self.radars:
            for traj in self.trajectories:
                if traj.is_destroyed:
                    continue
                pos = traj.get_position(self.simulation_time)
                if pos and radar.contains_point(pos, self.simulation_time):
                    # Проверяем, не было ли уже обнаружение от этого радара
                    if hasattr(traj, '_last_detection_time') and traj._last_detection_time == self.simulation_time:
                        continue
                    traj._last_detection_time = self.simulation_time

                    # Конвертируем расстояние в метры
                    dist_px = radar.get_distance_to_point(pos)
                    dist_m = dist_px * self.map_scale
                    self.detection_signal.emit(
                        f"Радар \"{radar.name}\" обнаружил объект \"{traj.name}\" "
                        f"на расстоянии {dist_m:.0f} м"
                    )
                    # Отложенный вызов для избежания рекурсии
                    QTimer.singleShot(0, lambda t=traj, p=pos: self.target_detected.emit(t, p))
    
    # ========== Проверяет, видит ли хотя бы один радар/локатор указанную точку ==========
    def is_target_visible_by_any_radar(self, pos):
        return any(radar.contains_point(pos, self.simulation_time) for radar in self.radars)

    def update_missiles(self, dt):
        for pad in self.launch_pads:
            pad.update_missiles(dt, self.simulation_time, self.radars, self.trajectories)

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
                val = int(self.simulation_time / self.max_time * self.progress_slider.maximum())
            else:
                val = 0
            self.progress_slider.setValue(val)
            self.progress_slider.blockSignals(False)
        dt_actual = self.simulation_time - old
        if dt_actual > 0:
            self.update_missiles(dt_actual)
        self.update()
        self.check_detections()

    def reset_all(self):
        self.stop_animation()
        self._reset_simulation_entities()
        self.set_simulation_time(0.0)

    def start_animation(self):
        if len(self.trajectories)==0 or not any(len(t.points)>=2 for t in self.trajectories):
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
        self.last_time = time.time()
        self.animation_timer.start(20)
        self._show_status("Анимация запущена")

    def update_animation(self):
        if not self.is_animating:
            return
        now = time.time()
        dt = now - self.last_time
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

    def on_slider_moved(self, value):
        if self.is_animating:
            self.stop_animation()
        if self.max_time > 0:
            t = value / self.progress_slider.maximum() * self.max_time
        else:
            t = 0.0
        self.set_simulation_time(t)

    def clear_active_points(self):
        if self.active_index >= 0:
            self.trajectories[self.active_index].points.clear()
            self.trajectories[self.active_index].compute_segments()
            self._recalc_max_time()
            self._update_all_positions()

    # ========== Мышь ==========
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            # Средняя кнопка - начало перетаскивания
            self.drag_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if self.is_animating:
            return

        # Преобразуем координаты клика в мировые
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
        name, ok = QInputDialog.getText(self, "Новый радар", "Имя:")
        if not ok or not name: return
        max_range_m, ok = QInputDialog.getDouble(self, "Дальность", "Макс. дальность (метры):",
                                                 1000, 1, 50000)
        if not ok: return
        # Конвертируем метры в пиксели для внутреннего представления
        max_range_px = max_range_m / self.map_scale

        view_angle, ok = QInputDialog.getDouble(self, "Угол обзора", "Градусы:", 90, 1, 360)
        if not ok: return
        rot_speed, ok = QInputDialog.getDouble(self, "Скорость вращения", "град/сек:", 45, 1, 360)
        if not ok: return

        radar = Radar(name, pos, max_range_px, view_angle, rot_speed)
        self.radars.append(radar)
        self.radar_list_changed.emit()
        self.update()

    def _add_launchpad_at(self, pos):
        name, ok = QInputDialog.getText(self, "Новая пусковая установка", "Имя:")
        if not ok or not name: return
        missile_speed, ok = QInputDialog.getDouble(self, "Скорость ракеты", "м/сек:", 200, 1, 1000)
        if not ok: return
        launch_range_m, ok = QInputDialog.getDouble(self, "Дальность пуска", "метры:", 2000, 1, 50000)
        if not ok: return
        missile_lifetime, ok = QInputDialog.getDouble(self, "Время жизни без цели", "сек:", 5, 0.5, 30)
        if not ok: return

        # Конвертируем в пиксели
        launch_range_px = launch_range_m / self.map_scale

        pad = LaunchPad(name, pos, missile_speed, launch_range_px, missile_lifetime)
        self.launch_pads.append(pad)
        self.launchpad_list_changed.emit()
        self.update()

    # ========== Отрисовка ==========
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Применяем трансформацию масштаба и смещения
        painter.save()
        painter.translate(self.view_offset)
        painter.scale(self.zoom_level, self.zoom_level)

        # Фоновое изображение (масштабируется вместе с видом)
        if self.background_image and not self.background_image.isNull():
            painter.setOpacity(self.background_opacity)
            painter.drawPixmap(0, 0, self.background_image)
            painter.setOpacity(1.0)

        # Масштабная сетка (рисуется в мировых координатах)
        painter.restore()  # Временно отключаем трансформацию для сетки
        self.draw_grid(painter)
        painter.save()
        painter.translate(self.view_offset)
        painter.scale(self.zoom_level, self.zoom_level)

        # Траектории
        for i, traj in enumerate(self.trajectories):
            if traj.points:
                painter.setPen(QPen(traj.color, 1 / self.zoom_level))
                painter.setBrush(QBrush(traj.color))
                for p in traj.points:
                    painter.drawEllipse(p, 5 / self.zoom_level, 5 / self.zoom_level)
                for j in range(1, len(traj.points)):
                    painter.drawLine(traj.points[j - 1], traj.points[j])
            pos = traj.get_position(self.simulation_time)
            pos = traj.get_position(self.simulation_time)
            if pos:
                if self.is_target_visible_by_any_radar(pos):
                    col = QColor(255, 0, 0)  # цель обнаружена
                else:
                    col = QColor(0, 255, 0) if i == self.active_index else QColor(0, 200, 0)

                painter.setPen(QPen(col, 2 / self.zoom_level))
                painter.setBrush(QBrush(col))
                painter.drawEllipse(pos, 6 / self.zoom_level, 6 / self.zoom_level)

        # Радары
        for radar in self.radars:
            painter.setPen(QPen(Qt.GlobalColor.blue, 2 / self.zoom_level))
            painter.setBrush(QBrush(Qt.GlobalColor.blue))
            painter.drawEllipse(radar.center, 5 / self.zoom_level, 5 / self.zoom_level)
            painter.setPen(QPen(Qt.GlobalColor.darkBlue, 1 / self.zoom_level, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(radar.center, radar.max_range, radar.max_range)
            cur_angle = radar.get_current_angle(self.simulation_time)
            half = radar.view_angle / 2.0
            start = cur_angle - half
            path = QPainterPath()
            path.moveTo(radar.center)
            rect = QRectF(radar.center.x() - radar.max_range,
                          radar.center.y() - radar.max_range,
                          2 * radar.max_range, 2 * radar.max_range)
            path.arcTo(rect, start, radar.view_angle)
            path.closeSubpath()
            painter.fillPath(path, QColor(255, 255, 0, 80))
            painter.setPen(QPen(Qt.GlobalColor.yellow, 1 / self.zoom_level))
            painter.drawPath(path)

        # Пусковые установки
        for pad in self.launch_pads:
            # Радиус действия пусковой
            painter.setPen(QPen(Qt.GlobalColor.darkMagenta, 1 / self.zoom_level, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(pad.center, pad.launch_range, pad.launch_range)

            # Центр пусковой установки
            painter.setPen(QPen(Qt.GlobalColor.magenta, 2 / self.zoom_level))
            painter.setBrush(QBrush(Qt.GlobalColor.magenta))
            size = 10 / self.zoom_level
            painter.drawRect(QRectF(
                pad.center.x() - size / 2,
                pad.center.y() - size / 2,
                size,
                size
            ))

        # Ракеты
        for pad in self.launch_pads:
            for m in pad.missiles:
                size = 8 / self.zoom_level
                points = [QPointF(m.pos.x(), m.pos.y() - size),
                          QPointF(m.pos.x() - size * 0.7, m.pos.y() + size * 0.5),
                          QPointF(m.pos.x() + size * 0.7, m.pos.y() + size * 0.5)]
                painter.setBrush(QBrush(QColor(255, 165, 0)))
                painter.setPen(QPen(Qt.GlobalColor.black, 1 / self.zoom_level))
                painter.drawPolygon(QPolygonF(points))

        painter.restore()

    # ========== Сохранение/загрузка сценария ==========
    def save_scene(self, path):
        data = {
            "version": 2,
            "trajectories": [t.to_dict() for t in self.trajectories],
            "radars": [r.to_dict() for r in self.radars],
            "launchpads": [p.to_dict() for p in self.launch_pads]
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            self._show_status(f"Сценарий сохранён в {path}")
        except Exception as e:
            self._show_status(f"Ошибка сохранения: {e}")

    def load_scene(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self._show_status(f"Ошибка загрузки: {e}")
            return
        self.stop_animation()
        self.trajectories.clear()
        self.radars.clear()
        self.launch_pads.clear()
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
        if self.parent() and hasattr(self.parent(), 'statusBar'):
            self.parent().statusBar.showMessage(msg, 2000)

    # ============= Карта =============
    def set_background_image(self, image_path, opacity=0.7):
        """Установить фоновое изображение"""
        if image_path and os.path.exists(image_path):
            self.background_image = QPixmap(image_path)
            self.background_opacity = max(0.0, min(1.0, opacity))
            self.background_path = image_path
            self.update()
            self._show_status(f"Фоновое изображение загружено: {os.path.basename(image_path)}")
            return True
        else:
            self._show_status(f"Не удалось загрузить изображение: {image_path}")
            return False

    def remove_background(self):
        """Удалить фоновое изображение"""
        self.background_image = None
        self.background_path = None
        self.update()
        self._show_status("Фоновое изображение удалено")

    def set_background_opacity(self, opacity):
        """Установить прозрачность фона"""
        self.background_opacity = max(0.0, min(1.0, opacity))
        self.update()



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Симуляция траекторий, радаров и пусковых установок")
        self.setGeometry(100, 100, 1300, 750)
        self.changes_made = False

        self.processing_detection = False  # Добавить эту строку
        self.old_map_scale = 100

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Верхняя панель (упрощенная)
        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = PointCanvas(self)

        # Группа управления видом
        view_group = QWidget()
        view_layout = QHBoxLayout(view_group)
        view_layout.setContentsMargins(0, 0, 0, 0)

        zoom_in_btn = QPushButton("🔍+")
        zoom_in_btn.setFixedSize(40, 30)
        zoom_in_btn.setToolTip("Приблизить (Ctrl++)")
        zoom_in_btn.clicked.connect(self.canvas.zoom_in)
        view_layout.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("🔍-")
        zoom_out_btn.setFixedSize(40, 30)
        zoom_out_btn.setToolTip("Отдалить (Ctrl+-)")
        zoom_out_btn.clicked.connect(self.canvas.zoom_out)
        view_layout.addWidget(zoom_out_btn)

        reset_view_btn = QPushButton("Сброс вида")
        reset_view_btn.setToolTip("Сбросить масштаб и позицию (Ctrl+0)")
        reset_view_btn.clicked.connect(self.canvas.reset_view)
        view_layout.addWidget(reset_view_btn)

        self.zoom_label = QLabel("Масштаб: 100%")
        view_layout.addWidget(self.zoom_label)

        top_layout.addWidget(view_group)

        top_layout.addWidget(QLabel("|"))

        # Группа масштаба карты
        scale_group = QWidget()
        scale_layout = QHBoxLayout(scale_group)
        scale_layout.setContentsMargins(0, 0, 0, 0)

        scale_layout.addWidget(QLabel("Реальный масштаб:"))
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.1, 100000)
        self.scale_spin.setValue(100)
        self.scale_spin.setSuffix(" м/пикс")
        self.scale_spin.setDecimals(1)
        self.scale_spin.setToolTip("Сколько метров в одном пикселе")
        self.scale_spin.valueChanged.connect(self.on_scale_changed)
        scale_layout.addWidget(self.scale_spin)

        top_layout.addWidget(scale_group)

        top_layout.addWidget(QLabel("|"))

        # Группа управления симуляцией
        sim_group = QWidget()
        sim_layout = QHBoxLayout(sim_group)
        sim_layout.setContentsMargins(0, 0, 0, 0)

        self.reset_btn = QPushButton("Сбросить все")
        self.reset_btn.clicked.connect(self.canvas.reset_all)
        sim_layout.addWidget(self.reset_btn)

        self.sim_btn = QPushButton("Симулировать")
        self.sim_btn.clicked.connect(self.canvas.simulate)
        sim_layout.addWidget(self.sim_btn)

        sim_layout.addWidget(QLabel("Лимит времени:"))
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0, 36000)
        self.duration_spin.setDecimals(1)
        self.duration_spin.setSingleStep(5.0)
        self.duration_spin.setSpecialValueText("Авто")
        self.duration_spin.setValue(0.0)
        self.duration_spin.setToolTip("Максимальное время симуляции в секундах (0 = авто)")
        self.duration_spin.valueChanged.connect(self.canvas.set_simulation_duration_override)
        sim_layout.addWidget(self.duration_spin)

        top_layout.addWidget(sim_group)

        # Слайдер времени
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setValue(0)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setToolTip("Временная шкала")
        top_layout.addWidget(self.slider)

        main_layout.addWidget(top)

        # Горизонтальный сплиттер
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.canvas)

        # Вкладки
        tabs = QTabWidget()
        tabs.setMaximumWidth(380)

        # --- Траектории ---
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
        self.speed_spin.setRange(0.1, 10000)
        self.speed_spin.setValue(200)
        speed_layout.addWidget(self.speed_spin)
        btn_apply_speed = QPushButton("Применить")
        btn_apply_speed.clicked.connect(self.apply_speed)
        speed_layout.addWidget(btn_apply_speed)
        grp_speed.setLayout(speed_layout)
        traj_layout.addWidget(grp_speed)

        tabs.addTab(traj_widget, "Траектории")

        # --- Радары ---
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
        self.radar_range = QDoubleSpinBox()
        self.radar_range.setRange(1, 50000)
        self.radar_range.setSuffix(" м")
        self.radar_angle = QDoubleSpinBox()
        self.radar_angle.setRange(1, 360)
        self.radar_angle.setSuffix("°")
        self.radar_speed = QDoubleSpinBox()
        self.radar_speed.setRange(1, 360)
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

        # Лог
        log_group = QGroupBox("Лог обнаружений")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        btn_clear_log = QPushButton("Очистить лог")
        btn_clear_log.clicked.connect(self.log_text.clear)
        log_layout.addWidget(btn_clear_log)
        log_group.setLayout(log_layout)
        radar_layout.addWidget(log_group)

        tabs.addTab(radar_widget, "Радары")

        # --- Пусковые установки ---
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
        self.launch_missile_speed = QDoubleSpinBox()
        self.launch_missile_speed.setRange(1, 3000)
        self.launch_missile_speed.setValue(200)
        self.launch_missile_speed.setSuffix(" м/с")
        self.launch_range = QDoubleSpinBox()
        self.launch_range.setRange(1, 50000)
        self.launch_range.setValue(2000)
        self.launch_range.setSuffix(" м")
        self.launch_lifetime = QDoubleSpinBox()
        self.launch_lifetime.setRange(0.5, 30)
        self.launch_lifetime.setValue(5)
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
        splitter.setSizes([850, 400])
        main_layout.addWidget(splitter)

        # Панель инструментов (упрощенная)
        toolbar = QToolBar("Файл")
        self.addToolBar(toolbar)
        toolbar.setMovable(False)

        btn_save = QPushButton("💾 Сохранить")
        btn_save.clicked.connect(self.save_scene)
        toolbar.addWidget(btn_save)

        btn_load = QPushButton("📂 Загрузить")
        btn_load.clicked.connect(self.load_scene)
        toolbar.addWidget(btn_load)

        btn_new = QPushButton("✨ Новый")
        btn_new.clicked.connect(self.create_new_scenario)
        toolbar.addWidget(btn_new)

        toolbar.addSeparator()

        btn_set_bg = QPushButton("🖼 Установить фон")
        btn_set_bg.clicked.connect(self.set_background)
        toolbar.addWidget(btn_set_bg)

        btn_remove_bg = QPushButton("❌ Удалить фон")
        btn_remove_bg.clicked.connect(self.remove_background)
        toolbar.addWidget(btn_remove_bg)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        # Сигналы
        self.canvas.detection_signal.connect(self.log_detection)
        self.canvas.target_detected.connect(self.on_target_detected)
        self.canvas.trajectory_list_changed.connect(self.refresh_trajectory_list)
        self.canvas.radar_list_changed.connect(self.refresh_radar_list)
        self.canvas.launchpad_list_changed.connect(self.refresh_launch_list)
        self.canvas.trajectory_list_changed.connect(self.on_data_changed)
        self.canvas.radar_list_changed.connect(self.on_data_changed)
        self.canvas.launchpad_list_changed.connect(self.on_data_changed)

        # Инициализация
        self.canvas.add_trajectory("Траектория 1")
        self.canvas.set_progress_slider(self.slider)

        # Горячие клавиши
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

        # Переключение режимов по вкладкам
        tabs.currentChanged.connect(self.on_tab_changed)

        self.refresh_trajectory_list()
        self.refresh_radar_list()
        self.refresh_launch_list()
        self.on_tab_changed(0)

        # Таймер для обновления масштаба
        self.zoom_update_timer = QTimer()
        self.zoom_update_timer.timeout.connect(self.update_zoom_display)
        self.zoom_update_timer.start(100)

        self.old_map_scale = 100
        self.statusBar.showMessage(
            "Готово. Режим: Траектория. ЛКМ — точка, ПКМ — удалить. Средняя кнопка — перемещение карты.")

    # ========== Обработчики вкладок ==========
    def on_tab_changed(self, idx):
        if idx == 0:
            self.canvas.drawing_mode = "trajectory"
            self.statusBar.showMessage("Режим: Траектория. ЛКМ — точка, ПКМ — удалить.")
        elif idx == 1:
            self.canvas.drawing_mode = "radar"
            self.statusBar.showMessage("Режим: Радар. ЛКМ — установить радар.")
        else:
            self.canvas.drawing_mode = "launchpad"
            self.statusBar.showMessage("Режим: Пусковая установка. ЛКМ — установить пусковую установку.")

    # ========== Траектории ==========
    def refresh_trajectory_list(self):
        self.traj_list.clear()
        for i, t in enumerate(self.canvas.trajectories):
            pix = QPixmap(16,16)
            pix.fill(t.color)
            icon = QIcon(pix)
            item = QListWidgetItem(icon, f"{t.name} (спид: {t.speed:.0f})")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.traj_list.addItem(item)
        if self.canvas.active_index >= 0:
            self.traj_list.setCurrentRow(self.canvas.active_index)
            self.speed_spin.setValue(self.canvas.trajectories[self.canvas.active_index].speed)

    def on_trajectory_selected(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        self.canvas.set_active_trajectory(idx)
        self.speed_spin.setValue(self.canvas.trajectories[idx].speed)
        self.refresh_trajectory_list()

    def show_trajectory_menu(self, pos):
        item = self.traj_list.itemAt(pos)
        if not item: return
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
        name, ok = QInputDialog.getText(self, "Новая траектория", "Имя:")
        if not ok: name = None
        self.canvas.add_trajectory(name)

    def remove_trajectory(self):
        cur = self.traj_list.currentRow()
        if cur >= 0:
            self.canvas.remove_trajectory(cur)

    def rename_trajectory(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        t = self.canvas.trajectories[idx]
        new_name, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=t.name)
        if ok and new_name:
            t.name = new_name
            self.refresh_trajectory_list()

    def apply_speed(self):
        if self.canvas.active_index >= 0:
            self.canvas.set_trajectory_speed(self.canvas.active_index, self.speed_spin.value())
            self.refresh_trajectory_list()

    # ========== Радары ==========
    def refresh_radar_list(self):
        self.radar_list.clear()
        for i, r in enumerate(self.canvas.radars):
            item = QListWidgetItem(f"{r.name} (R={r.max_range}, α={r.view_angle}°)")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.radar_list.addItem(item)

    def on_radar_selected(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        r = self.canvas.radars[idx]
        self.radar_name.setText(r.name)
        self.radar_range.setValue(r.max_range)
        self.radar_angle.setValue(r.view_angle)
        self.radar_speed.setValue(r.rotation_speed)

    def remove_radar(self):
        cur = self.radar_list.currentRow()
        if cur >= 0:
            self.canvas.remove_radar(cur)
            self.radar_name.clear()
            self.radar_range.setValue(100)
            self.radar_angle.setValue(90)
            self.radar_speed.setValue(45)

    def apply_radar(self):
        cur = self.radar_list.currentRow()
        if cur >= 0:
            name = self.radar_name.text() or f"Радар {cur+1}"
            self.canvas.update_radar(cur, name, self.radar_range.value(), self.radar_angle.value(), self.radar_speed.value())
            self.refresh_radar_list()

    # ========== Пусковые установки ==========
    def refresh_launch_list(self):
        self.launch_list.clear()
        for i, p in enumerate(self.canvas.launch_pads):
            item = QListWidgetItem(f"{p.name} (R={p.launch_range}, v={p.missile_speed})")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.launch_list.addItem(item)

    def on_launch_selected(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        p = self.canvas.launch_pads[idx]
        self.launch_name.setText(p.name)
        self.launch_missile_speed.setValue(p.missile_speed)
        self.launch_range.setValue(p.launch_range)
        self.launch_lifetime.setValue(p.missile_lifetime)

    def remove_launch(self):
        cur = self.launch_list.currentRow()
        if cur >= 0:
            self.canvas.remove_launch_pad(cur)
            self.launch_name.clear()
            self.launch_missile_speed.setValue(200)
            self.launch_range.setValue(200)
            self.launch_lifetime.setValue(5)

    def apply_launch(self):
        cur = self.launch_list.currentRow()
        if cur >= 0:
            name = self.launch_name.text() or f"Установка {cur+1}"
            self.canvas.update_launch_pad(cur, name, self.launch_missile_speed.value(), self.launch_range.value(), self.launch_lifetime.value())
            self.refresh_launch_list()

    # ========== Обнаружение целей и запуск ракет ==========
    def on_target_detected(self, traj, pos):
        """Обработка обнаружения цели"""
        # Защита от рекурсивных вызовов
        if self.processing_detection:
            return

        self.processing_detection = True

        try:
            for pad in self.canvas.launch_pads:
                # Проверяем, не уничтожена ли уже цель
                if traj.is_destroyed:
                    continue

                if pad.can_launch(pos):
                    # Проверяем, нет ли уже ракеты по этой цели
                    already = any(m.target_traj == traj for m in pad.missiles)
                    if not already:
                        # Используем QTimer для отложенного запуска ракеты
                        from PyQt6.QtCore import QTimer
                        QTimer.singleShot(0, lambda p=pad, t=traj, pos=pos: self.launch_missile(p, t, pos))
        except Exception as e:
            print(f"Ошибка при обработке обнаружения: {e}")
        finally:
            # Сбрасываем флаг через небольшой таймер, чтобы избежать блокировки
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(100, lambda: setattr(self, 'processing_detection', False))

    def launch_missile(self, pad, traj, pos):
        """запуск ракеты"""
        try:
            if not traj.is_destroyed:  # Проверяем, что цель еще существует
                pad.launch_missile(traj, pos, self.canvas.simulation_time)
                self.statusBar.showMessage(f"Пусковая установка '{pad.name}' запустила ракету по '{traj.name}'", 2000)
        except Exception as e:
            print(f"Ошибка при запуске ракеты: {e}")

    # ========== Лог ==========
    def log_detection(self, msg):
        self.log_text.append(msg)
        self.log_text.ensureCursorVisible()

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
        self.canvas.active_index = -1
        self.canvas._recalc_max_time()
        self.canvas.set_simulation_time(0.0)
        self.canvas.trajectory_list_changed.emit()
        self.canvas.radar_list_changed.emit()
        self.canvas.launchpad_list_changed.emit()
        self.canvas.update()
        self.changes_made = False
        self.statusBar.showMessage("Создан новый сценарий", 2000)

    def prompt_save_changes(self):
        reply = QMessageBox.question(
            self,
            "Новый сценарий",
            "У вас есть несохранённые изменения. Сохранить их перед созданием нового сценария?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save
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

    #======Масштаб=======
    def on_scale_changed(self, value):
        """Обработчик изменения реального масштаба карты"""
        self.canvas.set_map_scale(value)
        # При изменении реального масштаба обновляем данные объектов
        self.update_objects_scale(value)

    def on_grid_changed(self, value):
        """Обработчик изменения шага сетки"""
        self.canvas.set_grid_spacing(value)

    def update_zoom_display(self):
        """Обновляет отображение текущего масштаба"""
        zoom_percent = int(self.canvas.zoom_level * 100)
        self.zoom_label.setText(f"Масштаб: {zoom_percent}%")

    def update_objects_scale(self, new_scale):
        """Обновляет параметры объектов при изменении масштаба"""
        old_scale = getattr(self, 'old_map_scale', 100)
        if old_scale == new_scale:
            return

        scale_factor = old_scale / new_scale

        # Обновляем радары
        for radar in self.canvas.radars:
            radar.max_range *= scale_factor

        # Обновляем пусковые установки
        for pad in self.canvas.launch_pads:
            pad.launch_range *= scale_factor

        self.old_map_scale = new_scale
        self.canvas.update()

    #========Карта=========
    def set_background(self):
        """Выбрать и установить фоновое изображение с масштабом"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите фоновое изображение",
            "",
            "Изображения (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            # Сначала запрашиваем масштаб карты
            dialog = ScaleDialog(self.canvas.map_scale, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                scale = dialog.get_scale()
                self.canvas.set_map_scale(scale)
                self.scale_spin.setValue(scale)
                self.canvas.set_background_image(file_path)

    def remove_background(self):
        """Удалить фоновое изображение"""
        self.canvas.remove_background()
