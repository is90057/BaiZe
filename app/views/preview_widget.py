from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, QSize, QRectF, QTimer, QObject, QRunnable, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtGui import QImage, QPainter, QColor, QPen, QFont, QPixmap, QBrush
from PyQt6.QtWidgets import QWidget, QApplication

from ..core import ffmpeg as fx
from ..core.utils import fmt_timecode
from ..i18n import tr

MAX_PREVIEW_WIDTH = 1280


class _Emitter(QObject):
    frame_ready = pyqtSignal(int, float, QImage)


_emitter = _Emitter()


class _DecodeJob(QRunnable):
    def __init__(self, token: int, path: str, src_time: float, target: tuple[int, int], clip=None, timeline_time: float = 0.0, is_image: bool = False, has_alpha: bool = False, overlay_info=None):
        super().__init__()
        self.token = token
        self.path = path
        self.src_time = src_time
        self.w, self.h = target
        self.clip = clip
        self.timeline_time = timeline_time
        self.is_image = is_image
        self.has_alpha = has_alpha
        self.overlay_info = overlay_info or []

    def _decode_and_process_layer(self, clip, path: str, src_time: float, is_image: bool, has_alpha: bool) -> np.ndarray | None:
        pip_w = float(getattr(clip, "pip_w", 1.0) if clip else 1.0)
        pip_h = float(getattr(clip, "pip_h", 1.0) if clip else 1.0)
        lw = max(2, int(round(pip_w * self.w)) & ~1)
        lh = max(2, int(round(pip_h * self.h)) & ~1)
        is_ck = bool(getattr(clip, "chroma_key_enabled", False)) if clip else False

        if has_alpha or is_image or is_ck:
            layer = fx.decode_frame_rgba(path, src_time, lw, lh, is_image=is_image)
            if layer is None:
                return None
            if is_ck and clip is not None:
                layer = fx.apply_chroma_key(
                    layer, clip.chroma_key_color,
                    clip.chroma_key_similarity, clip.chroma_key_smoothness
                )
        else:
            layer = fx.decode_frame(path, src_time, lw, lh)
            if layer is None:
                return None

        if clip is not None:
            br = getattr(clip, "brightness", 0.0)
            ct = getattr(clip, "contrast", 1.0)
            sat = getattr(clip, "saturation", 1.0)
            if abs(br) > 1e-4 or abs(ct - 1.0) > 1e-4 or abs(sat - 1.0) > 1e-4:
                layer = fx.process_color_correction(layer, br, ct, sat)

            fm = getattr(clip, "focus_mode", "none")
            ba = getattr(clip, "blur_amount", 0.0)
            if fm != "none" or ba > 0:
                layer = fx.process_blur_focus(layer, fm, ba)

            vfx = getattr(clip, "video_fx", "none")
            if vfx != "none":
                layer = fx.process_video_effect(layer, vfx, current_time=self.timeline_time)

            if getattr(clip, "object_removal_enabled", False):
                masks = getattr(clip, "object_removal_masks", [])
                if masks:
                    layer = fx.apply_object_removal_inpainting(layer, masks)

            if layer.shape[2] == 3:
                layer = fx.process_frame_transition(layer, clip, self.timeline_time)
            else:
                rgb_part = fx.process_frame_transition(layer[:, :, :3], clip, self.timeline_time)
                layer = np.dstack([rgb_part, layer[:, :, 3]])

        return layer

    @pyqtSlot()
    def run(self):
        arr = None
        try:
            canvas = np.zeros((self.h, self.w, 3), dtype=np.uint8)
            base_layer = self._decode_and_process_layer(
                self.clip, self.path, self.src_time, self.is_image, self.has_alpha
            )
            if base_layer is not None:
                canvas = fx.composite_pip_layer(
                    canvas,
                    base_layer,
                    pip_x=float(getattr(self.clip, "pip_x", 0.0) if self.clip else 0.0),
                    pip_y=float(getattr(self.clip, "pip_y", 0.0) if self.clip else 0.0),
                    pip_w=float(getattr(self.clip, "pip_w", 1.0) if self.clip else 1.0),
                    pip_h=float(getattr(self.clip, "pip_h", 1.0) if self.clip else 1.0),
                    opacity=float(getattr(self.clip, "opacity", 1.0) if self.clip else 1.0),
                    border_width=int(getattr(self.clip, "pip_border_width", 0) if self.clip else 0),
                    border_color=str(getattr(self.clip, "pip_border_color", "#FFFFFF") if self.clip else "#FFFFFF"),
                )

            if self.overlay_info:
                for o_clip, o_media, o_src_time in self.overlay_info:
                    o_layer = self._decode_and_process_layer(
                        o_clip, o_media.path, o_src_time, o_media.is_image, o_media.has_alpha
                    )
                    if o_layer is not None:
                        canvas = fx.composite_pip_layer(
                            canvas,
                            o_layer,
                            pip_x=float(getattr(o_clip, "pip_x", 0.0)),
                            pip_y=float(getattr(o_clip, "pip_y", 0.0)),
                            pip_w=float(getattr(o_clip, "pip_w", 1.0)),
                            pip_h=float(getattr(o_clip, "pip_h", 1.0)),
                            opacity=float(getattr(o_clip, "opacity", 1.0)),
                            border_width=int(getattr(o_clip, "pip_border_width", 0)),
                            border_color=str(getattr(o_clip, "pip_border_color", "#FFFFFF")),
                        )
            arr = canvas
        except Exception:
            arr = None
        finally:
            if QApplication.instance() is not None:
                img = QImage()
                if arr is not None and arr.size > 0:
                    arr_c = np.ascontiguousarray(arr)
                    img = QImage(arr_c.data, self.w, self.h, self.w * 3,
                                 QImage.Format.Format_RGB888).copy()
                try:
                    _emitter.frame_ready.emit(self.token, self.timeline_time, img)
                except RuntimeError:
                    pass


