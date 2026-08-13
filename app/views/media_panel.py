from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QSize, pyqtSignal, QMimeData
from PyQt6.QtGui import QIcon, QPixmap, QDrag
from PyQt6.QtWidgets import (
    QWidget, QLayout, QVBoxLayout, QHBoxLayout, QPushButton, QToolButton,
    QListWidget, QListWidgetItem, QLabel, QFileDialog, QMenu, QApplication,
)

from ..core import ffmpeg as fx
from ..models.media import MediaClip
from ..i18n import tr
from .timeline_widget import MEDIA_MIME


class MediaListWidget(QListWidget):
    def startDrag(self, supportedActions):
        items = self.selectedItems()
        if not items:
            return
        mids = ",".join(i.data(Qt.ItemDataRole.UserRole) for i in items if i.data(Qt.ItemDataRole.UserRole))
        if not mids:
            return
        mime = QMimeData()
        mime.setData(MEDIA_MIME, mids.encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        if items[0].icon():
            pixmap = items[0].icon().pixmap(QSize(120, 68))
            if not pixmap.isNull():
                drag.setPixmap(pixmap)
        drag.exec(Qt.DropAction.CopyAction)


class MediaPanel(QWidget):
    add_to_timeline = pyqtSignal(object)
    media_removed = pyqtSignal(object)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._thumbnails: dict[str, QIcon] = {}
        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        head = QHBoxLayout()
        self._title = QLabel(tr("Media Library"))
        self._title.setStyleSheet("font-weight: bold; color: #d0d0d6;")
        head.addWidget(self._title)
        head.addStretch(1)
        self._import_btn = QToolButton()
        self._import_btn.setText(tr("Import…"))
        self._import_btn.setToolTip(tr("Import media files"))
        self._import_btn.clicked.connect(self._on_import_clicked)
        head.addWidget(self._import_btn)
        lay.addLayout(head)

        self.list = MediaListWidget(self)
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(160, 90))
        self.list.setGridSize(QSize(190, 138))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list.setDragEnabled(True)
        self.list.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        self.list.itemDoubleClicked.connect(self._activate)
        lay.addWidget(self.list)

        self._hint = QLabel(tr("Drag media onto a timeline track to add it."))
        self._hint.setStyleSheet("color: #77777e; font-size: 11px;")
        lay.addWidget(self._hint)

    def retranslate(self):
        self._title.setText(tr("Media Library"))
        self._hint.setText(tr("Drag media onto a timeline track to add it."))
        self._import_btn.setText(tr("Import…"))
        self._import_btn.setToolTip(tr("Import media files"))

    def _on_import_clicked(self):
        self.import_files()

    # ---------- import ----------
    def import_files(self, paths: list[str] | None = None):
        if not isinstance(paths, list):
            paths = None
        if paths is None:
            filter_str = (
                f"{tr('All Supported Media')} (*.mp4 *.mov *.m4v *.mkv *.avi *.wmv *.webm *.mpg "
                f"*.mpeg *.ts *.mts *.m2ts *.3gp *.bmp *.jpg *.jpeg *.png *.webp *.gif *.mp3 *.wav *.aac *.m4a);;"
                f"{tr('Image Files')} (*.bmp *.jpg *.jpeg *.png *.webp *.gif);;"
                f"{tr('Video Files')} (*.mp4 *.mov *.m4v *.mkv *.avi *.wmv *.webm);;"
                f"{tr('Audio Files')} (*.mp3 *.wav *.aac *.m4a);;"
                f"{tr('All files')} (*)"
            )
            paths, _ = QFileDialog.getOpenFileNames(
                self, tr("Import Media"), "", filter_str)
        if not paths:
            return
        clips: list[MediaClip] = []
        for p in paths:
            try:
                info = fx.probe(p)
            except Exception:
                continue
            if not (info["has_video"] or info["has_audio"]):
                continue
            m = MediaClip(
                path=p, name=Path(p).name, duration=info["duration"],
                width=info["width"], height=info["height"], fps=info["fps"],
                has_video=info["has_video"], has_audio=info["has_audio"],
                is_image=info.get("is_image", False), has_alpha=info.get("has_alpha", False),
            )
            clips.append(m)
        self.controller.add_media(clips)

    def media_item(self, mid: str) -> MediaClip | None:
        return self.controller.project.media_by_id(mid)

    # ---------- list management ----------
    def add_media_item(self, media: MediaClip):
        item = QListWidgetItem()
        item.setText(media.name)
        item.setData(Qt.ItemDataRole.UserRole, media.id)
        item.setToolTip(
            f"{media.filepath().name}\n"
            f"{media.resolution}  •  {media.fps:.0f} fps  •  "
            f"{_fmt_dur(media.duration)}")
        icon = self._thumbnail(media)
        if icon is not None:
            item.setIcon(icon)
        self.list.addItem(item)

    def refresh_all(self):
        self.list.clear()
        self._thumbnails.clear()
        for m in self.controller.project.media:
            self.add_media_item(m)

    def _thumbnail(self, media: MediaClip) -> QIcon | None:
        if media.id in self._thumbnails:
            return self._thumbnails[media.id]
        icon = None
        if media.has_video:
            path = fx.thumbnail(media.path, media.duration)
            if path:
                icon = QIcon(QPixmap(path))
        else:
            icon = _audio_icon()
        self._thumbnails[media.id] = icon
        return icon

    def _context_menu(self, pos):
        item = self.list.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #26262c; color: #e2e2e2; border: 1px solid #3a3a42;}"
            "QMenu::item:selected { background: #3a6ea5; }")
        add_act = menu.addAction(tr("Add to Timeline (V1 at playhead)"))
        del_act = menu.addAction(tr("Remove from Library"))
        action = menu.exec(self.list.mapToGlobal(pos))
        if action == add_act:
            mid = item.data(Qt.ItemDataRole.UserRole)
            media = self.media_item(mid)
            if media:
                self.add_to_timeline.emit(media)
        elif action == del_act:
            mid = item.data(Qt.ItemDataRole.UserRole)
            media = self.media_item(mid)
            if media:
                self.remove_media(media)

    def remove_media(self, media: MediaClip):
        used = any(c.media_id == media.id for tr in self.controller.project.all_tracks()
                   for c in tr.clips)
        if used:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, tr("In Use"),
                tr("media is used on the timeline and cannot be removed.").format(
                    name=media.name))
            return
        self.controller.project.media = [
            m for m in self.controller.project.media if m.id != media.id]
        self.controller.project_changed.emit()
        self.media_removed.emit(media)

    def _activate(self, item: QListWidgetItem):
        mid = item.data(Qt.ItemDataRole.UserRole)
        media = self.media_item(mid)
        if media:
            self.add_to_timeline.emit(media)

    # ---------- drop onto panel ----------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if paths:
            self.import_files(paths)
            e.acceptProposedAction()


def _fmt_dur(d: float) -> str:
    h, rem = divmod(int(d), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _audio_icon() -> QIcon:
    pm = QPixmap(160, 90)
    pm.fill(Qt.GlobalColor.transparent)
    return QIcon(pm)