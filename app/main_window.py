from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QKeySequence, QShortcut, QCloseEvent, QActionGroup
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter,
    QScrollArea, QFileDialog, QMessageBox, QDockWidget, QLineEdit,
    QSpinBox, QPlainTextEdit, QComboBox, QTextEdit, QTabWidget,
)

from .controllers.project_controller import ProjectController
from .models.project import Project, save_project, load_project
from .views.media_panel import MediaPanel
from .views.templates_panel import TemplatesPanel
from .views.transitions_panel import TransitionsPanel
from .views.subtitle_panel import SubtitlePanel
from .views.effects_panel import EffectsPanel
from .views.timeline_widget import TimelineWidget
from .views.preview_widget import PreviewWidget
from .views.transport_bar import TransportBar
from .views.inspector_panel import InspectorPanel
from .views.export_dialog import ExportDialog
from .theme import DARK_QSS
from .i18n import tr, subscribe, set_language, current_language, LANGUAGES


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BaiZe — Untitled")
        self.resize(1440, 900)
        self.controller = ProjectController()
        self._path = ""
        self._lang = QSettings("BaiZe", "BaiZe").value(
            "language", "en", str)
        set_language(self._lang)
        subscribe(self._apply_language)
        self._build_ui()
        self._wire()
        self._build_menu()
        self._build_shortcuts()
        self._update_title()
        self.update_marks()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.setStyleSheet(DARK_QSS)

        # left dock: Media Library, Templates, Transitions & Subtitles tabs
        self.media_panel = MediaPanel(self.controller)
        self.templates_panel = TemplatesPanel(self.controller)
        self.transitions_panel = TransitionsPanel(self.controller)
        self.effects_panel = EffectsPanel(self.controller)
        self.subtitle_panel = SubtitlePanel(self.controller, self)

        self.left_tabs = QTabWidget()
        self.left_tabs.addTab(self.media_panel, tr("Media Library"))
        self.left_tabs.addTab(self.templates_panel, tr("Templates"))
        self.left_tabs.addTab(self.transitions_panel, tr("Transitions"))
        self.left_tabs.addTab(self.effects_panel, tr("Effects"))
        self.left_tabs.addTab(self.subtitle_panel, tr("Subtitles"))

        self.media_dock = QDockWidget(self)
        self.media_dock.setObjectName("mediaDock")
        self.media_dock.setWidget(self.left_tabs)
        self.media_dock.setMinimumWidth(270)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.media_dock)

        # inspector dock (right)
        self.inspector = InspectorPanel(self.controller)
        self.inspector_dock = QDockWidget(self)
        self.inspector_dock.setObjectName("inspectorDock")
        self.inspector_dock.setWidget(self.inspector)
        self.inspector_dock.setMinimumWidth(250)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)

        # center preview
        self.preview = PreviewWidget(self.controller)

        # timeline area
        self.timeline = TimelineWidget(self.controller)
        self.timeline.setObjectName("timeline")
        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setObjectName("timelineScroll")
        self.timeline_scroll.setWidget(self.timeline)
        self.timeline_scroll.setWidgetResizable(False)
        self.timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.transport = TransportBar(self.controller)

        bottom = QWidget()
        bottom_lay = QVBoxLayout(bottom)
        bottom_lay.setContentsMargins(0, 0, 0, 0)
        bottom_lay.setSpacing(0)
        bottom_lay.addWidget(self.transport)
        bottom_lay.addWidget(self.timeline_scroll, 1)
        bottom_lay.addWidget(self._timeline_hint(), 0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.preview)
        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([420, 420])
        self.setCentralWidget(splitter)

        self.status = self.statusBar()
        self.status.showMessage(tr("Ready"))

    def _timeline_hint(self) -> QLabel:
        self._hint_label = QLabel(tr("Timeline hint"))
        self._hint_label.setObjectName("dimText")
        self._hint_label.setContentsMargins(6, 2, 6, 2)
        return self._hint_label

    # ---------------- wiring ----------------
    def _wire(self):
        c = self.controller
        c.project_changed.connect(self._on_project_changed)
        c.media_added.connect(self.media_panel.add_media_item)
        c.timeline_changed.connect(self._on_timeline_changed)

        # media -> timeline
        self.media_panel.add_to_timeline.connect(self.add_media_to_timeline)

        # subtitle panel -> inspector & preview
        self.subtitle_panel.subtitle_selected.connect(self.inspector.select_subtitle)
        self.subtitle_panel.seek_requested.connect(self.preview.set_time)

        # preview <-> timeline sync
        self.preview.time_changed.connect(self._sync_from_preview)
        self.timeline.playhead_changed.connect(self._sync_from_timeline)

        # transport
        self.transport.play_toggled.connect(self.toggle_play)
        self.transport.stop_requested.connect(self.preview.stop)
        self.transport.step_requested.connect(self.timeline.nudge_playhead)
        self.transport.goto_requested.connect(self.preview.set_time)
        self.transport.in_pressed.connect(self.set_in_point)
        self.transport.out_pressed.connect(self.set_out_point)
        self.transport.clear_marks_pressed.connect(self.clear_marks)

        # preview play state -> transport icon
        self.preview.play_state_changed.connect(self.transport.set_playing)

        self.media_panel.media_removed.connect(
            lambda m: self.status.showMessage(tr("Removed {name}").format(name=m.name)))

    def _sync_from_preview(self, t: float):
        self.timeline.set_playhead(t, notify=False)
        self.transport.set_time(t)

    def _sync_from_timeline(self, t: float):
        self.preview.set_time(t, notify=False)
        self.transport.set_time(t)

    def _on_project_changed(self):
        self.media_panel.refresh_all()
        self.inspector.on_selection_changed([])
        self._update_title()
        self.status.showMessage(tr("Project changed"))

    def _on_timeline_changed(self):
        self.transport.set_time(self.preview.current_time())
        self.update_marks()

    # ---------------- editing actions ----------------
    def add_media_to_timeline(self, media):
        position = self.timeline.playhead
        if media.has_video:
            track = self.controller.project.video_tracks[-1].index
            self.controller.add_clip(media, "video", track, position)
            if media.has_audio:
                atrack = self.controller.project.audio_tracks[-1].index
                self.controller.add_clip(media, "audio", atrack, position)
        elif media.has_audio:
            track = self.controller.project.audio_tracks[-1].index
            self.controller.add_clip(media, "audio", track, position)
        else:
            return
        self.status.showMessage(tr("Added {name} at {pos}s").format(name=media.name, pos=position))

    def toggle_play(self):
        if self.preview.is_playing():
            self.preview.pause()
        else:
            if self.preview.current_time() >= self.controller.project.duration() - 1e-3:
                self.preview.set_time(0.0)
            self.preview.play()

    def split_clip(self):
        self.timeline.split_at_playhead()

    def delete_selected(self):
        self.timeline.delete_selected()

    def set_in_point(self):
        t = self.timeline.playhead
        self.timeline.in_point = t
        if self.timeline.out_point >= 0 and self.timeline.out_point <= t:
            self.timeline.out_point = -1
        self.update_marks()
        self.timeline.update()

    def set_out_point(self):
        t = self.timeline.playhead
        self.timeline.out_point = t
        if self.timeline.in_point >= 0 and self.timeline.in_point >= t:
            self.timeline.in_point = -1
        self.update_marks()
        self.timeline.update()

    def clear_marks(self):
        self.timeline.in_point = -1
        self.timeline.out_point = -1
        self.update_marks()
        self.timeline.update()

    def update_marks(self):
        t = self.timeline
        self.transport.set_in_out(t.in_point if t.in_point >= 0 else None,
                                  t.out_point if t.out_point >= 0 else None)

    def add_video_track(self):
        self.controller.project.add_video_track()
        self.controller.project_changed.emit()
        self.status.showMessage(tr("Added video track"))

    def add_audio_track(self):
        self.controller.project.add_audio_track()
        self.controller.project_changed.emit()
        self.status.showMessage(tr("Added audio track"))

    # ---------------- file ops ----------------
    def new_project(self):
        self.controller.new_project()
        self._path = ""
        self._update_title()

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Open Project"), "", f"BaiZe Project (*.bzproj *.vproj);;{tr('All files')}")
        if not path:
            return
        try:
            project = load_project(path)
        except Exception as exc:
            QMessageBox.critical(self, tr("Open Project"),
                                 tr("Could not open project:\n{err}").format(err=exc))
            return
        self.controller.load(project)
        self._path = path
        self._update_title()

    def save_project(self):
        if not self._path:
            self.save_project_as()
            return
        try:
            save_project(self.controller.project, self._path)
        except Exception as exc:
            QMessageBox.critical(self, tr("Save"), str(exc))
            return
        self.status.showMessage(tr("Saved {path}").format(path=self._path))

    def save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Save Project"), f"{self.controller.project.name or 'Untitled'}.bzproj",
            f"BaiZe Project (*.bzproj)")
        if not path:
            return
        if not path.endswith(".bzproj") and not path.endswith(".vproj"):
            path += ".bzproj"
        try:
            save_project(self.controller.project, path)
        except Exception as exc:
            QMessageBox.critical(self, tr("Save"), str(exc))
            return
        self._path = path
        self._update_title()
        self.status.showMessage(tr("Saved {path}").format(path=path))

    def import_media(self):
        self.media_panel.import_files()

    def export(self):
        dlg = ExportDialog(self.controller, self)
        dlg.exec()

    def _update_title(self):
        try:
            if self.controller.undo_stack is None:
                return
            clean = self.controller.undo_stack.isClean()
        except RuntimeError:
            return
        name = self.controller.project.name or "Untitled"
        dirty_marker = "" if clean else "*"
        self.setWindowTitle(f"BaiZe — {name}{dirty_marker}")

    # ---------------- menu ----------------
    def _build_menu(self):
        mb = self.menuBar()
        c = self.controller

        self.m_file = mb.addMenu(tr("&File"))
        self.m_file.addAction(tr("New…"), QKeySequence("Ctrl+N"), self.new_project)
        self.m_file.addAction(tr("Open…"), QKeySequence("Ctrl+O"), self.open_project)
        self.m_file.addSeparator()
        self.m_file.addAction(tr("Save"), QKeySequence("Ctrl+S"), self.save_project)
        self.m_file.addAction(tr("Save As…"), QKeySequence("Ctrl+Shift+S"),
                              self.save_project_as)
        self.m_file.addSeparator()
        self.m_file.addAction(tr("Import Media…"), QKeySequence("Ctrl+I"),
                              self.import_media)
        self.m_file.addAction(tr("Export…"), QKeySequence("Ctrl+E"), self.export)
        self.m_file.addSeparator()
        self.m_file.addAction(tr("Quit"), QKeySequence("Ctrl+Q"), self.close)

        self.m_edit = mb.addMenu(tr("&Edit"))
        self.undo_action = c.undo_stack.createUndoAction(self, tr("&Undo"))
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.redo_action = c.undo_stack.createRedoAction(self, tr("&Redo"))
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        if not getattr(self, "_undo_index_connected", False):
            c.undo_stack.indexChanged.connect(self._update_title)
            self._undo_index_connected = True
        self.m_edit.addAction(self.undo_action)
        self.m_edit.addAction(self.redo_action)
        self.m_edit.addSeparator()
        self.m_edit.addAction(tr("Split Selected at Playhead"), self.split_clip)
        self.m_edit.addAction(tr("Delete Selected"), self.delete_selected)
        self.m_edit.addAction(tr("Set In Point"), QKeySequence("I"), self.set_in_point)
        self.m_edit.addAction(tr("Set Out Point"), QKeySequence("O"), self.set_out_point)

        self.m_track = mb.addMenu(tr("&Track"))
        self.m_track.addAction(tr("Add Video Track"), self.add_video_track)
        self.m_track.addAction(tr("Add Audio Track"), self.add_audio_track)
        self.m_track.addAction(tr("Fit Timeline"), QKeySequence("R"),
                               self.timeline.fit_timeline)

        self.m_play = mb.addMenu(tr("&Playback"))
        self.m_play.addAction(tr("Play / Pause"), QKeySequence("Space"), self.toggle_play)
        self.m_play.addAction(tr("Stop"), self.preview.stop)
        self.m_play.addAction(tr("Previous Frame"), QKeySequence(Qt.Key.Key_Left),
                              lambda: self.timeline.nudge_playhead(-1))
        self.m_play.addAction(tr("Next Frame"), QKeySequence(Qt.Key.Key_Right),
                              lambda: self.timeline.nudge_playhead(1))
        self.m_play.addAction(tr("Go to Start"), QKeySequence(Qt.Key.Key_Home),
                              lambda: self.preview.set_time(0.0))
        self.m_play.addAction(tr("Go to End"), QKeySequence(Qt.Key.Key_End),
                              lambda: self.preview.set_time(self.controller.project.duration()))

        self.m_lang = mb.addMenu(tr("Language"))
        self._lang_group = QActionGroup(self)
        self._lang_group.setExclusive(True)
        for code in LANGUAGES:
            act = QAction(LANGUAGES[code], self, checkable=True)
            act.triggered.connect(lambda _=False, c=code: self._set_language(c))
            self._lang_group.addAction(act)
            self.m_lang.addAction(act)
            if code == current_language():
                act.setChecked(True)

        self.m_help = mb.addMenu(tr("&Help"))
        self.m_help.addAction(tr("About BaiZe"), self._about)

    def _set_language(self, code: str):
        if code == current_language():
            return
        set_language(code)
        QSettings("BaiZe", "BaiZe").setValue("language", code)
        for act in self._lang_group.actions():
            if act.text() == LANGUAGES[code]:
                act.setChecked(True)

    def _build_shortcuts(self):
        self._shortcut("Delete", self.delete_selected)
        self._shortcut("Ctrl+B", self.split_clip)
        self._shortcut("Left", lambda: self.timeline.nudge_playhead(-1))
        self._shortcut("Right", lambda: self.timeline.nudge_playhead(1))

    def _shortcut(self, key, fn):
        sc = QShortcut(QKeySequence(key), self)
        sc.activated.connect(fn)

    def _about(self):
        QMessageBox.about(
            self, tr("About BaiZe"),
            f"BaiZe\n\n{tr('About text')}")

    def _apply_language(self):
        # retranslate dock titles & labels
        self.media_dock.setWindowTitle(tr("Media Library"))
        self.inspector_dock.setWindowTitle(tr("Inspector"))
        self.left_tabs.setTabText(0, tr("Media Library"))
        self.left_tabs.setTabText(1, tr("Templates"))
        self.left_tabs.setTabText(2, tr("Transitions"))
        self.left_tabs.setTabText(3, tr("Effects"))
        self.left_tabs.setTabText(4, tr("Subtitles"))
        self._hint_label.setText(tr("Timeline hint"))
        self.status.showMessage(tr("Ready"))
        # child panels
        self.media_panel.retranslate()
        self.templates_panel.retranslate()
        self.transitions_panel.retranslate()
        self.effects_panel.retranslate()
        self.subtitle_panel.retranslate()
        self.inspector.retranslate()
        self.preview.retranslate()
        self.transport.retranslate()
        # rebuild menus to retranslate action texts
        self._build_menu()

    def closeEvent(self, e: QCloseEvent):
        if not self.controller.undo_stack.isClean():
            ans = QMessageBox.question(
                self, tr("Unsaved Changes"),
                tr("Save changes to the project before exiting?"),
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel)
            if ans == QMessageBox.StandardButton.Save:
                self.save_project()
                e.accept()
            elif ans == QMessageBox.StandardButton.Cancel:
                e.ignore()
            else:
                e.accept()
        else:
            e.accept()