class PreviewWidget(QWidget):
    time_changed = pyqtSignal(float)
    play_state_changed = pyqtSignal(bool)
    pip_mode_changed = pyqtSignal(bool)
    pip_geometry_live_changed = pyqtSignal(str)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._time = 0.0
        self._playing = False
        self._token = 0
        self._rendered_token = 0
        self._pending = False
        self._last_req_time = 0.0
        self._pixmap: QPixmap | None = None
        self._audio_clip_id: str | None = None
        self._pip_edit_mode: bool = False
        self._pip_drag: dict | None = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)

        self.setMinimumSize(320, 200)
        self.setMouseTracking(True)
        self._emitter_sig = _emitter.frame_ready
        self._emitter_sig.connect(self._on_frame)
        self.controller.timeline_changed.connect(self._on_timeline_updated)
        self.controller.selection_changed.connect(lambda _ids: self.update())

    def _on_timeline_updated(self):
        cap = self.controller.project.duration()
        if cap > 0 and self._time > cap:
            self._time = cap
        self._request_frame(force=True)
        if self._playing:
            self._sync_audio(self._time, force=True)
        else:
            self._audio_clip_id = None
        self.update()

    def retranslate(self):
        self.update()

    # ---------------- API ----------------
    def set_time(self, t: float, notify: bool = True):
        cap = self.controller.project.duration()
        t = max(0.0, min(t, cap if cap > 0 else 1e3))
        if abs(t - self._time) < 1e-5:
            return
        self._time = t
        self._request_frame()
        self.update()
        if notify:
            self.time_changed.emit(t)

    def play(self):
        if self._playing:
            return
        if self.controller.project.duration() <= 0:
            return
        self._playing = True
        fps = self.controller.project.fps or 30.0
        self._timer.start(max(1, int(1000 / max(fps, 1.0))))
        self._sync_audio(self._time, force=True)
        self.play_state_changed.emit(True)

    def pause(self):
        if not self._playing:
            return
        self._playing = False
        self._timer.stop()
        self._player.pause()
        self.play_state_changed.emit(False)

    def stop(self):
        self._playing = False
        self._timer.stop()
        self._player.stop()
        self._audio_clip_id = None
        self.play_state_changed.emit(False)
        self.set_time(self._time)

    def is_playing(self) -> bool:
        return self._playing

    def current_time(self) -> float:
        return self._time

    # ---------------- playback loop ----------------
    def _tick(self):
        if not self._playing:
            return
        project = self.controller.project
        fps = project.fps or 30.0
        duration = project.duration()
        nt = self._time + 1.0 / fps
        if duration > 0 and nt >= duration:
            nt = duration
            self._time = nt
            self._request_frame(force=True)
            self.update()
            self.time_changed.emit(nt)
            self.pause()
            return
        self._time = nt
        self._request_frame()
        self._sync_audio(nt)
        self.update()
        self.time_changed.emit(nt)

    # ---------------- frame decoding ----------------
    def _target_size(self) -> tuple[int, int]:
        project = self.controller.project
        if project.width and project.height:
            pw, ph = project.width, project.height
            scale = min(1.0, MAX_PREVIEW_WIDTH / pw)
            return max(int(pw * scale) & ~1, 2), max(int(ph * scale) & ~1, 2)
        return 1280, 720

    def _request_frame(self, force: bool = False):
        import time
        now = time.time()
        if self._pending and not force:
            if getattr(self, "_last_req_time", 0) and (now - self._last_req_time) > 0.3:
                self._pending = False
            else:
                return
        self._last_req_time = now
        project = self.controller.project
        active_video_clips = []
        for c in project.video_clips_at(self._time):
            m = project.clip_media(c)
            if m and m.has_video:
                active_video_clips.append((c, m))

        if not active_video_clips:
            self._pixmap = None
            self._pending = False
            self.update()
            return

        base_clip, base_media = active_video_clips[0]
        base_speed = getattr(base_clip, "speed", 1.0)
        base_src_time = base_clip.trim_in + (self._time - base_clip.position) * base_speed

        overlay_info = []
        for o_clip, o_media in active_video_clips[1:]:
            o_speed = getattr(o_clip, "speed", 1.0)
            o_src_time = o_clip.trim_in + (self._time - o_clip.position) * o_speed
            overlay_info.append((o_clip, o_media, o_src_time))

        self._token += 1
        w, h = self._target_size()
        if not (w and h):
            self._pending = False
            return
        self._pending = True
        from PyQt6.QtCore import QThreadPool
        QThreadPool.globalInstance().start(
            _DecodeJob(
                self._token, base_media.path, base_src_time, (w, h),
                clip=base_clip, timeline_time=self._time,
                is_image=base_media.is_image, has_alpha=base_media.has_alpha,
                overlay_info=overlay_info
            )
        )

    @pyqtSlot(int, float, QImage)
    def _on_frame(self, token: int, t: float, img: QImage):
        self._pending = False
        if token < self._rendered_token:
            return
        self._rendered_token = token
        if img is not None and not img.isNull():
            self._pixmap = QPixmap.fromImage(img)
            self.update()
        if self._playing or token < self._token:
            self._request_frame()

    # ---------------- audio monitor ----------------
    def _sync_audio(self, t: float, force: bool = False):
        project = self.controller.project
        clip = project.active_clip_at("audio", t)
        if clip is None:
            for vclip in project.video_clips_at(t):
                vmedia = project.clip_media(vclip)
                if vmedia and vmedia.has_audio:
                    clip = vclip
                    break

        if clip is None:
            if self._audio_clip_id is not None or force:
                self._player.stop()
                self._audio_clip_id = None
            return
        media = project.clip_media(clip)
        new_id = clip.id if (media and media.has_audio) else None
        clip_switched = self._audio_clip_id != new_id
        if clip_switched or force:
            self._audio_clip_id = new_id
            if new_id is None:
                self._player.stop()
                return
            file_url = QUrl.fromLocalFile(media.path)
            if self._player.source() != file_url:
                self._player.setSource(file_url)
            self._audio_output.setVolume(max(0.0, min(1.0, float(clip.volume))))
        speed = getattr(clip, "speed", 1.0)
        self._player.setPlaybackRate(speed)
        src_ms = int((clip.trim_in + (t - clip.position) * speed) * 1000)
        if self._player.playbackState() != self._player.PlaybackState.PlayingState:
            self._player.play()
            self._player.setPosition(src_ms)
        elif clip_switched or force or abs(self._player.position() - src_ms) > 250:
            self._player.setPosition(src_ms)

    # ---------------- painting ----------------
    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(10, 10, 12))
        cw, ch = self.width(), self.height()
        if self._pixmap is not None and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                QSize(cw, ch),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            x = (cw - scaled.width()) // 2
            y = (ch - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        else:
            self._draw_placeholder(p)
        self._draw_subtitles(p)
        self._draw_overlay(p)
        p.end()

    def _draw_subtitles(self, p: QPainter):
        active_subs = self.controller.project.subtitles_at(self._time)
        if not active_subs:
            return
        cw, ch = self.width(), self.height()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        for sub in active_subs:
            effect = getattr(sub, "animation_effect", "none")
            anim_dur = getattr(sub, "animation_duration", 0.5)

            elapsed = self._time - sub.position
            remaining = sub.end - self._time

            # Typewriter text content calculation
            raw_text = sub.text
            if effect == "typewriter":
                total_chars = len(raw_text)
                type_dur = max(0.1, min(sub.duration * 0.8, total_chars * 0.08, anim_dur * 2))
                if elapsed < type_dur and total_chars > 0:
                    ratio = min(1.0, max(0.0, elapsed / type_dur))
                    char_count = int(total_chars * ratio)
                    display_text = raw_text[:char_count]
                    if char_count < total_chars and (int(elapsed * 4) % 2 == 0):
                        display_text += "|"
                else:
                    display_text = raw_text
            else:
                display_text = raw_text

            font_size = max(12, int(sub.font_size * (ch / 720.0)))
            font = QFont(sub.font_family, font_size, QFont.Weight.Bold)
            p.setFont(font)
            fm = p.fontMetrics()

            lines = display_text.splitlines() or [""]
            text_w = max((fm.horizontalAdvance(line) for line in lines), default=100)
            line_h = fm.height()
            text_h = line_h * len(lines)

            # Determine layout offset and opacity for fly / fade
            y_offset = 0.0
            opacity = 1.0

            if effect == "fade":
                if anim_dur > 0:
                    in_ratio = min(1.0, max(0.0, elapsed / anim_dur))
                    out_ratio = min(1.0, max(0.0, remaining / anim_dur))
                    opacity = min(in_ratio, out_ratio)
            elif effect == "fly":
                if anim_dur > 0:
                    p_in = min(1.0, max(0.0, elapsed / anim_dur))
                    p_out = min(1.0, max(0.0, remaining / anim_dur))
                    ease_in = p_in * (2.0 - p_in)
                    ease_out = p_out * (2.0 - p_out)
                    y_offset = (1.0 - ease_in) * (ch * 0.12) + (1.0 - ease_out) * (ch * 0.12)
                    opacity = min(p_in, p_out)

            if effect == "typewriter" and anim_dur > 0 and remaining < anim_dur:
                opacity = min(opacity, max(0.0, remaining / anim_dur))

            margin_x, margin_y = 20, int(ch * 0.08)
            if sub.alignment == "top_center":
                x = (cw - text_w) // 2
                y = int(margin_y + y_offset)
            elif sub.alignment == "center":
                x = (cw - text_w) // 2
                y = int((ch - text_h) // 2 + y_offset)
            elif sub.alignment == "bottom_left":
                x = margin_x
                y = int(ch - margin_y - text_h + y_offset)
            elif sub.alignment == "bottom_right":
                x = cw - margin_x - text_w
                y = int(ch - margin_y - text_h + y_offset)
            else: # bottom_center
                x = (cw - text_w) // 2
                y = int(ch - margin_y - text_h + y_offset)

            if sub.bg_color:
                pad = 8
                bg_rect = QRectF(x - pad, y - pad, text_w + 2 * pad, text_h + 2 * pad)
                bg_c = QColor(sub.bg_color)
                if bg_c.isValid():
                    bg_c.setAlphaF(bg_c.alphaF() * opacity)
                    p.fillRect(bg_rect, bg_c)

            if sub.stroke_width > 0:
                stroke_c = QColor(sub.stroke_color)
                if stroke_c.isValid():
                    stroke_c.setAlphaF(stroke_c.alphaF() * opacity)
                    p.setPen(QPen(stroke_c, sub.stroke_width))
                    for idx, line in enumerate(lines):
                        ly = y + (idx + 1) * line_h - fm.descent()
                        p.drawText(x, ly, line)

            font_c = QColor(sub.font_color)
            font_c.setAlphaF(font_c.alphaF() * opacity)
            p.setPen(font_c)
            for idx, line in enumerate(lines):
                ly = y + (idx + 1) * line_h - fm.descent()
                p.drawText(x, ly, line)

    def _draw_placeholder(self, p: QPainter):
        p.setPen(QColor(70, 70, 78))
        font = QFont("Menlo", 11)
        p.setFont(font)
        msg = tr("No video at playhead")
        fm = p.fontMetrics()
        p.drawText(self.width() // 2 - fm.horizontalAdvance(msg) // 2,
                   self.height() // 2, msg)

    def _draw_overlay(self, p: QPainter):
        p.setPen(QColor(225, 225, 228, 220))
        p.setFont(QFont("Menlo", 10))
        timecode = fmt_timecode(self._time, self.controller.project.fps, compact=True)
        p.drawText(8, self.height() - 10, timecode)
        if self._playing:
            p.setPen(QColor(235, 90, 90))
            p.drawText(8, 18, tr("PLAYING"))

        # Chroma Key status overlay
        active_clips = self.controller.project.video_clips_at(self._time)
        ck_clip = next((c for c in active_clips if getattr(c, "chroma_key_enabled", False)), None)
        if ck_clip:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            if self._pending:
                msg = f"⏳ {tr('Applying Chroma Key...')}"
                bg_col = QColor(140, 80, 20, 210)
            else:
                msg = f"💚 {tr('Chroma Key Enabled')}: {ck_clip.chroma_key_color} ({tr('Similarity')}: {ck_clip.chroma_key_similarity:.2f})"
                bg_col = QColor(20, 110, 50, 210)

            font = QFont("Helvetica", 9, QFont.Weight.Bold)
            p.setFont(font)
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(msg)
            th = fm.height()

            rx = self.width() - tw - 24
            ry = 10
            p.fillRect(QRectF(rx, ry, tw + 16, th + 8), bg_col)
            p.setPen(QPen(QColor(255, 255, 255)))
            p.drawText(QRectF(rx + 8, ry + 4, tw, th), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, msg)

        dur = self.controller.project.duration()
        if dur > 0:
            p.drawText(self.width() - 90, self.height() - 10,
                       fmt_timecode(dur, self.controller.project.fps, compact=True))

        # Picture-in-Picture (PiP) interactive bounding boxes & handles
        if not getattr(self, "_eraser_mode", False):
            self._draw_pip_overlay(p)

        # Magic Eraser brush overlay
        if getattr(self, "_eraser_mode", False):
            self._draw_eraser_overlay(p)

    def set_pip_edit_mode(self, enabled: bool):
        if self._pip_edit_mode == enabled:
            return
        self._pip_edit_mode = enabled
        if enabled and getattr(self, "_eraser_mode", False):
            self._eraser_mode = False
        self.setMouseTracking(True)
        self.pip_mode_changed.emit(enabled)
        self.update()

    def is_pip_edit_mode(self) -> bool:
        return self._pip_edit_mode

    def _video_viewport_rect(self) -> tuple[float, float, float, float]:
        cw, ch = self.width(), self.height()
        pw = self.controller.project.width or 1920
        ph = self.controller.project.height or 1080
        scale = min(cw / max(pw, 1), ch / max(ph, 1))
        vw, vh = pw * scale, ph * scale
        vx0, vy0 = (cw - vw) * 0.5, (ch - vh) * 0.5
        return vx0, vy0, max(vw, 1.0), max(vh, 1.0)

    def _clip_screen_rect(self, clip) -> QRectF:
        vx0, vy0, vw, vh = self._video_viewport_rect()
        px = float(getattr(clip, "pip_x", 0.0))
        py = float(getattr(clip, "pip_y", 0.0))
        pw = float(getattr(clip, "pip_w", 1.0))
        ph = float(getattr(clip, "pip_h", 1.0))
        return QRectF(vx0 + px * vw, vy0 + py * vh, pw * vw, ph * vh)

    @staticmethod
    def _pip_handles_for_rect(r: QRectF, hs: float = 9.0) -> dict[str, QRectF]:
        hh = hs * 0.5
        x0, y0, w, h = r.x(), r.y(), r.width(), r.height()
        xm, ym = x0 + w * 0.5, y0 + h * 0.5
        x1, y1 = x0 + w, y0 + h
        return {
            "nw": QRectF(x0 - hh, y0 - hh, hs, hs),
            "n":  QRectF(xm - hh, y0 - hh, hs, hs),
            "ne": QRectF(x1 - hh, y0 - hh, hs, hs),
            "e":  QRectF(x1 - hh, ym - hh, hs, hs),
            "se": QRectF(x1 - hh, y1 - hh, hs, hs),
            "s":  QRectF(xm - hh, y1 - hh, hs, hs),
            "sw": QRectF(x0 - hh, y1 - hh, hs, hs),
            "w":  QRectF(x0 - hh, ym - hh, hs, hs),
        }

    def _is_pip_interactive(self, active_clips: list) -> bool:
        if self._pip_edit_mode:
            return True
        if len(active_clips) > 1:
            return True
        return any(getattr(c, "has_custom_pip", False) or c.track_index > 0 for c in active_clips)

    def _draw_pip_overlay(self, p: QPainter):
        active_clips = [
            c for c in self.controller.project.video_clips_at(self._time)
            if self.controller.project.clip_media(c) and self.controller.project.clip_media(c).has_video
        ]
        if not active_clips or not self._is_pip_interactive(active_clips):
            return

        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected_ids = set(self.controller._selected)
        active_selected = next((c for c in reversed(active_clips) if c.id in selected_ids), None)
        if active_selected is None:
            active_selected = active_clips[-1]

        for c in active_clips:
            is_sel = (c.id == active_selected.id)
            if not self._pip_edit_mode and not is_sel and not getattr(c, "has_custom_pip", False) and c.track_index == 0:
                continue

            rect = self._clip_screen_rect(c)
            role_label = tr("Main Screen") if c.track_index == 0 else tr("Sub Screen")
            track_tag = f"V{c.track_index + 1}"
            w_pct = int(round(getattr(c, "pip_w", 1.0) * 100))
            h_pct = int(round(getattr(c, "pip_h", 1.0) * 100))
            badge_text = f"{role_label} ({track_tag}) {w_pct}%×{h_pct}%"

            if is_sel:
                pen = QPen(QColor(0, 229, 255, 235), 2.0, Qt.PenStyle.SolidLine)
                badge_bg = QColor(0, 150, 190, 220)
            else:
                pen = QPen(QColor(255, 175, 40, 185), 1.5, Qt.PenStyle.DashLine)
                badge_bg = QColor(160, 100, 20, 200)

            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(pen)
            p.drawRect(rect)

            font = QFont("Helvetica", 8, QFont.Weight.Bold)
            p.setFont(font)
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(badge_text)
            th = fm.height()
            bx = max(4.0, min(rect.x() + 4.0, self.width() - tw - 16.0))
            by = max(4.0, min(rect.y() + 4.0, self.height() - th - 10.0))
            p.fillRect(QRectF(bx, by, tw + 10, th + 4), badge_bg)
            p.setPen(QColor(255, 255, 255))
            p.drawText(QRectF(bx + 5, by + 2, tw, th), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, badge_text)

            if is_sel:
                handles = self._pip_handles_for_rect(rect)
                p.setBrush(QBrush(QColor(0, 229, 255)))
                p.setPen(QPen(QColor(15, 20, 25), 1.2))
                for hrect in handles.values():
                    p.drawRect(hrect)

        if self._pip_edit_mode:
            hint = f"🖼️ {tr('PiP Edit Mode: Drag frame to move, drag corners/edges to resize, click to switch Main/Sub screen')}"
            p.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(hint)
            p.fillRect(QRectF(10, 10, tw + 16, 24), QColor(20, 110, 150, 220))
            p.setPen(QColor(255, 255, 255))
            p.drawText(QRectF(18, 12, tw, 20), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, hint)

    def set_eraser_mode(self, enabled: bool, radius: int = 25):
        self._eraser_mode = enabled
        if enabled and self._pip_edit_mode:
            self._pip_edit_mode = False
            self.pip_mode_changed.emit(False)
        self._brush_radius = radius
        self.setMouseTracking(True)
        self.update()

    def mousePressEvent(self, e):
        if getattr(self, "_eraser_mode", False) and e.button() == Qt.MouseButton.LeftButton:
            self._apply_eraser_stroke(e.position())
            return

        if e.button() == Qt.MouseButton.LeftButton:
            active_clips = [
                c for c in self.controller.project.video_clips_at(self._time)
                if self.controller.project.clip_media(c) and self.controller.project.clip_media(c).has_video
            ]
            if active_clips and self._is_pip_interactive(active_clips):
                pos = e.position()
                selected_ids = set(self.controller._selected)
                active_selected = next((c for c in reversed(active_clips) if c.id in selected_ids), active_clips[-1])

                # 1. Check resize handles on active_selected clip first
                if active_selected is not None:
                    s_rect = self._clip_screen_rect(active_selected)
                    for h_name, h_rect in self._pip_handles_for_rect(s_rect, hs=12.0).items():
                        if h_rect.contains(pos):
                            self.controller.set_selection([active_selected.id])
                            self._pip_drag = {
                                "clip_id": active_selected.id,
                                "mode": h_name,
                                "start_pos": pos,
                                "orig": (
                                    float(getattr(active_selected, "pip_x", 0.0)),
                                    float(getattr(active_selected, "pip_y", 0.0)),
                                    float(getattr(active_selected, "pip_w", 1.0)),
                                    float(getattr(active_selected, "pip_h", 1.0)),
                                ),
                            }
                            self.update()
                            return

                # 2. If active_selected is clicked inside, or check topmost clip containing pos
                hit_clip = None
                for c in reversed(active_clips):
                    if self._clip_screen_rect(c).contains(pos):
                        hit_clip = c
                        break

                if hit_clip is not None:
                    self.controller.set_selection([hit_clip.id])
                    # Also check if a handle on hit_clip was clicked
                    h_mode = "move"
                    for h_name, h_rect in self._pip_handles_for_rect(self._clip_screen_rect(hit_clip), hs=12.0).items():
                        if h_rect.contains(pos):
                            h_mode = h_name
                            break
                    self._pip_drag = {
                        "clip_id": hit_clip.id,
                        "mode": h_mode,
                        "start_pos": pos,
                        "orig": (
                            float(getattr(hit_clip, "pip_x", 0.0)),
                            float(getattr(hit_clip, "pip_y", 0.0)),
                            float(getattr(hit_clip, "pip_w", 1.0)),
                            float(getattr(hit_clip, "pip_h", 1.0)),
                        ),
                    }
                    self.update()
                    return

    def mouseMoveEvent(self, e):
        if getattr(self, "_eraser_mode", False):
            self._mouse_pos = e.position()
            if e.buttons() & Qt.MouseButton.LeftButton:
                self._apply_eraser_stroke(e.position())
            self.update()
            return

        if self._pip_drag is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            c = self.controller.project.clip_by_id(self._pip_drag["clip_id"])
            if c is None:
                self._pip_drag = None
                return
            _, _, vw, vh = self._video_viewport_rect()
            dx = (e.position().x() - self._pip_drag["start_pos"].x()) / vw
            dy = (e.position().y() - self._pip_drag["start_pos"].y()) / vh
            ox, oy, ow, oh = self._pip_drag["orig"]
            mode = self._pip_drag["mode"]
            nx, ny, nw, nh = ox, oy, ow, oh
            min_s = 0.08

            if mode == "move":
                nx = max(-0.9, min(0.98, ox + dx))
                ny = max(-0.9, min(0.98, oy + dy))
            else:
                if "e" in mode:
                    nw = max(min_s, min(2.0, ow + dx))
                if "s" in mode:
                    nh = max(min_s, min(2.0, oh + dy))
                if "w" in mode:
                    max_dx = ow - min_s
                    clamped_dx = min(dx, max_dx)
                    nx = ox + clamped_dx
                    nw = max(min_s, ow - clamped_dx)
                if "n" in mode:
                    max_dy = oh - min_s
                    clamped_dy = min(dy, max_dy)
                    ny = oy + clamped_dy
                    nh = max(min_s, oh - clamped_dy)

            c.pip_x, c.pip_y, c.pip_w, c.pip_h = nx, ny, nw, nh
            self._request_frame(force=True)
            self.pip_geometry_live_changed.emit(c.id)
            self.update()

    def mouseReleaseEvent(self, e):
        if self._pip_drag is not None and e.button() == Qt.MouseButton.LeftButton:
            drag = self._pip_drag
            self._pip_drag = None
            c = self.controller.project.clip_by_id(drag["clip_id"])
            if c is not None:
                nx, ny, nw, nh = c.pip_x, c.pip_y, c.pip_w, c.pip_h
                ox, oy, ow, oh = drag["orig"]
                # Restore original before pushing undo command so undo works cleanly
                c.pip_x, c.pip_y, c.pip_w, c.pip_h = ox, oy, ow, oh
                if any(abs(a - b) > 1e-4 for a, b in zip((nx, ny, nw, nh), (ox, oy, ow, oh))):
                    self.controller.set_clip_pip_geometry(
                        c.id, pip_x=nx, pip_y=ny, pip_w=nw, pip_h=nh
                    )
            self.update()

    def _apply_eraser_stroke(self, pos):
        clips = self.controller.project.video_clips_at(self._time)
        if not clips:
            return
        c = clips[0]
        cw, ch = self.width(), self.height()
        if self._pixmap is None or self._pixmap.isNull():
            return

        pw, ph = self.controller.project.width or 1920, self.controller.project.height or 1080
        scale = min(cw / pw, ch / ph)
        vw, vh = int(pw * scale), int(ph * scale)
        vx0, vy0 = (cw - vw) // 2, (ch - vh) // 2

        mx, my = pos.x(), pos.y()
        if vx0 <= mx <= vx0 + vw and vy0 <= my <= vy0 + vh:
            x_norm = (mx - vx0) / vw
            y_norm = (my - vy0) / vh
            r_norm = max(0.01, float(getattr(self, "_brush_radius", 25)) / min(vw, vh))
            self.controller.add_object_removal_mask(
                c.id, {"x": x_norm, "y": y_norm, "radius": r_norm}
            )
            self._request_frame(force=True)

    def _draw_eraser_overlay(self, p: QPainter):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cw, ch = self.width(), self.height()
        pw, ph = self.controller.project.width or 1920, self.controller.project.height or 1080
        scale = min(cw / pw, ch / ph)
        vw, vh = int(pw * scale), int(ph * scale)
        vx0, vy0 = (cw - vw) // 2, (ch - vh) // 2

        active_clips = self.controller.project.video_clips_at(self._time)
        c = active_clips[0] if active_clips else None

        # Draw existing masks as red semi-transparent highlight circles
        if c and getattr(c, "object_removal_masks", None):
            p.setBrush(QBrush(QColor(255, 50, 50, 110)))
            p.setPen(QPen(QColor(255, 80, 80, 200), 1.5))
            masks = c.object_removal_masks
            step = max(1, len(masks) // 60)
            for m in masks[::step]:
                cx = vx0 + int(m.get("x", 0.5) * vw)
                cy = vy0 + int(m.get("y", 0.5) * vh)
                r = max(4, int(m.get("radius", 0.05) * min(vw, vh)))
                p.drawEllipse(QRectF(float(cx - r), float(cy - r), float(r * 2), float(r * 2)))

        # Draw active brush circle at mouse position
        mpos = getattr(self, "_mouse_pos", None)
        if mpos:
            r = float(getattr(self, "_brush_radius", 25))
            p.setBrush(QBrush(QColor(255, 220, 0, 70)))
            p.setPen(QPen(QColor(255, 230, 0, 230), 2, Qt.PenStyle.DashLine))
            p.drawEllipse(QRectF(mpos.x() - r, mpos.y() - r, r * 2, r * 2))

        # Status badge at top left
        msg = f"🪄 {tr('Magic Eraser Active')} ({len(c.object_removal_masks) if c and getattr(c, 'object_removal_masks', None) else 0} {tr('masks')})"
        p.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(msg)
        p.fillRect(QRectF(10, 10, tw + 16, 24), QColor(180, 40, 40, 220))
        p.setPen(QPen(QColor(255, 255, 255)))
        p.drawText(QRectF(18, 12, tw, 20), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, msg)