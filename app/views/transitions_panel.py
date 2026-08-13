from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QDoubleSpinBox, QComboBox, QMessageBox, QGroupBox,
)

from ..i18n import tr

TRANSITION_PRESETS = [
    {"type": "fade", "title": "Fade / Crossfade", "desc": "Smooth opacity dissolve transition"},
    {"type": "black", "title": "Fade to Black", "desc": "Fade transition to/from solid black"},
    {"type": "white", "title": "Fade to White", "desc": "Fade transition to/from solid white"},
    {"type": "wipe_right", "title": "Wipe Right", "desc": "Horizontal wipe from left to right"},
    {"type": "wipe_left", "title": "Wipe Left", "desc": "Horizontal wipe from right to left"},
    {"type": "wipe_up", "title": "Wipe Up", "desc": "Vertical wipe from bottom to top"},
    {"type": "wipe_down", "title": "Wipe Down", "desc": "Vertical wipe from top to bottom"},
    {"type": "slide_right", "title": "Slide Right", "desc": "Push slide transition from left"},
    {"type": "slide_left", "title": "Slide Left", "desc": "Push slide transition from right"},
    {"type": "slide_up", "title": "Slide Up", "desc": "Push slide transition from bottom"},
    {"type": "slide_down", "title": "Slide Down", "desc": "Push slide transition from top"},
    {"type": "zoom_in", "title": "Zoom In", "desc": "Zoom scaling focal transition"},
    {"type": "circle_crop", "title": "Circle Crop", "desc": "Circular expanding mask wipe"},
]


def _create_preset_icon(preset_type: str) -> QIcon:
    pm = QPixmap(140, 80)
    pm.fill(QColor(28, 28, 34))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # background gradient or pattern preview
    if preset_type == "black":
        p.fillRect(0, 0, 70, 80, QColor(60, 100, 160))
        p.fillRect(70, 0, 70, 80, QColor(10, 10, 12))
    elif preset_type == "white":
        p.fillRect(0, 0, 70, 80, QColor(60, 100, 160))
        p.fillRect(70, 0, 70, 80, QColor(240, 240, 245))
    elif "wipe" in preset_type:
        p.fillRect(0, 0, 140, 80, QColor(45, 80, 140))
        p.fillRect(70, 0, 70, 80, QColor(180, 100, 50))
        p.setPen(QPen(QColor(255, 255, 255, 200), 2))
        if "right" in preset_type:
            p.drawLine(70, 10, 70, 70)
            p.drawLine(65, 40, 75, 40)
        elif "left" in preset_type:
            p.drawLine(70, 10, 70, 70)
            p.drawLine(75, 40, 65, 40)
        elif "up" in preset_type:
            p.drawLine(10, 40, 130, 40)
            p.drawLine(70, 45, 70, 35)
        else:
            p.drawLine(10, 40, 130, 40)
            p.drawLine(70, 35, 70, 45)
    elif "slide" in preset_type:
        p.fillRect(0, 0, 140, 80, QColor(35, 65, 120))
        p.fillRect(50, 0, 90, 80, QColor(200, 120, 60))
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawRect(50, 0, 90, 80)
    elif preset_type == "zoom_in":
        p.fillRect(0, 0, 140, 80, QColor(40, 70, 130))
        p.setPen(QPen(QColor(255, 180, 60), 2, Qt.PenStyle.DashLine))
        p.drawRect(30, 16, 80, 48)
    elif preset_type == "circle_crop":
        p.fillRect(0, 0, 140, 80, QColor(40, 70, 130))
        p.setBrush(QColor(200, 120, 60))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(35, 5, 70, 70)
    else: # fade / crossfade
        for i in range(140):
            alpha = int(255 * (i / 140.0))
            c = QColor(50, 100, 180, 255 - alpha)
            p.fillRect(i, 0, 1, 80, c)

    p.end()
    return QIcon(pm)


