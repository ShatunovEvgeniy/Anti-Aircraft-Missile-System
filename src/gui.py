import time
import json
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                             QPushButton, QStatusBar, QSlider, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QInputDialog, QFileDialog,
                             QMenu, QDoubleSpinBox, QToolBar, QTabWidget, QTextEdit,
                             QGroupBox, QFormLayout, QLineEdit, QSplitter)
from PyQt6.QtCore import Qt, QPointF, QTimer, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QBrush, QColor, QPen, QAction, QPixmap, QIcon, QPainterPath, QPolygonF

from trajectory import Trajectory
from radar import Radar
from launchpad import LaunchPad


class PointCanvas(QWidget):
    detection_signal = pyqtSignal(str)
    target_detected = pyqtSignal(object, QPointF)  # (trajectory, position)
    radar_list_changed = pyqtSignal()
    trajectory_list_changed = pyqtSignal()
    launchpad_list_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400,300)
        self.setStyleSheet("background-color: white;")

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
        for radar in self.radars:
            for traj in self.trajectories:
                if traj.is_destroyed:
                    continue
                pos = traj.get_position(self.simulation_time)
                if pos and radar.contains_point(pos, self.simulation_time):
                    self.detection_signal.emit(f"Радар \"{radar.name}\" обнаружил объект \"{traj.name}\"")
                    self.target_detected.emit(traj, pos)

    def update_missiles(self, dt):
        for pad in self.launch_pads:
            pad.update_missiles(dt, self.simulation_time, self.radars, self.trajectories)

    # ========== Анимация и время ==========
    def set_simulation_time(self, t, dt=0):
        # dt для ракет передаётся отдельно, но мы можем пересчитать из изменения времени
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
        # Обновляем ракеты с dt = изменение времени
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
        if self.is_animating:
            return
        if self.drawing_mode == "radar" and event.button() == Qt.MouseButton.LeftButton:
            self._add_radar_at(event.pos())
            return
        if self.drawing_mode == "launchpad" and event.button() == Qt.MouseButton.LeftButton:
            self._add_launchpad_at(event.pos())
            return
        if self.drawing_mode == "trajectory":
            if event.button() == Qt.MouseButton.LeftButton:
                if self.active_index < 0:
                    return
                traj = self.trajectories[self.active_index]
                traj.points.append(event.pos())
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
        max_range, ok = QInputDialog.getDouble(self, "Дальность", "Макс. дальность (пикс):", 100, 1, 1000)
        if not ok: return
        view_angle, ok = QInputDialog.getDouble(self, "Угол обзора", "Градусы:", 90, 1, 360)
        if not ok: return
        rot_speed, ok = QInputDialog.getDouble(self, "Скорость вращения", "град/сек:", 45, 1, 360)
        if not ok: return
        self.add_radar(name, pos, max_range, view_angle, rot_speed)

    def _add_launchpad_at(self, pos):
        name, ok = QInputDialog.getText(self, "Новая пусковая установка", "Имя:")
        if not ok or not name: return
        missile_speed, ok = QInputDialog.getDouble(self, "Скорость ракеты", "пикс/сек:", 200, 1, 1000)
        if not ok: return
        launch_range, ok = QInputDialog.getDouble(self, "Дальность пуска", "пикс:", 200, 1, 1000)
        if not ok: return
        missile_lifetime, ok = QInputDialog.getDouble(self, "Время жизни без цели", "сек:", 5, 0.5, 30)
        if not ok: return
        self.add_launch_pad(name, pos, missile_speed, launch_range, missile_lifetime)

    # ========== Отрисовка ==========
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Траектории
        for i, traj in enumerate(self.trajectories):
            if traj.points:
                painter.setPen(QPen(traj.color, 1))
                painter.setBrush(QBrush(traj.color))
                for p in traj.points:
                    painter.drawEllipse(p, 5,5)
                for j in range(1,len(traj.points)):
                    painter.drawLine(traj.points[j-1], traj.points[j])
            pos = traj.get_position(self.simulation_time)
            if pos:
                col = QColor(0,255,0) if i==self.active_index else QColor(0,200,0)
                painter.setPen(QPen(col,2))
                painter.setBrush(QBrush(col))
                painter.drawEllipse(pos, 6,6)

        # Радары
        for radar in self.radars:
            painter.setPen(QPen(Qt.GlobalColor.blue,2))
            painter.setBrush(QBrush(Qt.GlobalColor.blue))
            painter.drawEllipse(radar.center, 5,5)
            painter.setPen(QPen(Qt.GlobalColor.darkBlue,1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(radar.center, radar.max_range, radar.max_range)
            cur_angle = radar.get_current_angle(self.simulation_time)
            half = radar.view_angle/2.0
            start = cur_angle - half
            path = QPainterPath()
            path.moveTo(radar.center)
            rect = QRectF(radar.center.x()-radar.max_range, radar.center.y()-radar.max_range, 2*radar.max_range, 2*radar.max_range)
            path.arcTo(rect, start, radar.view_angle)
            path.closeSubpath()
            painter.fillPath(path, QColor(255,255,0,80))
            painter.setPen(QPen(Qt.GlobalColor.yellow,1))
            painter.drawPath(path)

        # Пусковые установки
        for pad in self.launch_pads:
            painter.setPen(QPen(Qt.GlobalColor.magenta,2))
            painter.setBrush(QBrush(Qt.GlobalColor.magenta))
            painter.drawRect(QRectF(pad.center.x()-10, pad.center.y()-10, 20,20))

        # Ракеты
        for pad in self.launch_pads:
            for m in pad.missiles:
                # Треугольник
                angle = 0.0  # можно вычислить по направлению, но для простоты рисуем треугольник вверх
                size = 8
                points = [QPointF(m.pos.x(), m.pos.y()-size),
                          QPointF(m.pos.x()-size*0.7, m.pos.y()+size*0.5),
                          QPointF(m.pos.x()+size*0.7, m.pos.y()+size*0.5)]
                painter.setBrush(QBrush(QColor(255,165,0)))
                painter.setPen(QPen(Qt.GlobalColor.black,1))
                painter.drawPolygon(QPolygonF(points))

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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Симуляция траекторий, радаров и пусковых установок")
        self.setGeometry(100,100,1300,750)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Верхняя панель
        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0,0,0,0)

        self.canvas = PointCanvas(self)

        self.reset_btn = QPushButton("Сбросить все")
        self.reset_btn.clicked.connect(self.canvas.reset_all)
        top_layout.addWidget(self.reset_btn)

        self.sim_btn = QPushButton("Симулировать")
        self.sim_btn.clicked.connect(self.canvas.simulate)
        top_layout.addWidget(self.sim_btn)

        top_layout.addWidget(QLabel("Время (сек):"))
        top_layout.addWidget(QLabel("Лимит (с):"))
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0, 36000)
        self.duration_spin.setDecimals(1)
        self.duration_spin.setSingleStep(5.0)
        self.duration_spin.setSpecialValueText("Авто")
        self.duration_spin.setValue(0.0)
        self.duration_spin.valueChanged.connect(self.canvas.set_simulation_duration_override)
        top_layout.addWidget(self.duration_spin)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0,1000)
        self.slider.setValue(0)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
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
        speed_layout.addWidget(QLabel("Скорость (пкс/с):"))
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.1,10000)
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
        self.radar_range.setRange(1,1000)
        self.radar_angle = QDoubleSpinBox()
        self.radar_angle.setRange(1,360)
        self.radar_speed = QDoubleSpinBox()
        self.radar_speed.setRange(1,360)
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
        self.launch_missile_speed.setRange(1,1000)
        self.launch_missile_speed.setValue(200)
        self.launch_range = QDoubleSpinBox()
        self.launch_range.setRange(1,1000)
        self.launch_range.setValue(200)
        self.launch_lifetime = QDoubleSpinBox()
        self.launch_lifetime.setRange(0.5,30)
        self.launch_lifetime.setValue(5)
        btn_apply_launch = QPushButton("Применить")
        btn_apply_launch.clicked.connect(self.apply_launch)
        form_launch.addRow("Имя:", self.launch_name)
        form_launch.addRow("Скорость ракеты (пкс/с):", self.launch_missile_speed)
        form_launch.addRow("Дальность пуска (пикс):", self.launch_range)
        form_launch.addRow("Время жизни без цели (с):", self.launch_lifetime)
        form_launch.addRow(btn_apply_launch)
        grp_launch.setLayout(form_launch)
        launch_layout.addWidget(grp_launch)

        tabs.addTab(launch_widget, "Пусковые установки")

        splitter.addWidget(tabs)
        splitter.setSizes([850,400])
        main_layout.addWidget(splitter)

        # Панель инструментов
        toolbar = QToolBar("Файл")
        self.addToolBar(toolbar)
        toolbar.setMovable(False)
        btn_save = QPushButton("Сохранить сценарий")
        btn_save.clicked.connect(self.save_scene)
        toolbar.addWidget(btn_save)
        btn_load = QPushButton("Загрузить сценарий")
        btn_load.clicked.connect(self.load_scene)
        toolbar.addWidget(btn_load)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        # Сигналы
        self.canvas.detection_signal.connect(self.log_detection)
        self.canvas.target_detected.connect(self.on_target_detected)
        self.canvas.trajectory_list_changed.connect(self.refresh_trajectory_list)
        self.canvas.radar_list_changed.connect(self.refresh_radar_list)
        self.canvas.launchpad_list_changed.connect(self.refresh_launch_list)

        # Инициализация
        self.canvas.add_trajectory("Траектория 1")
        self.canvas.set_progress_slider(self.slider)

        # Переключение режимов по вкладкам
        tabs.currentChanged.connect(self.on_tab_changed)

        self.refresh_trajectory_list()
        self.refresh_radar_list()
        self.refresh_launch_list()
        self.on_tab_changed(0)

        self.statusBar.showMessage("Готово. Режим: Траектория. ЛКМ — точка, ПКМ — удалить.")

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
        for pad in self.canvas.launch_pads:
            if pad.can_launch(pos):
                # Проверяем, не запущена ли уже ракета по этой цели
                already = any(m.target_traj == traj for m in pad.missiles)
                if not already:
                    pad.launch_missile(traj, pos, self.canvas.simulation_time)
                    self.statusBar.showMessage(f"Пусковая установка '{pad.name}' запустила ракету по '{traj.name}'", 2000)

    # ========== Лог ==========
    def log_detection(self, msg):
        self.log_text.append(msg)
        self.log_text.ensureCursorVisible()

    # ========== Сохранение/загрузка ==========
    def save_scene(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить сценарий", "scene.json", "JSON (*.json)")
        if path:
            self.canvas.save_scene(path)

    def load_scene(self):
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить сценарий", "", "JSON (*.json)")
        if path:
            self.canvas.load_scene(path)
            self.refresh_trajectory_list()
            self.refresh_radar_list()
            self.refresh_launch_list()
