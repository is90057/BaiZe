from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QToolButton, QLineEdit, QLabel, QFrame,
)

from ..core.utils import fmt_timecode, parse_timecode
from ..i18n import tr


class TransportBar(QWidget):
    play_toggled = pyqtSignal()
    stop_requested = pyqtSignal()
    step_requested = pyqtSignal(int)          # frames
    goto_requested = pyqtSignal(float)
    in_pressed = pyqtSignal()
    out_pressed = pyqtSignal()
    clear_marks_pressed = pyqtSignal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._time = 0.0
        self._playing = False
        self._setup_ui()

    def _setup_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(4)

        b = lambda icon, tip: self._button(icon, tip)

        self.btn_play = QToolButton()
        self.btn_play.setText("▶")
        self.btn_play.setToolTip(tr("Play / Pause  (Space)"))
        self.btn_play.clicked.connect(self.play_toggled)
        lay.addWidget(self.btn_play)

        btn_stop = b("■", None)
        btn_stop.setToolTip(tr("Stop"))
        btn_stop.clicked.connect(self.stop_requested)
        lay.addWidget(btn_stop)

        lay.addWidget(self._vsep())

        btn_home = b("⏮", None)
        btn_home.setToolTip(tr("Go to Start  (Home)"))
        btn_home.clicked.connect(lambda: self.goto_requested.emit(0.0))
        lay.addWidget(btn_home)

        btn_back = b("-1", None)
        btn_back.setToolTip(tr("Previous Frame  (Left)"))
        btn_back.clicked.connect(lambda: self.step_requested.emit(-1))
        lay.addWidget(btn_back)

        btn_fwd = b("+1", None)
        btn_fwd.setToolTip(tr("Next Frame  (Right)"))
        btn_fwd.clicked.connect(lambda: self.step_requested.emit(1))
        lay.addWidget(btn_fwd)

        btn_end = b("⏭", None)
        btn_end.setToolTip(tr("Go to End  (End)"))
        btn_end.clicked.connect(
            lambda: self.goto_requested.emit(self.controller.project.duration()))
        lay.addWidget(btn_end)

        lay.addWidget(self._vsep())

        self.time_edit = QLineEdit()
        self.time_edit.setFixedWidth(92)
        self.time_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_edit.returnPressed.connect(self._commit_timecode)
        lay.addWidget(self.time_edit)

        self.lbl_total = QLabel(" / 00:00:00")
        self.lbl_total.setObjectName("totalLabel")
        lay.addWidget(self.lbl_total)

        lay.addStretch(1)

        self.btn_in = QToolButton()
        self.btn_in.setText("{")
        self.btn_in.setToolTip(tr("Set In Point  (I)"))
        self.btn_in.clicked.connect(self.in_pressed)
        lay.addWidget(self.btn_in)

        self.in_label = QLabel("In: –")
        self.in_label.setObjectName("markLabel")
        lay.addWidget(self.in_label)

        self.btn_out = QToolButton()
        self.btn_out.setText("}")
        self.btn_out.setToolTip(tr("Set Out Point  (O)"))
        self.btn_out.clicked.connect(self.out_pressed)
        lay.addWidget(self.btn_out)

        self.out_label = QLabel("Out: –")
        self.out_label.setObjectName("markLabel")
        lay.addWidget(self.out_label)

        btn_clr = b("×", None)
        btn_clr.setToolTip(tr("Clear In/Out"))
        btn_clr.clicked.connect(self.clear_marks_pressed)
        lay.addWidget(btn_clr)

        self.setObjectName("transport")
        self._playing = False

    def _button(self, text: str, tip):
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip or text)
        return b

    def _vsep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setFrameShadow(QFrame.Shadow.Sunken)
        return f

    # ---------------- API ----------------
    def set_time(self, t: float, total: float | None = None):
        self._time = t
        fps = self.controller.project.fps
        self.time_edit.setText(fmt_timecode(t, fps, compact=True))
        if total is not None:
            self.lbl_total_text = fmt_timecode(total, fps, compact=True)
        else:
            self.lbl_total_text = fmt_timecode(
                self.controller.project.duration(), fps, compact=True)
        self.lbl_total.setText(f" / {self.lbl_total_text}")

    def retranslate(self):
        self.btn_play.setToolTip(tr("Play / Pause  (Space)"))
        for b, key in ((self.btn_in, "Set In Point  (I)"),
                       (self.btn_out, "Set Out Point  (O)")):
            b.setToolTip(tr(key))
        self._update_marks_text()

    def set_playing(self, playing: bool):
        self._playing = playing
        self.btn_play.setText("⏸" if playing else "▶")

    def _update_marks_text(self):
        in_t = getattr(self, "_in_t", None)
        out_t = getattr(self, "_out_t", None)
        fps = self.controller.project.fps
        self.in_label.setText(
            f"{tr('In')}: {fmt_timecode(in_t, fps, compact=True) if in_t is not None else '–'}")
        self.out_label.setText(
            f"{tr('Out')}: {fmt_timecode(out_t, fps, compact=True) if out_t is not None else '–'}")

    def set_in_out(self, in_t: float | None, out_t: float | None):
        self._in_t = in_t
        self._out_t = out_t
        self._update_marks_text()

    def _commit_timecode(self):
        val = parse_timecode(self.time_edit.text(), self.controller.project.fps)
        if val is not None:
            self.goto_requested.emit(val)