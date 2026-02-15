import sys
import time
from dataclasses import dataclass, replace
from threading import Lock, Thread

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, pyqtProperty
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from pynput import keyboard, mouse


AVAILABLE_BINDS = [
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "q", "e", "r", "t", "f", "g", "v", "b", "c", "x", "z", "left_shift", "tab",
    "mouse_left", "mouse_right", "mouse_middle", "mouse_x1", "mouse_x2",
]


@dataclass
class MacroConfig:
    enable_double_edit: bool = False
    enable_drag_edit: bool = False
    enable_pickup: bool = False
    macro_bind: str = "f6"
    edit_bind: str = "f"
    select_bind: str = "mouse_left"
    pickup_bind: str = "e"
    double_edit_speed_ms: int = 35
    double_edit_select_delay_ms: int = 13
    pickup_speed_ms: int = 45


class AnimatedToggle(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._offset = 4.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.toggled.connect(self._on_toggled)
        self.setMinimumHeight(38)

    def _on_toggled(self, checked: bool):
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(34.0 if checked else 4.0)
        self._anim.start()
        self.update()

    def get_offset(self):
        return self._offset

    def set_offset(self, value: float):
        self._offset = value
        self.update()

    offset = pyqtProperty(float, get_offset, set_offset)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = QRectF(0, 0, 68, 28)
        track.moveCenter(self.rect().center())

        if self.isChecked():
            track_color = QColor("#94d8ff")
            knob_color = QColor("#ffe0f0")
        else:
            track_color = QColor("#eecde0")
            knob_color = QColor("#ffffff")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 14, 14)

        knob = QRectF(track.left() + self._offset, track.top() + 3, 22, 22)
        painter.setBrush(knob_color)
        painter.drawEllipse(knob)

        painter.setPen(QPen(QColor("#5a6f8f")))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(80, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, self.text())


class MacroEngine:
    def __init__(self):
        self._config = MacroConfig()
        self._lock = Lock()
        self._running = True
        self._held_keys: set[str] = set()
        self._held_mouse: set[str] = set()
        self._kb = keyboard.Controller()
        self._mouse = mouse.Controller()
        self._drag_select_held = False
        self._double_last = 0.0
        self._pickup_last = 0.0

        self._worker = Thread(target=self._run, daemon=True)
        self._worker.start()

        self._keyboard_listener = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release)
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._keyboard_listener.start()
        self._mouse_listener.start()

    def stop(self):
        self._running = False

    def update_config(self, cfg: MacroConfig):
        with self._lock:
            self._config = replace(cfg)

    def snapshot(self) -> MacroConfig:
        with self._lock:
            return replace(self._config)

    def _on_key_press(self, key):
        name = self._normalize_keyboard_key(key)
        if name:
            self._held_keys.add(name)

    def _on_key_release(self, key):
        name = self._normalize_keyboard_key(key)
        if name:
            self._held_keys.discard(name)

    def _on_click(self, x, y, button, pressed):
        m = self._normalize_mouse_button(button)
        if not m:
            return
        if pressed:
            self._held_mouse.add(m)
        else:
            self._held_mouse.discard(m)

    def _normalize_keyboard_key(self, key):
        if isinstance(key, keyboard.KeyCode) and key.char:
            return key.char.lower()
        key_map = {
            keyboard.Key.f1: "f1", keyboard.Key.f2: "f2", keyboard.Key.f3: "f3", keyboard.Key.f4: "f4",
            keyboard.Key.f5: "f5", keyboard.Key.f6: "f6", keyboard.Key.f7: "f7", keyboard.Key.f8: "f8",
            keyboard.Key.f9: "f9", keyboard.Key.f10: "f10", keyboard.Key.f11: "f11", keyboard.Key.f12: "f12",
            keyboard.Key.shift_l: "left_shift", keyboard.Key.tab: "tab",
        }
        return key_map.get(key)

    def _normalize_mouse_button(self, button):
        mapping = {
            mouse.Button.left: "mouse_left",
            mouse.Button.right: "mouse_right",
            mouse.Button.middle: "mouse_middle",
            mouse.Button.x1: "mouse_x1",
            mouse.Button.x2: "mouse_x2",
        }
        return mapping.get(button)

    def _is_bind_down(self, bind: str) -> bool:
        if bind.startswith("mouse_"):
            return bind in self._held_mouse
        return bind in self._held_keys

    def _press_bind(self, bind: str):
        if bind.startswith("mouse_"):
            btn = {
                "mouse_left": mouse.Button.left,
                "mouse_right": mouse.Button.right,
                "mouse_middle": mouse.Button.middle,
                "mouse_x1": mouse.Button.x1,
                "mouse_x2": mouse.Button.x2,
            }.get(bind)
            if btn:
                self._mouse.click(btn)
            return

        k = self._resolve_keyboard_bind(bind)
        if k:
            self._kb.press(k)
            self._kb.release(k)

    def _resolve_keyboard_bind(self, bind: str):
        special = {
            "left_shift": keyboard.Key.shift_l,
            "tab": keyboard.Key.tab,
            "f1": keyboard.Key.f1,
            "f2": keyboard.Key.f2,
            "f3": keyboard.Key.f3,
            "f4": keyboard.Key.f4,
            "f5": keyboard.Key.f5,
            "f6": keyboard.Key.f6,
            "f7": keyboard.Key.f7,
            "f8": keyboard.Key.f8,
            "f9": keyboard.Key.f9,
            "f10": keyboard.Key.f10,
            "f11": keyboard.Key.f11,
            "f12": keyboard.Key.f12,
        }
        if bind in special:
            return special[bind]
        if len(bind) == 1:
            return bind
        return None

    def _hold_bind(self, bind: str):
        if bind.startswith("mouse_"):
            btn = {
                "mouse_left": mouse.Button.left,
                "mouse_right": mouse.Button.right,
                "mouse_middle": mouse.Button.middle,
                "mouse_x1": mouse.Button.x1,
                "mouse_x2": mouse.Button.x2,
            }.get(bind)
            if btn:
                self._mouse.press(btn)
            return

        k = self._resolve_keyboard_bind(bind)
        if k:
            self._kb.press(k)

    def _release_bind(self, bind: str):
        if bind.startswith("mouse_"):
            btn = {
                "mouse_left": mouse.Button.left,
                "mouse_right": mouse.Button.right,
                "mouse_middle": mouse.Button.middle,
                "mouse_x1": mouse.Button.x1,
                "mouse_x2": mouse.Button.x2,
            }.get(bind)
            if btn:
                self._mouse.release(btn)
            return

        k = self._resolve_keyboard_bind(bind)
        if k:
            self._kb.release(k)

    def _run(self):
        while self._running:
            cfg = self.snapshot()
            macro_held = self._is_bind_down(cfg.macro_bind)
            now = time.monotonic()

            # Drag macro: while held, click edit once then hold select until release.
            if cfg.enable_drag_edit and macro_held and not self._drag_select_held:
                self._press_bind(cfg.edit_bind)
                time.sleep(0.01)
                self._hold_bind(cfg.select_bind)
                self._drag_select_held = True
            elif self._drag_select_held and (not macro_held or not cfg.enable_drag_edit):
                self._release_bind(cfg.select_bind)
                self._drag_select_held = False

            if macro_held:
                # Double edit: repeatedly press edit bind then select bind.
                if cfg.enable_double_edit and (now - self._double_last) * 1000 >= cfg.double_edit_speed_ms:
                    self._press_bind(cfg.edit_bind)
                    time.sleep(max(cfg.double_edit_select_delay_ms, 0) / 1000.0)
                    self._press_bind(cfg.select_bind)
                    self._double_last = time.monotonic()

                if cfg.enable_pickup and (now - self._pickup_last) * 1000 >= cfg.pickup_speed_ms:
                    self._press_bind(cfg.pickup_bind)
                    self._pickup_last = now

            time.sleep(0.001)


class AnimatedWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MacroRS PyQt6")
        self.resize(860, 560)
        self.engine = MacroEngine()

        self._phase = 0.0
        self._bg_timer = QTimer(self)
        self._bg_timer.timeout.connect(self._tick_bg)
        self._bg_timer.start(16)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)

        title = QLabel("Fortnite Macro Control Center")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        subtitle = QLabel("Light pink + baby blue theme with animated controls")
        subtitle.setStyleSheet("color: #5f6e8c;")
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._build_enablers_tab(), "Enablers")
        self.tabs.addTab(self._build_speeds_tab(), "Speeds")
        self.tabs.addTab(self._build_binds_tab(), "Binds")
        self.tabs.addTab(self._build_status_tab(), "Status")
        card_layout.addWidget(self.tabs)

        root.addWidget(card)

        self._fade_in(central)
        self._apply_styles()
        self._update_status_text()

    def closeEvent(self, event):
        self.engine.stop()
        super().closeEvent(event)

    def _tick_bg(self):
        self._phase += 0.02
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(QPointF(0, 0), QPointF(self.width(), self.height()))
        v = (1 + __import__('math').sin(self._phase)) * 0.5
        grad.setColorAt(0.0, QColor.fromRgbF(0.95, 0.86 + 0.05 * v, 0.92 + 0.04 * v, 1.0))
        grad.setColorAt(1.0, QColor.fromRgbF(0.78 + 0.08 * v, 0.89, 1.0, 1.0))
        painter.fillRect(self.rect(), grad)
        super().paintEvent(event)

    def _fade_in(self, widget: QWidget):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(700)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.start()
        self._fade_anim = anim

    def _apply_styles(self):
        self.setStyleSheet(
            """
            #card {
                background: rgba(255, 255, 255, 0.78);
                border: 2px solid #ffd0e8;
                border-radius: 18px;
            }
            QLabel { color: #3f4d6b; }
            QTabWidget::pane {
                border: 1px solid #b8deff;
                border-radius: 12px;
                background: rgba(255,255,255,0.70);
            }
            QTabBar::tab {
                background: #ffd8eb;
                color: #4f6487;
                border-radius: 10px;
                padding: 8px 16px;
                margin: 4px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #b8e3ff;
            }
            QComboBox, QSlider, QPushButton {
                font-size: 14px;
            }
            QComboBox {
                border: 1px solid #b6dfff;
                border-radius: 8px;
                padding: 6px;
                background: #fff4fb;
            }
            """
        )

    def _build_enablers_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        self.double_toggle = AnimatedToggle("Enable Double Edit")
        self.drag_toggle = AnimatedToggle("Enable Drag Edit")
        self.pickup_toggle = AnimatedToggle("Enable Pickup Spam")

        self.double_toggle.toggled.connect(self._sync_config)
        self.drag_toggle.toggled.connect(self._sync_config)
        self.pickup_toggle.toggled.connect(self._sync_config)

        lay.addWidget(self.double_toggle)
        lay.addWidget(self.drag_toggle)
        lay.addWidget(self.pickup_toggle)
        lay.addStretch()
        return tab

    def _build_speeds_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)

        self.double_speed = self._slider(5, 250, 35, self._sync_config)
        self.double_delay = self._slider(0, 120, 13, self._sync_config)
        self.pickup_speed = self._slider(5, 250, 45, self._sync_config)

        form.addRow("Double Edit Loop Speed (ms)", self.double_speed)
        form.addRow("Edit ➜ Select Delay (ms)", self.double_delay)
        form.addRow("Pickup Spam Speed (ms)", self.pickup_speed)
        return tab

    def _build_binds_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)

        self.macro_bind = self._bind_combo("f6")
        self.edit_bind = self._bind_combo("f")
        self.select_bind = self._bind_combo("mouse_left")
        self.pickup_bind = self._bind_combo("e")

        form.addRow("Macro Hold Bind", self.macro_bind)
        form.addRow("Edit Bind", self.edit_bind)
        form.addRow("Select Bind", self.select_bind)
        form.addRow("Pickup Bind", self.pickup_bind)

        info = QLabel("You can reuse one key for multiple binds.")
        form.addRow(info)
        return tab

    def _build_status_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("font-size: 14px; color: #4e6485;")
        refresh = QPushButton("Refresh Status")
        refresh.clicked.connect(self._update_status_text)
        lay.addWidget(self.status)
        lay.addWidget(refresh)
        lay.addStretch()
        return tab

    def _slider(self, min_v, max_v, default, cb):
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(default)
        label = QLabel(str(default))
        slider.valueChanged.connect(lambda v: label.setText(str(v)))
        slider.valueChanged.connect(cb)
        row.addWidget(slider)
        row.addWidget(label)
        return container

    def _extract_slider_value(self, widget: QWidget):
        slider = widget.findChild(QSlider)
        return slider.value() if slider else 0

    def _bind_combo(self, default):
        combo = QComboBox()
        combo.addItems(AVAILABLE_BINDS)
        combo.setCurrentText(default)
        combo.currentTextChanged.connect(self._sync_config)
        return combo

    def _collect_config(self):
        return MacroConfig(
            enable_double_edit=self.double_toggle.isChecked(),
            enable_drag_edit=self.drag_toggle.isChecked(),
            enable_pickup=self.pickup_toggle.isChecked(),
            macro_bind=self.macro_bind.currentText(),
            edit_bind=self.edit_bind.currentText(),
            select_bind=self.select_bind.currentText(),
            pickup_bind=self.pickup_bind.currentText(),
            double_edit_speed_ms=self._extract_slider_value(self.double_speed),
            double_edit_select_delay_ms=self._extract_slider_value(self.double_delay),
            pickup_speed_ms=self._extract_slider_value(self.pickup_speed),
        )

    def _sync_config(self):
        cfg = self._collect_config()
        self.engine.update_config(cfg)
        self._update_status_text()

    def _update_status_text(self):
        cfg = self._collect_config()
        self.status.setText(
            f"Macro Hold: {cfg.macro_bind}\n"
            f"Double Edit: {'ON' if cfg.enable_double_edit else 'OFF'} | {cfg.double_edit_speed_ms}ms loop, "
            f"{cfg.double_edit_select_delay_ms}ms edit->select\n"
            f"Drag Edit: {'ON' if cfg.enable_drag_edit else 'OFF'} | hold macro bind to keep select held\n"
            f"Pickup Spam: {'ON' if cfg.enable_pickup else 'OFF'} | {cfg.pickup_speed_ms}ms\n"
            f"Edit Bind: {cfg.edit_bind} | Select Bind: {cfg.select_bind} | Pickup Bind: {cfg.pickup_bind}"
        )


def main():
    app = QApplication(sys.argv)
    win = AnimatedWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
