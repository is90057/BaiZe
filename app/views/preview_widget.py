from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, QRectF, QTimer, QObject, QRunnable, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtGui import QImage, QPainter, QColor, QPen, QFont, QPixmap, QBrush
from PyQt6.QtWidgets import QWidget

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

    @pyqtSlot()
    def run(self):
        arr = None
        try:
            is_base_ck = getattr(self.clip, "chroma_key_enabled", False)
            if self.has_alpha or self.is_image or is_base_ck:
                rgba = fx.decode_frame_rgba(self.path, self.src_time, self.w, self.h, is_image=self.is_image)
                if is_base_ck:
                    rgba = fx.apply_chroma_key(
                        rgba, self.clip.chroma_key_color,
                        self.clip.chroma_key_similarity, self.clip.chroma_key_smoothness
                    )
                base_rgb = np.zeros((self.h, self.w, 3), dtype=np.uint8)
                op = self.clip.opacity if self.clip else 1.0
                arr = fx.composite_alpha(base_rgb, rgba, opacity=op)
            else:
                arr = fx.decode_frame(self.path, self.src_time, self.w, self.h)

            if arr is not None and self.clip is not None:
                br = getattr(self.clip, "brightness", 0.0)
                ct = getattr(self.clip, "contrast", 1.0)
                sat = getattr(self.clip, "saturation", 1.0)
                if abs(br) > 1e-4 or abs(ct - 1.0) > 1e-4 or abs(sat - 1.0) > 1e-4:
                    arr = fx.process_color_correction(arr, br, ct, sat)

                fm = getattr(self.clip, "focus_mode", "none")
                ba = getattr(self.clip, "blur_amount", 0.0)
                if fm != "none" or ba > 0:
                    arr = fx.process_blur_focus(arr, fm, ba)

                base_fx = getattr(self.clip, "video_fx", "none")
                if base_fx != "none":
                    arr = fx.process_video_effect(arr, base_fx, current_time=self.timeline_time)

                if getattr(self.clip, "object_removal_enabled", False):
                    masks = getattr(self.clip, "object_removal_masks", [])
                    if masks:
                        arr = fx.apply_object_removal_inpainting(arr, masks)

                arr = fx.process_frame_transition(arr, self.clip, self.timeline_time)

            if arr is not None and self.overlay_info:
                for o_clip, o_media, o_src_time in self.overlay_info:
                    is_o_ck = getattr(o_clip, "chroma_key_enabled", False)
                    if o_media.has_alpha or o_media.is_image or is_o_ck:
                        o_rgba = fx.decode_frame_rgba(o_media.path, o_src_time, self.w, self.h, is_image=o_media.is_image)
                        if is_o_ck:
                            o_rgba = fx.apply_chroma_key(
                                o_rgba, o_clip.chroma_key_color,
                                o_clip.chroma_key_similarity, o_clip.chroma_key_smoothness
                            )
                        o_br = getattr(o_clip, "brightness", 0.0)
                        o_ct = getattr(o_clip, "contrast", 1.0)
                        o_sat = getattr(o_clip, "saturation", 1.0)
                        if abs(o_br) > 1e-4 or abs(o_ct - 1.0) > 1e-4 or abs(o_sat - 1.0) > 1e-4:
                            o_rgba = fx.process_color_correction(o_rgba, o_br, o_ct, o_sat)
                        o_fm = getattr(o_clip, "focus_mode", "none")
                        o_ba = getattr(o_clip, "blur_amount", 0.0)
                        if o_fm != "none" or o_ba > 0:
                            o_rgba = fx.process_blur_focus(o_rgba, o_fm, o_ba)
                        o_fx = getattr(o_clip, "video_fx", "none")
                        if o_fx != "none":
                            o_rgba = fx.process_video_effect(o_rgba, o_fx, current_time=self.timeline_time)
                        if getattr(o_clip, "object_removal_enabled", False):
                            o_masks = getattr(o_clip, "object_removal_masks", [])
                            if o_masks:
                                o_rgba = fx.apply_object_removal_inpainting(o_rgba, o_masks)
                        arr = fx.composite_alpha(arr, o_rgba, opacity=o_clip.opacity)
                    else:
                        o_rgb = fx.decode_frame(o_media.path, o_src_time, self.w, self.h)
                        if o_rgb is not None:
                            o_br = getattr(o_clip, "brightness", 0.0)
                            o_ct = getattr(o_clip, "contrast", 1.0)
                            o_sat = getattr(o_clip, "saturation", 1.0)
                            if abs(o_br) > 1e-4 or abs(o_ct - 1.0) > 1e-4 or abs(o_sat - 1.0) > 1e-4:
                                o_rgb = fx.process_color_correction(o_rgb, o_br, o_ct, o_sat)
                            o_fm = getattr(o_clip, "focus_mode", "none")
                            o_ba = getattr(o_clip, "blur_amount", 0.0)
                            if o_fm != "none" or o_ba > 0:
                                o_rgb = fx.process_blur_focus(o_rgb, o_fm, o_ba)
                            o_fx = getattr(o_clip, "video_fx", "none")
                            if o_fx != "none":
                                o_rgb = fx.process_video_effect(o_rgb, o_fx, current_time=self.timeline_time)
                            if getattr(o_clip, "object_removal_enabled", False):
                                o_masks = getattr(o_clip, "object_removal_masks", [])
                                if o_masks:
                                    o_rgb = fx.apply_object_removal_inpainting(o_rgb, o_masks)
                            o_rgba = np.dstack([o_rgb, np.full((self.h, self.w), int(o_clip.opacity * 255), dtype=np.uint8)])
                            arr = fx.composite_alpha(arr, o_rgba, opacity=1.0)
        except Exception:
            arr = None
        finally:
            from PyQt6.QtWidgets import QApplication
            if QApplication.instance() is not None:
                img = QImage()
                if arr is not None and arr.size > 0:
                    import numpy as np
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

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)

        self.setMinimumSize(320, 200)
        self._emitter_sig = _emitter.frame_ready
        self._emitter_sig.connect(self._on_frame)

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
        if self._audio_clip_id != new_id or force:
            self._audio_clip_id = new_id
            if new_id is None:
                self._player.stop()
                return
            self._player.setSource(QUrl.fromLocalFile(media.path))
            self._audio_output.setVolume(max(0.0, min(1.0, float(clip.volume))))
        speed = getattr(clip, "speed", 1.0)
        self._player.setPlaybackRate(speed)
        src_ms = int((clip.trim_in + (t - clip.position) * speed) * 1000)
        if self._player.playbackState() != self._player.PlaybackState.PlayingState:
            self._player.play()
            self._player.setPosition(src_ms)
        elif abs(self._player.position() - src_ms) > 400:
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

        # Magic Eraser brush overlay
        if getattr(self, "_eraser_mode", False):
            self._draw_eraser_overlay(p)

    def set_eraser_mode(self, enabled: bool, radius: int = 25):
        self._eraser_mode = enabled
        self._brush_radius = radius
        self.setMouseTracking(enabled)
        self.update()

    def mousePressEvent(self, e):
        if getattr(self, "_eraser_mode", False) and e.button() == Qt.MouseButton.LeftButton:
            self._apply_eraser_stroke(e.position())

    def mouseMoveEvent(self, e):
        if getattr(self, "_eraser_mode", False):
            self._mouse_pos = e.position()
            if e.buttons() & Qt.MouseButton.LeftButton:
                self._apply_eraser_stroke(e.position())
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