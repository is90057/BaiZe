from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QLinearGradient
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QGroupBox, QMessageBox,
)

from ..i18n import tr


PRESET_EFFECTS = [
    ("none", "Original", "無特效", "#444450"),
    ("explosion", "Explosion Burst", "💥 爆炸衝擊波", "#d9381e"),
    ("flash", "Camera Flash", "⚡ 強光閃閃光", "#e6b800"),
    ("particles", "Gold Sparkles", "✨ 金燦星光粒子", "#d4af37"),
    ("cyber_particles", "Cyber Particles", "🌌 賽博霓光粒子", "#8a2be2"),
    ("warm_film", "Warm Film", "暖陽電影", "#b87033"),
    ("cool_cyber", "Cool Cyberpunk", "冷藍賽博", "#2b6b8b"),
    ("teal_orange", "Teal & Orange", "青橙大片", "#2b8b7a"),
    ("vivid", "Vivid Boost", "高對比鮮豔", "#9b2b5a"),
    ("grayscale", "Grayscale", "經典黑白", "#555555"),
    ("sepia", "Sepia Vintage", "復古懷舊", "#8b5a2b"),
    ("invert", "Color Invert", "負片反轉", "#2b5a8b"),
    ("blur", "Soft Blur", "柔焦模糊", "#3a7b5a"),
    ("center_focus", "Center Focus", "中心聚焦", "#3a5a7b"),
    ("tilt_shift", "Tilt Shift Focus", "移軸聚焦", "#5a3a7b"),
    ("mirror_h", "Horizontal Mirror", "水平鏡像", "#6b3a7b"),
    ("vignette", "Cinema Vignette", "電影暗角", "#222233"),
]


class EffectsPanel(QWidget):
    effect_applied = pyqtSignal(str, str)  # (clip_id, fx_id)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        head = QHBoxLayout()
        self._title = QLabel(tr("Preset Effects"))
        self._title.setStyleSheet("font-weight: bold; color: #d0d0d6; font-size: 13px;")
        head.addWidget(self._title)
        head.addStretch(1)
        lay.addLayout(head)

        self._hint = QLabel(tr("Select a video clip on timeline and click an effect to apply."))
        self._hint.setStyleSheet("color: #888894; font-size: 11px;")
        self._hint.setWordWrap(True)
        lay.addWidget(self._hint)

        self.list = QListWidget(self)
        self.list.setIconSize(QSize(120, 60))
        self.list.setSpacing(4)
        self.list.itemClicked.connect(self._on_item_clicked)
        self.list.itemDoubleClicked.connect(self._on_item_clicked)
        lay.addWidget(self.list, 1)

        self._populate_list()

    def _populate_list(self):
        self.list.clear()
        for fx_id, name_en, name_zh, bg_color in PRESET_EFFECTS:
            item = QListWidgetItem()
            display_name = f"{tr(name_en)}"
            item.setText(display_name)
            item.setData(Qt.ItemDataRole.UserRole, fx_id)
            item.setToolTip(f"{display_name} ({fx_id})")
            self.list.addItem(item)

    def retranslate(self):
        self._title.setText(tr("Preset Effects"))
        self._hint.setText(tr("Select a video clip on timeline and click an effect to apply."))
        self._populate_list()

    def _on_item_clicked(self, item: QListWidgetItem):
        fx_id = item.data(Qt.ItemDataRole.UserRole)
        if not fx_id:
            return
        selected = self.controller._selected
        if not selected:
            QMessageBox.information(
                self, tr("Preset Effects"),
                tr("Please select a video clip on the timeline first."))
            return

        for clip_id in selected:
            c = self.controller.project.clip_by_id(clip_id)
            if c:
                self.controller.set_clip_video_fx(c.id, fx_id)
