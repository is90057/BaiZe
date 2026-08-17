from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QFileDialog, QProgressBar, QGroupBox,
    QCheckBox, QSlider, QMessageBox,
)

from ..core import ffmpeg as fx
from ..core.utils import fmt_timecode, parse_timecode
from ..i18n import tr

RESOLUTIONS = [
    ("Match project", None),
    ("3840×2160 (4K)", (3840, 2160)),
    ("2560×1440 (2K)", (2560, 1440)),
    ("1920×1080 (HD)", (1920, 1080)),
    ("1280×720", (1280, 720)),
    ("854×480", (854, 480)),
]

FRAME_RATES = [
    ("Match project", None),
    ("23.976", 23.976),
    ("24", 24.0),
    ("25", 25.0),
    ("29.97", 29.97),
    ("30", 30.0),
    ("50", 50.0),
    ("60", 60.0),
]

SCALE_MODES = [
    ("Fit (letterbox)", "fit"),
    ("Crop to fill", "crop"),
    ("Stretch", "stretch"),
]

FORMATS = [
    ("H.264 MP4", {"ext": ".mp4", "vc": "libx264", "ac": "aac"}),
    ("H.265 / HEVC MP4", {"ext": ".mp4", "vc": "libx265", "ac": "aac"}),
    ("ProRes 422 MOV", {"ext": ".mov", "vc": "prores_ks", "ac": "pcm_s16le"}),
]