class TransitionsPanel(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        head = QHBoxLayout()
        self._title = QLabel(tr("Transitions Library"))
        self._title.setStyleSheet("font-weight: bold; color: #d0d0d6;")
        head.addWidget(self._title)
        head.addStretch(1)
        lay.addLayout(head)

        self.list = QListWidget(self)
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(130, 74))
        self.list.setGridSize(QSize(160, 115))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.itemDoubleClicked.connect(self._on_item_double_clicked)
        lay.addWidget(self.list)

        # target settings group
        opts_box = QGroupBox(tr("Apply Settings"))
        opts_lay = QVBoxLayout(opts_box)
        opts_lay.setContentsMargins(6, 6, 6, 6)
        opts_lay.setSpacing(4)

        row1 = QHBoxLayout()
        self._lbl_target = QLabel(tr("Apply to:"))
        self.target_combo = QComboBox()
        self.target_combo.addItem(tr("Both In & Out"), "both")
        self.target_combo.addItem(tr("Fade In (Entry)"), "in")
        self.target_combo.addItem(tr("Fade Out (Exit)"), "out")
        row1.addWidget(self._lbl_target)
        row1.addWidget(self.target_combo, 1)
        opts_lay.addLayout(row1)

        row2 = QHBoxLayout()
        self._lbl_dur = QLabel(tr("Duration (s):"))
        self.dur_spin = QDoubleSpinBox()
        self.dur_spin.setRange(0.1, 5.0)
        self.dur_spin.setSingleStep(0.1)
        self.dur_spin.setValue(1.0)
        row2.addWidget(self._lbl_dur)
        row2.addWidget(self.dur_spin, 1)
        opts_lay.addLayout(row2)

        self.apply_btn = QPushButton(tr("Apply to Selected Clip"))
        self.apply_btn.clicked.connect(self.apply_selected_transition)
        opts_lay.addWidget(self.apply_btn)

        lay.addWidget(opts_box)
        self._populate_list()

    def _populate_list(self):
        self.list.clear()
        for item_data in TRANSITION_PRESETS:
            item = QListWidgetItem()
            item.setText(tr(item_data["title"]))
            item.setData(Qt.ItemDataRole.UserRole, item_data["type"])
            item.setToolTip(f"{tr(item_data['title'])}\n{item_data['desc']}")
            item.setIcon(_create_preset_icon(item_data["type"]))
            self.list.addItem(item)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def retranslate(self):
        self._title.setText(tr("Transitions Library"))
        self._lbl_target.setText(tr("Apply to:"))
        self.target_combo.setItemText(0, tr("Both In & Out"))
        self.target_combo.setItemText(1, tr("Fade In (Entry)"))
        self.target_combo.setItemText(2, tr("Fade Out (Exit)"))
        self._lbl_dur.setText(tr("Duration (s):"))
        self.apply_btn.setText(tr("Apply to Selected Clip"))
        self._populate_list()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self.apply_selected_transition()

    def apply_selected_transition(self):
        item = self.list.currentItem()
        if item is None:
            return
        trans_type = item.data(Qt.ItemDataRole.UserRole)
        dur = float(self.dur_spin.value())
        target = self.target_combo.currentData()

        selected_clips = self.controller.selected_clips()
        if not selected_clips:
            QMessageBox.information(
                self, tr("Transitions"),
                tr("Select a clip on the timeline first."))
            return

        for clip in selected_clips:
            in_dur = dur if target in ("in", "both") else clip.fade_in_duration
            in_type = trans_type if target in ("in", "both") else clip.fade_in_type
            out_dur = dur if target in ("out", "both") else clip.fade_out_duration
            out_type = trans_type if target in ("out", "both") else clip.fade_out_type

            self.controller.set_clip_transition(
                clip.id,
                fade_in_dur=in_dur, fade_in_type=in_type,
                fade_out_dur=out_dur, fade_out_type=out_type,
            )
