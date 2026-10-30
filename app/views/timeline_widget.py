from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QPixmap, QLinearGradient
from PyQt6.QtWidgets import QWidget, QMenu, QScrollArea

from ..core import ffmpeg as fx
from ..core.utils import fmt_timecode
from ..i18n import tr

NAME_W = 150
RULER_H = 34
VIDEO_TRACK_H = 64
AUDIO_TRACK_H = 58
SNAP_PX = 8.0
HANDLE_W = 9.0
MIN_FRAME = 1e-3
BLANK_TAIL = 10.0

VIDEO_COLOR = QColor(48, 92, 160)
SELECT_COLOR = QColor(255, 178, 54)
TEXT_COLOR = QColor(224, 224, 224)
RULER_BG = QColor(36, 36, 40)
LANE_BG = QColor(24, 24, 28)
LANE_BG_ALT = QColor(21, 21, 25)
HANDLE_BG = QColor(0, 0, 0, 120)

MEDIA_MIME = "application/x-baize-media"


@dataclass
class HitResult:
    kind: str
    track_index: int
    clip_id: str | None
    area: str          # "body" | "left" | "right" | "ruler" | "none"


class TimelineWidget(QWidget):
    playhead_changed = pyqtSignal(float)
    seek_requested = pyqtSignal(float)
    user_action = pyqtSignal()
    marks_changed = pyqtSignal()
    cut_requested = pyqtSignal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.controller = controller
        self.px_per_sec = 80.0
        self.playhead = 0.0
        self.in_point = -1.0
        self.out_point = -1.0
        self.range_select_mode = False
        self._range_drag = None
        self._drag = None
        self._snapshot = None
        self._snap_marker = None
        self._scrub = False
        self._hover_hit = None
        self._tracks_geom: list[tuple[str, int, int]] = []
        self.controller.project_changed.connect(self.on_project_changed)
        self.controller.timeline_changed.connect(self.update_preview)
        self.on_project_changed()

    def set_range_select_mode(self, enabled: bool):
        self.range_select_mode = enabled
        self.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)
        self.update()

    # ---------------- geometry ----------------
    def track_height(self, kind: str) -> int:
        if kind == "subtitle":
            return 38
        return VIDEO_TRACK_H if kind == "video" else AUDIO_TRACK_H

    def rebuild_geometry(self):
        rows: list[tuple[str, int, int]] = []
        y = RULER_H
        if self.controller.project.subtitles:
            rows.append(("subtitle", 0, y))
            y += 38 + 4
        for t in self.controller.project.video_tracks:
            rows.append(("video", t.index, y))
            y += self.track_height("video")
        y += 8
        for t in self.controller.project.audio_tracks:
            rows.append(("audio", t.index, y))
            y += self.track_height("audio")
        self._tracks_geom = rows

    def track_y(self, kind: str, idx: int) -> int:
        for k, i, y in self._tracks_geom:
            if k == kind and i == idx:
                return y
        return RULER_H

    def total_height(self) -> int:
        self.rebuild_geometry()
        h = self.track_height("audio")
        for k, i, y in self._tracks_geom:
            h = max(h, y + self.track_height(k))
        return h + 12

    def content_width(self) -> int:
        dur = max(self.controller.project.duration() + BLANK_TAIL, 1.0)
        return int(NAME_W + dur * self.px_per_sec)

    def x_for(self, time: float) -> float:
        return NAME_W + time * self.px_per_sec

    def time_for(self, x: float) -> float:
        return (x - NAME_W) / self.px_per_sec

    def on_project_changed(self):
        self.rebuild_geometry()
        self.adjust_size()

    def update_preview(self, *a):
        self.adjust_size()
        self.update()

    def adjust_size(self):
        self.rebuild_geometry()
        self.setFixedSize(self.content_width(), self.total_height())
        self.updateGeometry()

    def sizeHint(self):
        return QSize(self.content_width(), self.total_height())

    def minimumSizeHint(self):
        return QSize(self.content_width(), self.total_height())

    # ---------------- playhead ----------------
    def set_playhead(self, time: float, notify: bool = True):
        t = max(time, 0.0)
        cap = self.controller.project.duration() + BLANK_TAIL
        self.playhead = min(t, cap)
        self.ensure_visible()
        self.update()
        if notify:
            self.playhead_changed.emit(self.playhead)

    def ensure_visible(self):
        sa = self.find_parent_scroll()
        if sa is None:
            return
        x = self.x_for(self.playhead)
        hbar = sa.horizontalScrollBar()
        v0, vw = hbar.value(), hbar.pageStep()
        if x < v0 + 8:
            hbar.setValue(int(x - 8))
        elif x > v0 + vw - 8:
            hbar.setValue(int(x - vw + 8))

    def find_parent_scroll(self):
        p = self.parentWidget()
        while p is not None:
            if isinstance(p, QScrollArea):
                return p
            p = p.parentWidget()
        return None

    # ---------------- painting ----------------
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), LANE_BG)
        self.rebuild_geometry()
        self.paint_ruler(p)
        self.paint_tracks(p)
        self.paint_in_out_range(p)
        self.paint_playhead(p)
        if self._snap_marker is not None:
            self.paint_snap_marker(p)
        if self._drag and self._drag.get("ghost"):
            self.paint_ghost(p, self._drag["ghost"])
        p.end()

    def track_step(self) -> float:
        step = 1.0
        while step * self.px_per_sec < 110:
            step *= 2
        return step

    def paint_ruler(self, p: QPainter):
        p.fillRect(QRectF(0, 0, self.width(), RULER_H), RULER_BG)
        step = self.track_step()
        t = 0.0
        while self.x_for(t) <= self.width() + 120:
            x = self.x_for(t)
            if x >= NAME_W - 4:
                p.setPen(QColor(90, 90, 100))
                p.drawLine(int(x), RULER_H - 9, int(x), RULER_H)
                sub = step / 4
                for k in range(1, 4):
                    sx = int(x + k * sub * self.px_per_sec)
                    if sx < self.width():
                        p.setPen(QColor(66, 66, 74))
                        p.drawLine(sx, RULER_H - 5, sx, RULER_H)
                if x >= NAME_W:
                    p.setPen(TEXT_COLOR)
                    font = QFont("Menlo", 9)
                    p.setFont(font)
                    p.drawText(QRectF(x + 4, 3, 200, 18),
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                               fmt_timecode(t, self.controller.project.fps, compact=True))
            t += step
        p.setPen(QPen(QColor(46, 46, 52)))
        p.drawLine(0, RULER_H, self.width(), RULER_H)

    def paint_tracks(self, p: QPainter):
        project = self.controller.project
        for kind, idx, y in self._tracks_geom:
            h = self.track_height(kind)
            self.paint_lane(p, kind, idx, y, h)
            self.paint_track_header(p, kind, idx, y)
        for kind, idx, y0 in self._tracks_geom:
            if kind == "subtitle":
                for sub in project.subtitles:
                    self.paint_subtitle_clip(p, sub, y0)
            else:
                for c in project.track(kind, idx).sorted_clips():
                    self.paint_clip(p, kind, c, y0)

    def paint_lane(self, p, kind, idx, y, h):
        bg = LANE_BG if idx % 2 == 0 else LANE_BG_ALT
        p.fillRect(QRectF(0, y, self.content_width(), h), bg)
        if kind == "audio":
            p.fillRect(QRectF(0, y, self.content_width(), h),
                       QColor(16, 26, 24, 110))
        elif kind == "subtitle":
            p.fillRect(QRectF(0, y, self.content_width(), h),
                       QColor(40, 20, 50, 120))
        step = self.track_step()
        t = 0.0
        p.setPen(QPen(QColor(33, 33, 39)))
        while self.x_for(t) <= self.content_width():
            p.drawLine(int(self.x_for(t)), y + 1, int(self.x_for(t)), y + h - 1)
            t += step
        p.setPen(QPen(QColor(38, 38, 44)))
        p.drawLine(0, y, self.content_width(), y)

    def paint_track_header(self, p, kind, idx, y):
        h = self.track_height(kind)
        grad = QLinearGradient(0, y, NAME_W, y)
        grad.setColorAt(0, QColor(44, 44, 50))
        grad.setColorAt(1, QColor(30, 30, 35))
        p.fillRect(QRectF(0, y, NAME_W, h), grad)
        p.setPen(QPen(QColor(46, 46, 52)))
        p.drawLine(NAME_W, y, NAME_W, y + h)
        p.setPen(TEXT_COLOR)
        p.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        if kind == "subtitle":
            name = tr("Subtitles")
        else:
            track = self.controller.project.track(kind, idx)
            name = f"{track.name or ('V' if kind == 'video' else 'A')}{idx + 1}"
            if track.muted:
                name += "  (muted)"
        p.drawText(QRectF(6, y, NAME_W - 10, h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)
        p.setPen(QPen(QColor(46, 46, 52)))
        p.drawLine(0, y + h, self.content_width(), y + h)

    def paint_subtitle_clip(self, p, sub, y0):
        x = self.x_for(sub.position)
        w = sub.duration * self.px_per_sec
        h = 38
        if w < 2:
            return
        rect = QRectF(x, y0 + 2, w, h - 4)
        p.setBrush(QColor(130, 50, 160))
        p.setPen(QPen(QColor(220, 150, 255), 1.2))
        p.drawRoundedRect(rect, 3, 3)

        if w > 15:
            p.setPen(QColor(255, 255, 255))
            font = QFont("Helvetica", 9)
            p.setFont(font)
            fm = QFontMetrics(font)
            elided = fm.elidedText(sub.text.replace("\n", " "), Qt.TextElideMode.ElideRight, max(5, int(w - 10)))
            p.drawText(QRectF(x + 5, y0 + 2, w - 10, h - 4),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

    def paint_clip(self, p, kind, c, y0):
        x = self.x_for(c.position)
        w = c.duration * self.px_per_sec
        h = self.track_height(kind)
        if w < 2:
            return
        rect = QRectF(x, y0 + 2, w, h - 4)
        selected = c.id in self.controller._selected
        if selected:
            p.setBrush(QColor(92, 62, 18))
            p.setPen(QPen(QColor(240, 170, 40), 1.5))
        else:
            p.setBrush(VIDEO_COLOR if kind == "video" else QColor(42, 118, 94))
            p.setPen(QPen(QColor(0, 0, 0, 100)))
        p.drawRoundedRect(rect, 3, 3)

        media = self.controller.project.clip_media(c)
        if kind == "video" and media and w > 30:
            strip = fx.sprite_strip(media.path, media.duration)
            if strip:
                pm = QPixmap(strip)
                if not pm.isNull():
                    aspect = pm.width() / max(pm.height(), 1)
                    target_h = h - 4
                    target_w = target_h * aspect
                    if target_w >= w:
                        target_w = w
                        target_h = w / aspect
                    p.setOpacity(0.92 if not selected else 0.75)
                    target_rect = QRectF(x, y0 + 2 + (h - 2 - target_h) / 2, target_w, target_h)
                    p.drawPixmap(target_rect, pm, QRectF(pm.rect()))
                    p.setOpacity(1.0)

        if w > 30:
            p.setPen(TEXT_COLOR)
            font = QFont("Helvetica", 9)
            p.setFont(font)
            name = c.name or (media.name if media else "")
            fm = QFontMetrics(font)
            elided = fm.elidedText(name, Qt.TextElideMode.ElideMiddle, int(w - 24))
            p.drawText(QRectF(x + HANDLE_W + 2, y0 + 2, w - 2 * HANDLE_W - 6, h - 4),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)
        if w > 130:
            p.setPen(QColor(215, 215, 218))
            p.drawText(QRectF(x + w - 86, y0 + h - 18, 80, 14),
                       Qt.AlignmentFlag.AlignRight,
                       fmt_timecode(c.duration, self.controller.project.fps, compact=True))

        if w > 3 * HANDLE_W + 6:
            p.setBrush(HANDLE_BG)
            p.setPen(QPen(QColor(255, 255, 255, 40)))
            p.drawRoundedRect(QRectF(x, y0 + 2, HANDLE_W, h - 4), 2, 2)
            p.drawRoundedRect(QRectF(x + w - HANDLE_W, y0 + 2, HANDLE_W, h - 4), 2, 2)

        # Draw Transition Indicators
        if kind == "video":
            from PyQt6.QtGui import QPainterPath
            if getattr(c, "fade_in_duration", 0.0) > 0:
                in_w = min(c.fade_in_duration * self.px_per_sec, w)
                path = QPainterPath()
                path.moveTo(x, y0 + 2)
                path.lineTo(x + in_w, y0 + 2)
                path.lineTo(x, y0 + h - 2)
                path.closeSubpath()
                p.fillPath(path, QColor(140, 70, 220, 110))
                p.setPen(QPen(QColor(200, 150, 255), 1))
                p.drawLine(QPointF(x, y0 + h - 2), QPointF(x + in_w, y0 + 2))
                if in_w > 20:
                    p.setFont(QFont("Helvetica", 7))
                    p.setPen(QColor(240, 230, 255))
                    p.drawText(QRectF(x + 2, y0 + 2, in_w - 2, 12),
                               Qt.AlignmentFlag.AlignLeft, c.fade_in_type[:6])

            if getattr(c, "fade_out_duration", 0.0) > 0:
                out_w = min(c.fade_out_duration * self.px_per_sec, w)
                path = QPainterPath()
                path.moveTo(x + w, y0 + 2)
                path.lineTo(x + w - out_w, y0 + h - 2)
                path.lineTo(x + w, y0 + h - 2)
                path.closeSubpath()
                p.fillPath(path, QColor(220, 90, 70, 110))
                p.setPen(QPen(QColor(255, 160, 140), 1))
                p.drawLine(QPointF(x + w - out_w, y0 + h - 2), QPointF(x + w, y0 + 2))
                if out_w > 20:
                    p.setFont(QFont("Helvetica", 7))
                    p.setPen(QColor(255, 230, 230))
                    p.drawText(QRectF(x + w - out_w, y0 + h - 14, out_w - 2, 12),
                               Qt.AlignmentFlag.AlignRight, c.fade_out_type[:6])

    def paint_in_out_range(self, p: QPainter):
        th = self.total_height()
        has_in = self.in_point >= 0
        has_out = self.out_point >= 0
        if has_in and has_out and self.out_point > self.in_point:
            x0 = max(float(NAME_W), self.x_for(self.in_point))
            x1 = max(x0, self.x_for(self.out_point))
            w = x1 - x0
            # Track area highlight
            p.fillRect(QRectF(x0, RULER_H, w, th - RULER_H), QColor(235, 75, 60, 65))
            # Ruler area highlight
            p.fillRect(QRectF(x0, 0, w, RULER_H), QColor(220, 65, 55, 130))

            # Left & Right boundary lines and handles
            p.setPen(QPen(QColor(255, 110, 90, 235), 2.0))
            p.drawLine(int(x0), 0, int(x0), th)
            p.drawLine(int(x1), 0, int(x1), th)

            p.setBrush(QColor(235, 75, 60))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(x0, 2, 6, RULER_H - 4), 2, 2)
            p.drawRoundedRect(QRectF(x1 - 6, 2, 6, RULER_H - 4), 2, 2)

            if w > 64:
                dur = self.out_point - self.in_point
                badge = f"✂ {tr('Selected')}: {fmt_timecode(dur, self.controller.project.fps, compact=True)}"
                p.setFont(QFont("Helvetica", 8, QFont.Weight.Bold))
                p.setPen(QColor(255, 245, 240))
                p.drawText(
                    QRectF(x0 + 8, 2, w - 16, RULER_H - 4),
                    Qt.AlignmentFlag.AlignCenter,
                    badge,
                )
        else:
            if has_in:
                xi = int(max(float(NAME_W), self.x_for(self.in_point)))
                p.setPen(QPen(QColor(80, 210, 120, 220), 2.0))
                p.drawLine(xi, 0, xi, th)
                p.setBrush(QColor(80, 210, 120))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(QRectF(xi, 2, 6, RULER_H - 4), 2, 2)
            if has_out:
                xo = int(max(float(NAME_W), self.x_for(self.out_point)))
                p.setPen(QPen(QColor(245, 150, 60, 220), 2.0))
                p.drawLine(xo, 0, xo, th)
                p.setBrush(QColor(245, 150, 60))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(QRectF(xo - 6, 2, 6, RULER_H - 4), 2, 2)

    def paint_playhead(self, p: QPainter):
        x = int(self.x_for(self.playhead))
        if x < 0 or x > self.content_width() + 10:
            return
        p.setPen(QPen(QColor(235, 90, 90), 1.4))
        p.drawLine(x, RULER_H, x, self.total_height())
        p.setBrush(QColor(235, 90, 90))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon([QPointF(x - 5, 2), QPointF(x + 5, 2), QPointF(x, RULER_H - 2)])

    def paint_snap_marker(self, p: QPainter):
        x = self.x_for(self._snap_marker)
        p.setPen(QPen(QColor(120, 200, 255), 1))
        p.drawLine(int(x), RULER_H, int(x), self.total_height())

    def paint_ghost(self, p, ghost):
        kind, idx, c, y0, pos, dur = ghost
        x = self.x_for(pos)
        w = dur * self.px_per_sec
        h = self.track_height(kind) - 4
        p.setBrush(QColor(120, 200, 255, 60))
        p.setPen(QPen(QColor(120, 200, 255), 1.2, Qt.PenStyle.DashLine))
        p.drawRoundedRect(QRectF(x, y0 + 2, w, h), 3, 3)

    # ---------------- hit testing ----------------
    def hit_test(self, pos):
        x, y = pos.x(), pos.y()
        project = self.controller.project
        if y < RULER_H:
            if self.in_point >= 0 and abs(x - self.x_for(self.in_point)) <= 8:
                return HitResult("ruler", -1, None, "in_handle")
            if self.out_point >= 0 and abs(x - self.x_for(self.out_point)) <= 8:
                return HitResult("ruler", -1, None, "out_handle")
            return HitResult("ruler", -1, None, "ruler")
        for kind, idx, y0 in self._tracks_geom:
            h = self.track_height(kind)
            if y0 <= y < y0 + h and x >= NAME_W:
                if kind == "subtitle":
                    for sub in reversed(project.subtitles):
                        cx = self.x_for(sub.position)
                        cw = sub.duration * self.px_per_sec
                        if cx <= x <= cx + cw:
                            return HitResult("subtitle", 0, sub.id, "body")
                else:
                    for c in reversed(project.track(kind, idx).clips):
                        cx = self.x_for(c.position)
                        cw = c.duration * self.px_per_sec
                        if cx <= x <= cx + cw:
                            if cw > 3 * HANDLE_W and x < cx + HANDLE_W:
                                return HitResult(kind, idx, c.id, "left")
                            if cw > 3 * HANDLE_W and x > cx + cw - HANDLE_W:
                                return HitResult(kind, idx, c.id, "right")
                            return HitResult(kind, idx, c.id, "body")
        return HitResult("none", -1, None, "none")

    # ---------------- mouse ----------------
    def mousePressEvent(self, e):
        self.setFocus()
        hit = self.hit_test(e.position().toPoint())
        self._hover_hit = hit
        if e.button() == Qt.MouseButton.LeftButton:
            if hit.area in ("in_handle", "out_handle"):
                self._range_drag = (hit.area, 0.0)
                e.accept()
                return
            if self.range_select_mode or (e.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                t0 = max(0.0, self.time_for(e.position().x()))
                self.controller.clear_selection()
                self._range_drag = ("new_range", t0)
                self.in_point = t0
                self.out_point = t0
                self.set_playhead(t0)
                self.seek_requested.emit(self.playhead)
                self.marks_changed.emit()
                self.update()
                e.accept()
                return
            if hit.kind == "subtitle":
                main_win = self.window()
                if hasattr(main_win, "inspector"):
                    main_win.inspector.select_subtitle(hit.clip_id)
                self.update()
            elif hit.area in ("ruler", "none"):
                self.controller.clear_selection()
                self._scrub = True
                self.set_playhead(self.time_for(e.position().x()))
                self.seek_requested.emit(self.playhead)
            elif hit.area in ("body", "left", "right"):
                c = self.controller.project.clip_by_id(hit.clip_id)
                if c is None:
                    return
                linked_ids = [lc.id for lc in self.controller.find_linked_clips(c.id)]
                if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    curr = list(self.controller._selected)
                    if c.id in curr:
                        for lid in linked_ids:
                            if lid in curr:
                                curr.remove(lid)
                    else:
                        for lid in linked_ids:
                            if lid not in curr:
                                curr.append(lid)
                    self.controller.set_selection(curr)
                elif c.id not in self.controller._selected:
                    self.controller.set_selection(linked_ids)
                self._begin_drag(hit, e.position())
        elif e.button() == Qt.MouseButton.RightButton:
            if hit.area in ("body", "left", "right"):
                if hit.clip_id not in self.controller._selected:
                    linked_ids = [lc.id for lc in self.controller.find_linked_clips(hit.clip_id)]
                    self.controller.set_selection(linked_ids)
                self.show_context_menu(e.globalPosition().toPoint(), hit)
            elif self.in_point >= 0 and self.out_point > self.in_point:
                self.show_context_menu(e.globalPosition().toPoint(), hit)
            else:
                self.controller.clear_selection()
        e.accept()

    def mouseMoveEvent(self, e):
        if (e.buttons() & Qt.MouseButton.LeftButton) and self._range_drag:
            mode, anchor = self._range_drag
            t = max(0.0, min(self.time_for(e.position().x()), self.controller.project.duration() + BLANK_TAIL))
            if mode == "new_range":
                self.in_point = min(anchor, t)
                self.out_point = max(anchor, t)
            elif mode == "in_handle":
                if self.out_point >= 0:
                    self.in_point = min(t, max(0.0, self.out_point - MIN_FRAME))
                else:
                    self.in_point = t
            elif mode == "out_handle":
                if self.in_point >= 0:
                    self.out_point = max(t, self.in_point + MIN_FRAME)
                else:
                    self.out_point = t
            self.set_playhead(t)
            self.seek_requested.emit(self.playhead)
            self.marks_changed.emit()
            self.update()
        elif (e.buttons() & Qt.MouseButton.LeftButton) and self._drag:
            self._update_drag(e.position())
        elif (e.buttons() & Qt.MouseButton.LeftButton) and self._scrub:
            self.set_playhead(self.time_for(e.position().x()))
            self.seek_requested.emit(self.playhead)
        else:
            self.setCursor(self.cursor_for(e.position().toPoint()))
        e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self._range_drag:
                if self.out_point >= 0 and self.in_point >= 0 and self.out_point - self.in_point < 1e-3:
                    self.out_point = -1.0
                    self.marks_changed.emit()
                self._range_drag = None
                self.update()
            if self._drag:
                self._commit_drag()
            self._scrub = False
        e.accept()

    def mouseDoubleClickEvent(self, e):
        hit = self.hit_test(e.position().toPoint())
        if hit.kind == "subtitle" and hit.clip_id:
            sub = self.controller.project.subtitle_by_id(hit.clip_id)
            if sub:
                from PyQt6.QtWidgets import QInputDialog
                text, ok = QInputDialog.getMultiLineText(
                    self,
                    tr("Edit Subtitle Text"),
                    tr("Enter subtitle text content:"),
                    sub.text
                )
                if ok and text is not None:
                    self.controller.update_subtitle(sub.id, text=text)
                    self.controller.timeline_changed.emit()
                    main_win = self.window()
                    if hasattr(main_win, "inspector"):
                        main_win.inspector.select_subtitle(sub.id)
        e.accept()

    def cursor_for(self, pos) -> Qt.CursorShape:
        if self.range_select_mode:
            return Qt.CursorShape.CrossCursor
        hit = self.hit_test(pos)
        if hit.area in ("left", "right", "in_handle", "out_handle"):
            return Qt.CursorShape.SizeHorCursor
        if hit.area == "body":
            return Qt.CursorShape.SizeAllCursor
        return Qt.CursorShape.ArrowCursor

    # ---------------- drag ----------------
    def _begin_drag(self, hit: HitResult, pos: QPointF):
        c = self.controller.project.clip_by_id(hit.clip_id)
        media = self.controller.project.clip_media(c)
        linked = [
            dict(
                clip_id=lc.id, kind=self.controller.clip_kind(lc.id),
                position=lc.position, trim_in=lc.trim_in,
                duration=lc.duration, track_index=lc.track_index,
            )
            for lc in self.controller.find_linked_clips(c.id)
            if lc.id != c.id
        ]
        self._snapshot = dict(
            clip_id=c.id, kind=hit.kind, position=c.position, trim_in=c.trim_in,
            duration=c.duration, track_index=c.track_index,
            linked=linked,
        )
        self._drag = dict(
            mode=hit.area, session_x0=pos.x(), session_y0=pos.y(),
            start_pos=c.position, start_in=c.trim_in, start_dur=c.duration,
            start_track=c.track_index,
            src_dur=(media.duration if media else c.duration),
            ghost=None,
        )

    def snap_candidates(self) -> list[float]:
        cands = {0.0}
        project = self.controller.project
        if self.playhead > 1e-4:
            cands.add(self.playhead)
        if self.in_point >= 0:
            cands.add(self.in_point)
        if self.out_point >= 0:
            cands.add(self.out_point)
        skip_ids = {self._snapshot["clip_id"]} | {l["clip_id"] for l in self._snapshot.get("linked", [])}
        for kind, idx, _ in self._tracks_geom:
            if kind in ("video", "audio"):
                for cc in project.track(kind, idx).clips:
                    if cc.id in skip_ids:
                        continue
                    cands.add(cc.position)
                    cands.add(cc.end)
        return cands

    def _snap(self, value: float) -> float:
        thr = SNAP_PX / self.px_per_sec
        best, best_d = value, thr
        for cand in self.snap_candidates():
            d = abs(cand - value)
            if d < best_d:
                best, best_d = cand, d
        self._snap_marker = best if best_d < thr else None
        return best

    def _update_drag(self, pos: QPointF):
        d = self._drag
        c = self.controller.project.clip_by_id(self._snapshot["clip_id"])
        if c is None:
            return
        kind = self._snapshot["kind"]
        dx = (pos.x() - d["session_x0"]) / self.px_per_sec

        if d["mode"] == "body":
            new_pos = self._snap(d["start_pos"] + dx)
            if new_pos < 0:
                new_pos = 0.0
            new_idx = self.track_at_y(pos.y(), kind)
            if new_idx is None:
                new_idx = d["start_track"]
            if new_idx != c.track_index:
                project = self.controller.project
                old = project.track(kind, c.track_index)
                old.clips = [x for x in old.clips if x.id != c.id]
                c.track_index = new_idx
                project.track(kind, new_idx).clips.append(c)
            c.position = new_pos
            for linfo in self._snapshot.get("linked", []):
                lc = self.controller.project.clip_by_id(linfo["clip_id"])
                if lc:
                    lc.position = new_pos
            d["ghost"] = (kind, new_idx, c, self.track_y(kind, new_idx), new_pos, c.duration)

        elif d["mode"] == "left":
            new_in = self._snap(d["start_in"] + dx)
            new_in = max(0.0, min(new_in, d["src_dur"] - MIN_FRAME))
            delta = new_in - d["start_in"]
            edge = d["start_pos"] + delta
            if edge < 0:
                delta = -d["start_pos"]
                new_in = d["start_in"] + delta
                edge = 0.0
            new_dur = max(MIN_FRAME, min(d["start_dur"] - delta,
                                         d["src_dur"] - new_in))
            c.trim_in = new_in
            c.position = edge
            c.duration = new_dur
            for linfo in self._snapshot.get("linked", []):
                lc = self.controller.project.clip_by_id(linfo["clip_id"])
                if lc:
                    lc.trim_in = new_in
                    lc.position = edge
                    lc.duration = new_dur
            d["ghost"] = (kind, c.track_index, c, self.track_y(kind, c.track_index),
                          c.position, c.duration)

        else:  # right
            new_dur = self._snap(d["start_dur"] + dx)
            new_dur = max(MIN_FRAME, min(new_dur, d["src_dur"] - d["start_in"]))
            c.duration = new_dur
            for linfo in self._snapshot.get("linked", []):
                lc = self.controller.project.clip_by_id(linfo["clip_id"])
                if lc:
                    lc.duration = new_dur
            d["ghost"] = (kind, c.track_index, c, self.track_y(kind, c.track_index),
                          c.position, c.duration)

        self.update()

    def track_at_y(self, y: float, target_kind: str | None = None) -> int | None:
        for kind, idx, y0 in self._tracks_geom:
            if kind in ("video", "audio") and (target_kind is None or kind == target_kind):
                h = self.track_height(kind)
                if y0 <= y < y0 + h:
                    return idx
        return None

    def _commit_drag(self):
        d, snap = self._drag, self._snapshot
        c = self.controller.project.clip_by_id(snap["clip_id"])
        self._drag = None
        self._snapshot = None
        self._snap_marker = None
        if c is None:
            self.update()
            return
        kind = snap["kind"]
        final_pos, final_track = c.position, c.track_index
        final_in, final_dur = c.trim_in, c.duration

        # Restore original properties before pushing undo commands
        if c.track_index != snap["track_index"]:
            project = self.controller.project
            cur_tr = project.track(kind, c.track_index)
            cur_tr.clips = [x for x in cur_tr.clips if x.id != c.id]
            c.track_index = snap["track_index"]
            project.track(kind, snap["track_index"]).clips.append(c)
        c.position = snap["position"]
        c.trim_in = snap["trim_in"]
        c.duration = snap["duration"]
        for linfo in snap.get("linked", []):
            lc = self.controller.project.clip_by_id(linfo["clip_id"])
            if lc:
                lc.position = linfo["position"]
                lc.trim_in = linfo["trim_in"]
                lc.duration = linfo["duration"]

        moved_or_trimmed = (
            abs(final_pos - snap["position"]) > 1e-5
            or final_track != snap["track_index"]
            or abs(final_in - snap["trim_in"]) > 1e-5
            or abs(final_dur - snap["duration"]) > 1e-5
        )
        if moved_or_trimmed:
            linked = snap.get("linked", [])
            if linked:
                self.controller.undo_stack.beginMacro("Edit Clip")
            if d["mode"] == "body":
                self.controller.move_clip(c.id, final_pos, final_track, kind)
                for linfo in linked:
                    self.controller.move_clip(linfo["clip_id"], final_pos, linfo["track_index"], linfo["kind"])
            else:
                self.controller.trim_clip(c.id, final_in, final_dur, final_pos)
                for linfo in linked:
                    self.controller.trim_clip(linfo["clip_id"], final_in, final_dur, final_pos)
            if linked:
                self.controller.undo_stack.endMacro()
        self.update()

    # ---------------- actions ----------------
    def split_at_playhead(self) -> int:
        return self.controller.split_at_time(self.playhead, self.controller._selected)

    def cut_selected(self) -> float:
        """Cut out the selected unwanted segment (In-Out range or selected clips) across video & audio."""
        if self.in_point >= 0 and self.out_point > self.in_point + 1e-3:
            t0, t1 = self.in_point, self.out_point
            cut_dur = self.controller.cut_range(t0, t1, ripple=True)
            if cut_dur > 0:
                self.in_point = -1.0
                self.out_point = -1.0
                self.marks_changed.emit()
                self.set_playhead(t0)
                self.seek_requested.emit(self.playhead)
                self.update()
            return cut_dur

        clips = self.controller.selected_clips()
        if clips:
            earliest = min(c.position for c in clips)
            cut_dur = self.controller.cut_selected_clips(ripple=True)
            if cut_dur > 0:
                self.set_playhead(earliest)
                self.seek_requested.emit(self.playhead)
                self.update()
            return cut_dur

        if self.in_point >= 0 and abs(self.playhead - self.in_point) > 1e-3:
            t0, t1 = min(self.in_point, self.playhead), max(self.in_point, self.playhead)
            cut_dur = self.controller.cut_range(t0, t1, ripple=True)
            if cut_dur > 0:
                self.in_point = -1.0
                self.out_point = -1.0
                self.marks_changed.emit()
                self.set_playhead(t0)
                self.seek_requested.emit(self.playhead)
                self.update()
            return cut_dur

        return 0.0

    def kind_of(self, c) -> str:
        for kind, idx, _ in self._tracks_geom:
            if kind in ("video", "audio") and c.track_index == idx:
                if any(cc.id == c.id
                       for cc in self.controller.project.track(kind, idx).clips):
                    return kind
        return "video"

    def delete_selected(self):
        clips = list(self.controller.selected_clips())
        if not clips:
            return
        seen: set[str] = set()
        targets = []
        for c in clips:
            for lc in self.controller.find_linked_clips(c.id):
                if lc.id not in seen:
                    seen.add(lc.id)
                    targets.append(lc)
        self.controller.undo_stack.beginMacro("Delete Clip")
        for lc in targets:
            self.controller.remove_clip(lc.id, self.kind_of(lc))
        self.controller.undo_stack.endMacro()
        self.controller.set_selection([])

    def nudge_playhead(self, frames: int):
        fps = self.controller.project.fps
        self.set_playhead(self.playhead + frames / fps)
        self.seek_requested.emit(self.playhead)

    def fit_timeline(self):
        dur = max(self.controller.project.duration(), 1.0)
        avail = max(self.width() - NAME_W - 60, 200)
        self.px_per_sec = max(avail / dur, 2.0)
        self.adjust_size()
        self.update()

    def zoom(self, factor: float):
        self.px_per_sec = min(max(self.px_per_sec * factor, 2.0), 4000.0)
        self.adjust_size()
        self.update()

    def show_context_menu(self, global_pos, hit: HitResult):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #26262c; color: #e2e2e2; border: 1px solid #3a3a42;}"
            "QMenu::item:selected { background: #3a6ea5; }")
        act_cut = menu.addAction(tr("Cut Selected (Video & Audio)\tCtrl+X"))
        act_split = menu.addAction(tr("Split at Playhead\tCtrl+B"))
        menu.addSeparator()
        act_delete = menu.addAction(tr("Delete Clip\tDelete"))
        action = menu.exec(global_pos)
        if action == act_cut:
            self.cut_requested.emit()
        elif action == act_split:
            self.split_at_playhead()
        elif action == act_delete:
            self.delete_selected()

    # ---------------- drag & drop ----------------
    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(MEDIA_MIME):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat(MEDIA_MIME):
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        e.accept()

    def dropEvent(self, e):
        md = e.mimeData()
        if not md.hasFormat(MEDIA_MIME):
            return
        mids = [m.strip() for m in bytes(md.data(MEDIA_MIME)).decode().split(",") if m.strip()]
        pos = e.position().toPoint()
        project = self.controller.project
        for kind, idx, y0 in self._tracks_geom:
            if kind not in ("video", "audio"):
                continue
            if y0 <= pos.y() < y0 + self.track_height(kind):
                t = max(self.time_for(pos.x()), 0.0)
                added_any = False
                for mid in mids:
                    media = project.media_by_id(mid)
                    if media is None:
                        continue
                    if kind == "video":
                        if media.has_video:
                            self.controller.add_clip(media, "video", idx, t)
                            added_any = True
                        if media.has_audio and project.audio_tracks:
                            atrack_idx = idx if any(tr.index == idx for tr in project.audio_tracks) else project.audio_tracks[0].index
                            self.controller.add_clip(media, "audio", atrack_idx, t)
                            added_any = True
                    elif kind == "audio":
                        if media.has_audio:
                            self.controller.add_clip(media, "audio", idx, t)
                            added_any = True
                        if media.has_video and project.video_tracks:
                            vtrack_idx = idx if any(tr.index == idx for tr in project.video_tracks) else project.video_tracks[0].index
                            self.controller.add_clip(media, "video", vtrack_idx, t)
                            added_any = True
                    t += media.duration
                if added_any:
                    self.user_action.emit()
                    self.update()
                    e.acceptProposedAction()
                    return
        e.ignore()

    # ---------------- misc ----------------
    def wheelEvent(self, e):
        sa = self.find_parent_scroll()
        if sa is None:
            super().wheelEvent(e)
            return
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.15 if e.angleDelta().y() > 0 else 1 / 1.15)
            e.accept()
            return
        hbar = sa.horizontalScrollBar()
        vbar = sa.verticalScrollBar()
        if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            vbar.setValue(vbar.value() - e.angleDelta().y())
        else:
            hbar.setValue(hbar.value() - e.angleDelta().y())
        e.accept()