class _Worker(QObject):
    progress = pyqtSignal(str)
    done = pyqtSignal(bool, str)

    def __init__(self, cmd: list[str], duration: float):
        super().__init__()
        self._cmd = cmd
        self._duration = duration
        self._proc = None

    def run(self):
        err_lines = []
        try:
            self._proc = subprocess.Popen(
                self._cmd, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1)
            while True:
                if self._proc.stdout is None:
                    break
                line = self._proc.stdout.readline()
                if not line and self._proc.poll() is not None:
                    break
                if line:
                    err_lines.append(line.strip())
                    if len(err_lines) > 40:
                        err_lines.pop(0)
                    info = fx.parse_ffmpeg_progress(line)
                    if info and self._duration > 0:
                        pct = min(100, int(100 * info["time"] / self._duration))
                        self.progress.emit(f"{pct}|{fmt_timecode(info['time'], 30, compact=True)}")
                    else:
                        self.progress.emit("-1|")
            rc = self._proc.wait()
            error_msg = ""
            if rc != 0:
                error_msg = "\n".join([l for l in err_lines if l and not l.startswith("frame=")][-6:]) or f"ffmpeg exited with code {rc}."
            self.done.emit(rc == 0, error_msg)
        except Exception as exc:
            self.done.emit(False, str(exc))

    def cancel(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.kill()
            except Exception:
                pass


class ExportDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._running = False
        self.setWindowTitle(tr("Export Video"))
        self.setMinimumWidth(460)
        self._build()
        self._load_defaults()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.fmt_combo = QComboBox()
        for i, (name, _) in enumerate(FORMATS):
            self.fmt_combo.addItem(name, i)
        self._label_fmt = QLabel(tr("Format"))
        form.addRow(self._label_fmt, self.fmt_combo)

        self.res_combo = QComboBox()
        for i, (name, _) in enumerate(RESOLUTIONS):
            self.res_combo.addItem(name, i)
        self._label_res = QLabel(tr("Resolution"))
        form.addRow(self._label_res, self.res_combo)

        self.fps_combo = QComboBox()
        for i, (name, _) in enumerate(FRAME_RATES):
            self.fps_combo.addItem(name, i)
        self._label_fps = QLabel(tr("Frame rate"))
        form.addRow(self._label_fps, self.fps_combo)

        self.scale_combo = QComboBox()
        for i, (name, _) in enumerate(SCALE_MODES):
            self.scale_combo.addItem(name, i)
        self._label_scale = QLabel(tr("Scaling"))
        form.addRow(self._label_scale, self.scale_combo)

        self.range_combo = QComboBox()
        self.range_combo.addItem(tr("Entire timeline"))
        self.range_combo.addItem(tr("In–Out range"))
        self._label_range = QLabel(tr("Range"))
        form.addRow(self._label_range, self.range_combo)

        self.video_bitrate = QLineEdit("")
        self.video_bitrate.setPlaceholderText(tr("Leave empty for CRF quality"))
        self.video_bitrate.setToolTip(tr("e.g. 8M"))
        self._label_vbr = QLabel(tr("Video bitrate"))
        form.addRow(self._label_vbr, self.video_bitrate)

        self.audio_bitrate = QLineEdit("192k")
        self._label_abr = QLabel(tr("Audio bitrate"))
        form.addRow(self._label_abr, self.audio_bitrate)

        self.crf = QSlider(Qt.Orientation.Horizontal)
        self.crf.setRange(0, 30)
        self.crf.setValue(18)
        self._label_crf = QLabel(tr("Quality (CRF 0=best 30=worst)"))
        form.addRow(self._label_crf, self.crf)

        lay.addLayout(form)

        out_row = QHBoxLayout()
        self._label_out = QLabel(tr("Output:"))
        out_row.addWidget(self._label_out)
        self.out_edit = QLineEdit()
        out_row.addWidget(self.out_edit, 1)
        browse = QPushButton(tr("Browse…"))
        browse.clicked.connect(self._browse)
        out_row.addWidget(browse)
        lay.addLayout(out_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        lay.addWidget(self.progress)

        self.time_label = QLabel()
        self.time_label.setObjectName("dimText")
        lay.addWidget(self.time_label)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton(tr("Export"))
        self.start_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton(tr("Close"))
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.start_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.cancel_btn)
        lay.addLayout(btn_row)

    def retranslate(self):
        self.setWindowTitle(tr("Export Video"))
        for label, key in (
            (self._label_fmt, "Format"), (self._label_res, "Resolution"),
            (self._label_fps, "Frame rate"), (self._label_scale, "Scaling"),
            (self._label_range, "Range"), (self._label_vbr, "Video bitrate"),
            (self._label_abr, "Audio bitrate"), (self._label_crf,
                                                 "Quality (CRF 0=best 30=worst)"),
            (self._label_out, "Output:")):
            label.setText(tr(key))
        self.video_bitrate.setPlaceholderText(tr("Leave empty for CRF quality"))
        self.video_bitrate.setToolTip(tr("e.g. 8M"))
        self.range_combo.setItemText(0, tr("Entire timeline"))
        self.range_combo.setItemText(1, tr("In–Out range"))
        for combo, names in ((self.fmt_combo, [n for n, _ in FORMATS]),
                             (self.res_combo, [n for n, _ in RESOLUTIONS]),
                             (self.fps_combo, [n for n, _ in FRAME_RATES]),
                             (self.scale_combo, [n for n, _ in SCALE_MODES])):
            for i in range(combo.count()):
                combo.setItemText(i, tr(names[i]))
        self.start_btn.setText(tr("Export"))
        self.cancel_btn.setText(tr("Close"))

    def _load_defaults(self):
        p = self.controller.project
        base = Path(p.filepath or "output").parent \
            if p.filepath else Path.home()
        self.out_edit.setText(str(base / f"{p.name or 'Untitled'}.mp4"))

    def _browse(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Export to"), self.out_edit.text(),
            f"{tr('Video')} (*.mp4 *.mov)")
        if path:
            self.out_edit.setText(path)

    def duration(self) -> float:
        p = self.controller.project
        if self.range_combo.currentIndex() == 1:
            timeline = self._timeline()
            if timeline and timeline.in_point >= 0 and timeline.out_point > timeline.in_point:
                return timeline.out_point - timeline.in_point
        return p.duration()

    def _timeline(self):
        return self.parent().findChild(object, "timeline") if self.parent() else None

    def _start(self):
        if self._running:
            return
        p = self.controller.project
        out = self.out_edit.text().strip()
        if not out:
            QMessageBox.warning(self, tr("Export"), tr("Choose an output path."))
            return
        res_opt = RESOLUTIONS[self.res_combo.currentIndex()][1]
        fps_opt = FRAME_RATES[self.fps_combo.currentIndex()][1]
        fmt = FORMATS[self.fmt_combo.currentIndex()][1]
        if not res_opt:
            res_opt = (p.width, p.height)
        if not fps_opt:
            fps_opt = p.fps
        if not out.lower().endswith((".mp4", ".mov")):
            out += fmt["ext"]
        scale_mode = SCALE_MODES[self.scale_combo.currentIndex()][1]
        crf = self.crf.value()
        vbr = self.video_bitrate.text().strip()
        abr = self.audio_bitrate.text().strip() or "192k"

        start, end = 0.0, None
        if self.range_combo.currentIndex() == 1:
            t = self._timeline()
            if t and t.in_point >= 0 and t.out_point > t.in_point:
                start, end = t.in_point, t.out_point

        cmd = fx.build_ffmpeg_cmd(
            p, out, start=start, end=end, fps=fps_opt,
            resolution=res_opt, scale_mode=scale_mode,
            video_bitrate=vbr, audio_bitrate=abr, crf=crf,
            video_codec=fmt.get("vc", "libx264"),
            audio_codec=fmt.get("ac", "aac"),
        )
        dur = self.duration()
        self._running = True
        self.start_btn.setEnabled(False)
        self.progress.setValue(0)

        self._thread = QThread(self)
        self._worker = _Worker(cmd, dur)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._worker_done)
        self._worker.progress.connect(self._on_progress)
        self.cancel_btn.setText(tr("Cancel"))
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self._cancel)
        self._thread.start()

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
        self._running = False
        self.start_btn.setEnabled(True)
        self.progress.setValue(0)
        self.cancel_btn.setText(tr("Close"))
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.reject)

    def _on_progress(self, msg: str):
        pct, tc = msg.split("|", 1)
        if pct == "-1":
            return
        self.progress.setValue(int(pct))
        self.time_label.setText(f"{tr('Rendering…')} {tc}")

    def _worker_done(self, ok: bool, err: str):
        self._thread.quit()
        self._thread.wait()
        self.start_btn.setEnabled(True)
        self.progress.setValue(100 if ok else self.progress.value())
        self.cancel_btn.setText(tr("Close"))
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.reject)
        if ok:
            self.time_label.setText(tr("Export complete."))
            QMessageBox.information(
                self, tr("Export"), f"{tr('Video exported to\n')}{self.out_edit.text()}")
        else:
            self.time_label.setText(tr("Export failed."))
            QMessageBox.critical(
                self, tr("Export"), f"{tr('Export failed.\n')}{err}")
        self._running = False