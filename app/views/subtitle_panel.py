from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QMenu, QGroupBox,
    QComboBox, QFormLayout, QProgressDialog,
)

from ..i18n import tr
from ..core.utils import fmt_timecode
from ..core.asr import AutoSubtitleThread


class SubtitlePanel(QWidget):
    subtitle_selected = pyqtSignal(str)   # subtitle_id
    seek_requested = pyqtSignal(float)    # time_sec

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._asr_thread = None
        self._progress_dlg = None
        self._setup_ui()
        self.controller.timeline_changed.connect(self.refresh_list)
        self.controller.project_changed.connect(self.refresh_list)

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        head = QHBoxLayout()
        self._title = QLabel(tr("Subtitle Editor"))
        self._title.setStyleSheet("font-weight: bold; color: #d0d0d6;")
        head.addWidget(self._title)
        head.addStretch(1)
        lay.addLayout(head)

        # AI Auto Subtitling Group
        self.asr_box = QGroupBox(tr("AI Auto Subtitling"))
        self.asr_box.setStyleSheet("QGroupBox { font-weight: bold; color: #a0c0f0; }")
        asr_lay = QVBoxLayout(self.asr_box)
        asr_lay.setContentsMargins(6, 6, 6, 6)
        asr_lay.setSpacing(4)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.asr_model_combo = QComboBox()
        self.asr_model_combo.addItem(tr("base (Recommended)"), "base")
        self.asr_model_combo.addItem(tr("tiny (Fastest)"), "tiny")
        self.asr_model_combo.addItem(tr("small (High Accuracy)"), "small")
        self._lbl_asr_model = QLabel(tr("AI Model:"))
        form.addRow(self._lbl_asr_model, self.asr_model_combo)

        self.asr_lang_combo = QComboBox()
        self.asr_lang_combo.addItem(tr("Auto Detect"), "auto")
        self.asr_lang_combo.addItem(tr("Chinese (zh)"), "zh")
        self.asr_lang_combo.addItem(tr("English (en)"), "en")
        self.asr_lang_combo.addItem(tr("Japanese (ja)"), "ja")
        self.asr_lang_combo.addItem(tr("Korean (ko)"), "ko")
        self._lbl_asr_lang = QLabel(tr("Language:"))
        form.addRow(self._lbl_asr_lang, self.asr_lang_combo)

        self.asr_range_combo = QComboBox()
        self.asr_range_combo.addItem(tr("Entire timeline"), "timeline")
        self.asr_range_combo.addItem(tr("In–Out range"), "in_out")
        self._lbl_asr_range = QLabel(tr("Range:"))
        form.addRow(self._lbl_asr_range, self.asr_range_combo)

        asr_lay.addLayout(form)

        self.asr_start_btn = QPushButton(tr("Recognize & Generate Subtitles"))
        self.asr_start_btn.setStyleSheet(
            "background: #7a3ca3; color: white; font-weight: bold; padding: 5px;"
        )
        self.asr_start_btn.clicked.connect(self._on_start_asr_clicked)
        asr_lay.addWidget(self.asr_start_btn)
        lay.addWidget(self.asr_box)

        # Quick Add Group
        add_box = QGroupBox(tr("Add Subtitle"))
        add_lay = QVBoxLayout(add_box)
        add_lay.setContentsMargins(6, 6, 6, 6)
        add_lay.setSpacing(4)

        self.text_input = QPlainTextEdit()
        self.text_input.setPlaceholderText(tr("Type subtitle text here..."))
        self.text_input.setMaximumHeight(50)
        add_lay.addWidget(self.text_input)

        self.add_btn = QPushButton(tr("Add Subtitle at Playhead"))
        self.add_btn.setStyleSheet("background: #2a6e9a; color: white; font-weight: bold;")
        self.add_btn.clicked.connect(self._on_add_clicked)
        add_lay.addWidget(self.add_btn)
        lay.addWidget(add_box)

        # Subtitle List
        self.list = QListWidget(self)
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        self.list.itemClicked.connect(self._on_item_clicked)
        self.list.itemDoubleClicked.connect(self._on_item_double_clicked)
        lay.addWidget(self.list, 1)

        # SRT Import / Export buttons
        srt_lay = QHBoxLayout()
        self.import_srt_btn = QPushButton(tr("Import SRT…"))
        self.import_srt_btn.clicked.connect(self._on_import_srt)
        srt_lay.addWidget(self.import_srt_btn)

        self.export_srt_btn = QPushButton(tr("Export SRT…"))
        self.export_srt_btn.clicked.connect(self._on_export_srt)
        srt_lay.addWidget(self.export_srt_btn)
        lay.addLayout(srt_lay)

        self.refresh_list()

    def retranslate(self):
        self._title.setText(tr("Subtitle Editor"))
        self.asr_box.setTitle(tr("AI Auto Subtitling"))
        self._lbl_asr_model.setText(tr("AI Model:"))
        self.asr_model_combo.setItemText(0, tr("base (Recommended)"))
        self.asr_model_combo.setItemText(1, tr("tiny (Fastest)"))
        self.asr_model_combo.setItemText(2, tr("small (High Accuracy)"))
        self._lbl_asr_lang.setText(tr("Language:"))
        self.asr_lang_combo.setItemText(0, tr("Auto Detect"))
        self.asr_lang_combo.setItemText(1, tr("Chinese (zh)"))
        self.asr_lang_combo.setItemText(2, tr("English (en)"))
        self.asr_lang_combo.setItemText(3, tr("Japanese (ja)"))
        self.asr_lang_combo.setItemText(4, tr("Korean (ko)"))
        self._lbl_asr_range.setText(tr("Range:"))
        self.asr_range_combo.setItemText(0, tr("Entire timeline"))
        self.asr_range_combo.setItemText(1, tr("In–Out range"))
        self.asr_start_btn.setText(tr("Recognize & Generate Subtitles"))

        self.text_input.setPlaceholderText(tr("Type subtitle text here..."))
        self.add_btn.setText(tr("Add Subtitle at Playhead"))
        self.import_srt_btn.setText(tr("Import SRT…"))
        self.export_srt_btn.setText(tr("Export SRT…"))
        self.refresh_list()

    def _on_start_asr_clicked(self):
        model_name = self.asr_model_combo.currentData() or "base"
        language = self.asr_lang_combo.currentData() or "auto"
        range_type = self.asr_range_combo.currentData()

        main_win = self.window()
        timeline = getattr(main_win, "timeline", None)

        start_time, end_time = 0.0, None
        if range_type == "in_out" and timeline:
            if timeline.in_point >= 0 and timeline.out_point > timeline.in_point:
                start_time = timeline.in_point
                end_time = timeline.out_point

        self._progress_dlg = QProgressDialog(
            tr("Extracting audio from timeline..."), tr("Cancel"), 0, 100, self
        )
        self._progress_dlg.setWindowTitle(tr("Speech Recognition Progress"))
        self._progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dlg.setValue(5)
        self._progress_dlg.canceled.connect(self._on_asr_canceled)
        self._progress_dlg.show()

        self._asr_thread = AutoSubtitleThread(
            project=self.controller.project,
            model_name=model_name,
            language=language,
            start_time=start_time,
            end_time=end_time,
            parent=self,
        )
        self._asr_thread.progress_changed.connect(self._on_asr_progress)
        self._asr_thread.finished_success.connect(self._on_asr_finished)
        self._asr_thread.failed_error.connect(self._on_asr_failed)
        self._asr_thread.start()

    def _on_asr_progress(self, val: int, msg: str):
        if self._progress_dlg:
            self._progress_dlg.setValue(val)
            self._progress_dlg.setLabelText(msg)

    def _on_asr_finished(self, clips: list):
        if self._progress_dlg:
            self._progress_dlg.close()
            self._progress_dlg = None

        if clips:
            self.controller.add_auto_subtitles(clips)
            self.refresh_list()
            QMessageBox.information(
                self, tr("AI Auto Subtitling"),
                tr("Done! Generated {count} subtitles.").format(count=len(clips)))
        else:
            QMessageBox.information(
                self, tr("AI Auto Subtitling"),
                tr("No speech detected on audio track."))

    def _on_asr_failed(self, err_msg: str):
        if self._progress_dlg:
            self._progress_dlg.close()
            self._progress_dlg = None
        QMessageBox.critical(
            self, tr("Speech Recognition Failed"),
            f"{tr('Speech Recognition Failed')}:\n{err_msg}")

    def _on_asr_canceled(self):
        if self._asr_thread:
            self._asr_thread.cancel()
            self._asr_thread.quit()

    def refresh_list(self):
        self.list.clear()
        subs = sorted(self.controller.project.subtitles, key=lambda s: s.position)
        for s in subs:
            tc = fmt_timecode(s.position, self.controller.project.fps, compact=True)
            preview = s.text.replace("\n", " ")
            item = QListWidgetItem(f"[{tc}]  {preview}")
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            item.setToolTip(f"[{tc}] ({s.duration:.1f}s)\n{s.text}")
            self.list.addItem(item)

    def _on_add_clicked(self):
        text = self.text_input.toPlainText().strip()
        if not text:
            text = "Your Subtitle Here"
        pos = getattr(self.parent(), "timeline", None)
        playhead_time = pos.playhead if pos else 0.0
        sub = self.controller.add_subtitle(text, playhead_time, duration=3.0)
        self.text_input.clear()
        self.refresh_list()
        self.subtitle_selected.emit(sub.id)

    def _on_item_clicked(self, item: QListWidgetItem):
        sub_id = item.data(Qt.ItemDataRole.UserRole)
        if sub_id:
            self.subtitle_selected.emit(sub_id)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        sub_id = item.data(Qt.ItemDataRole.UserRole)
        sub = self.controller.project.subtitle_by_id(sub_id)
        if sub:
            self.seek_requested.emit(sub.position)
            self.subtitle_selected.emit(sub.id)

    def _context_menu(self, pos):
        item = self.list.itemAt(pos)
        if item is None:
            return
        sub_id = item.data(Qt.ItemDataRole.UserRole)
        sub = self.controller.project.subtitle_by_id(sub_id)
        if sub is None:
            return
        menu = QMenu(self)
        del_act = menu.addAction(tr("Delete Subtitle"))
        jump_act = menu.addAction(tr("Jump to Playhead"))
        action = menu.exec(self.list.mapToGlobal(pos))
        if action == del_act:
            self.controller.remove_subtitle(sub_id)
            self.refresh_list()
        elif action == jump_act:
            self.seek_requested.emit(sub.position)

    def _on_import_srt(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Import SRT Subtitles"), "", tr("SRT Subtitle Files (*.srt)"))
        if not path:
            return
        count = self.controller.import_srt(path)
        if count > 0:
            QMessageBox.information(
                self, tr("Import SRT Subtitles"),
                tr("Imported {count} subtitles.").format(count=count))
            self.refresh_list()

    def _on_export_srt(self):
        if not self.controller.project.subtitles:
            QMessageBox.information(
                self, tr("Export SRT Subtitles"),
                tr("No subtitles to export."))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Export SRT Subtitles"), "subtitles.srt", tr("SRT Subtitle Files (*.srt)"))
        if not path:
            return
        self.controller.export_srt(path)
        QMessageBox.information(
            self, tr("Export SRT Subtitles"),
            tr("Exported subtitles to {path}").format(path=path))
