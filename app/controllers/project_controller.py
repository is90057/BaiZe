from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QUndoStack, QUndoCommand

from ..models.media import MediaClip, TimelineClip, SubtitleClip, new_id
from ..models.project import Project


def _clone_clip(c: TimelineClip, **overrides) -> TimelineClip:
    masks = [dict(m) for m in getattr(c, "object_removal_masks", [])]
    return replace(c, object_removal_masks=masks, **overrides)


def _clone_subtitle(s: SubtitleClip, **overrides) -> SubtitleClip:
    return replace(s, **overrides)


class ProjectController(QObject):
    project_changed = pyqtSignal()
    timeline_changed = pyqtSignal()
    media_added = pyqtSignal(object)
    selection_changed = pyqtSignal(list)   # clip ids

    def __init__(self, project: Project | None = None, parent=None):
        super().__init__(parent)
        self.project = project or Project()
        self.undo_stack = QUndoStack(self)
        self.undo_stack.indexChanged.connect(self.timeline_changed)
        self._selected: list[str] = []

    # ---------- selection ----------
    def selected_clips(self) -> list[TimelineClip]:
        return [c for c in (self.project.clip_by_id(i) for i in self._selected) if c]

    def set_selection(self, clip_ids: list[str]):
        self._selected = clip_ids
        self.selection_changed.emit(clip_ids)

    def clear_selection(self):
        if self._selected:
            self._selected = []
            self.selection_changed.emit([])

    # ---------- media ----------
    def add_media(self, clips: list[MediaClip]):
        self.undo_stack.push(_AddMedia(self.project, clips))
        for m in clips:
            self.media_added.emit(m)

    def add_clip(self, media: MediaClip, kind: str, track_index: int, position: float):
        src_dur = media.duration
        c = TimelineClip(
            media_id=media.id, position=position, duration=src_dur,
            trim_in=0.0, track_index=track_index, name=media.name or media.filepath().stem,
        )
        self.undo_stack.push(_AddClip(self.project, c, kind))
        return c

    def move_clip(self, clip_id: str, new_position: float, new_track: int, kind: str):
        c = self.project.clip_by_id(clip_id)
        if c is None:
            return
        self.undo_stack.push(
            _MoveClip(self.project, clip_id, c.position, new_position,
                      c.track_index, new_track, kind))

    def trim_clip(self, clip_id: str, new_trim_in: float, new_duration: float, new_position: float | None = None):
        c = self.project.clip_by_id(clip_id)
        if c is None:
            return
        self.undo_stack.push(
            _TrimClip(self.project, clip_id, c.trim_in, c.duration,
                      new_trim_in, new_duration, c.position,
                      c.position if new_position is None else new_position))

    def remove_clip(self, clip_id: str, kind: str):
        c = self.project.clip_by_id(clip_id)
        if c is None:
            return
        self.undo_stack.push(_RemoveClip(self.project, clip_id, c.track_index, kind))

    def split_clip(self, clip_id: str, time: float, kind: str):
        c = self.project.clip_by_id(clip_id)
        if c is None or not (c.position + 1e-3 < time < c.end - 1e-3):
            return
        self.undo_stack.push(_SplitClip(self.project, clip_id, time, kind))

    def clip_kind(self, clip_id: str) -> str:
        for tr in self.project.video_tracks:
            if any(c.id == clip_id for c in tr.clips):
                return "video"
        return "audio"

    def find_linked_clips(self, clip_id: str) -> list[TimelineClip]:
        """Return [clip] plus any counterpart video/audio clips with same media_id and time span."""
        c = self.project.clip_by_id(clip_id)
        if c is None:
            return []
        kind = self.clip_kind(clip_id)
        other_tracks = self.project.audio_tracks if kind == "video" else self.project.video_tracks
        out = [c]
        for tr in other_tracks:
            for oc in tr.clips:
                if (oc.media_id == c.media_id
                        and abs(oc.position - c.position) < 0.05
                        and abs(oc.duration - c.duration) < 0.05):
                    out.append(oc)
        return out

    def split_at_time(self, time: float, clip_ids: list[str] | None = None) -> int:
        """Split targeted clips (and linked counterparts) or all clips covering `time`."""
        targets: list[tuple[TimelineClip, str]] = []
        seen: set[str] = set()
        if clip_ids:
            for cid in clip_ids:
                for lc in self.find_linked_clips(cid):
                    if lc.id not in seen and (lc.position + 1e-3 < time < lc.end - 1e-3):
                        seen.add(lc.id)
                        targets.append((lc, self.clip_kind(lc.id)))
        if not targets:
            for tr in self.project.all_tracks():
                if not tr.enabled:
                    continue
                for c in tr.clips:
                    if c.id not in seen and (c.position + 1e-3 < time < c.end - 1e-3):
                        seen.add(c.id)
                        targets.append((c, tr.kind))
        if not targets:
            return 0
        self.undo_stack.beginMacro("Split Clip")
        for c, kind in targets:
            self.undo_stack.push(_SplitClip(self.project, c.id, time, kind))
        self.undo_stack.endMacro()
        return len(targets)

    def cut_time_intervals(self, intervals: list[tuple[float, float]], ripple: bool = True) -> float:
        """Cut out one or more [t0, t1] time ranges across all video and audio tracks."""
        valid = sorted((max(0.0, float(a)), float(b)) for a, b in intervals if b - a > 1e-3)
        if not valid:
            return 0.0
        merged: list[tuple[float, float]] = []
        for a, b in valid:
            if merged and a <= merged[-1][1] + 1e-4:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        cmd = _CutIntervalsCommand(self.project, merged, ripple=ripple)
        if not cmd.has_changes:
            return 0.0
        self.undo_stack.push(cmd)
        self.set_selection([])
        return sum(b - a for a, b in merged)

    def cut_range(self, start_time: float, end_time: float, ripple: bool = True) -> float:
        return self.cut_time_intervals([(start_time, end_time)], ripple=ripple)

    def cut_selected_clips(self, ripple: bool = True) -> float:
        clips = self.selected_clips()
        if not clips:
            return 0.0
        intervals = [(c.position, c.end) for c in clips if c.duration > 1e-3]
        return self.cut_time_intervals(intervals, ripple=ripple)

    def set_clip_volume(self, clip_id: str, volume: float):
        self._set_clip_prop(clip_id, "volume", volume)

    def set_clip_opacity(self, clip_id: str, opacity: float):
        self._set_clip_prop(clip_id, "opacity", opacity)

    def set_clip_transition(
        self, clip_id: str,
        fade_in_dur: float | None = None, fade_in_type: str | None = None,
        fade_out_dur: float | None = None, fade_out_type: str | None = None,
    ):
        c = self.project.clip_by_id(clip_id)
        if c is None:
            return
        self.undo_stack.push(
            _SetTransition(self.project, clip_id,
                           fade_in_dur, fade_in_type,
                           fade_out_dur, fade_out_type))

    def set_clip_chroma_key(
        self, clip_id: str,
        enabled: bool | None = None,
        color: str | None = None,
        similarity: float | None = None,
        smoothness: float | None = None,
    ):
        c = self.project.clip_by_id(clip_id)
        if c is None:
            return
        self.undo_stack.push(
            _SetChromaKey(self.project, clip_id, enabled, color, similarity, smoothness)
        )

    def set_clip_video_fx(self, clip_id: str, fx_id: str):
        c = self.project.clip_by_id(clip_id)
        if c is None or getattr(c, "video_fx", "none") == fx_id:
            return
        self.undo_stack.push(_SetProp(self.project, clip_id, "video_fx", fx_id))

    def set_clip_speed(self, clip_id: str, speed: float):
        c = self.project.clip_by_id(clip_id)
        if c is None:
            return
        self.undo_stack.push(_SetProp(self.project, clip_id, "speed", max(0.1, min(speed, 10.0))))

    def set_clip_color_correction(
        self, clip_id: str,
        brightness: float | None = None,
        contrast: float | None = None,
        saturation: float | None = None,
    ):
        c = self.project.clip_by_id(clip_id)
        if c is None:
            return
        if brightness is not None:
            self.undo_stack.push(_SetProp(self.project, clip_id, "brightness", max(-1.0, min(brightness, 1.0))))
        if contrast is not None:
            self.undo_stack.push(_SetProp(self.project, clip_id, "contrast", max(0.1, min(contrast, 3.0))))
        if saturation is not None:
            self.undo_stack.push(_SetProp(self.project, clip_id, "saturation", max(0.0, min(saturation, 3.0))))

    def set_clip_blur_focus(
        self, clip_id: str,
        focus_mode: str | None = None,
        blur_amount: float | None = None,
    ):
        c = self.project.clip_by_id(clip_id)
        if c is None:
            return
        if focus_mode is not None:
            self.undo_stack.push(_SetProp(self.project, clip_id, "focus_mode", focus_mode))
        if blur_amount is not None:
            self.undo_stack.push(_SetProp(self.project, clip_id, "blur_amount", max(0.0, min(blur_amount, 20.0))))

    def rename_clip(self, clip_id: str, name: str):
        c = self.project.clip_by_id(clip_id)
        if c is None or c.name == name:
            return
        self.undo_stack.push(_SetProp(self.project, clip_id, "name", name))

    def _set_clip_prop(self, clip_id: str, attr: str, value: float):
        c = self.project.clip_by_id(clip_id)
        if c is None:
            return
        self.undo_stack.push(_SetProp(self.project, clip_id, attr, value))

    # ---------- Picture-in-Picture (PiP / 子母畫面) ----------
    def ensure_video_track(self, min_track_index: int = 1):
        while len(self.project.video_tracks) <= min_track_index:
            self.undo_stack.push(_AddVideoTrack(self.project))

    def set_clip_pip_geometry(
        self,
        clip_id: str,
        pip_x: float | None = None,
        pip_y: float | None = None,
        pip_w: float | None = None,
        pip_h: float | None = None,
        border_width: int | None = None,
        border_color: str | None = None,
    ):
        c = self.project.clip_by_id(clip_id)
        if c is None:
            return
        cmd = _SetPipGeometry(
            self.project, clip_id,
            pip_x=pip_x, pip_y=pip_y, pip_w=pip_w, pip_h=pip_h,
            border_width=border_width, border_color=border_color,
        )
        if cmd.has_changes:
            self.undo_stack.push(cmd)

    def add_pip_clip(self, media: MediaClip, position: float = 0.0, track_index: int = 1) -> TimelineClip:
        """Add a media asset as a Picture-in-Picture sub-screen on upper video track V2+."""
        self.undo_stack.beginMacro("Add PiP Clip")
        self.ensure_video_track(track_index)
        c = TimelineClip(
            media_id=media.id,
            position=max(0.0, position),
            duration=media.duration,
            trim_in=0.0,
            track_index=track_index,
            name=media.name or media.filepath().stem,
            pip_x=0.62,
            pip_y=0.60,
            pip_w=0.35,
            pip_h=0.35,
            pip_border_width=2,
            pip_border_color="#FFFFFF",
        )
        self.undo_stack.push(_AddClip(self.project, c, "video"))
        self.undo_stack.endMacro()
        self.set_selection([c.id])
        return c

    def set_clip_as_sub_screen(self, clip_id: str):
        """Move clip to upper video track V2+ and apply default sub-screen PiP size if full-screen."""
        c = self.project.clip_by_id(clip_id)
        if c is None or self.clip_kind(clip_id) != "video":
            return
        self.undo_stack.beginMacro("Set as Sub Screen")
        target_track = max(1, c.track_index)
        self.ensure_video_track(target_track)
        if c.track_index != target_track:
            self.undo_stack.push(
                _MoveClip(self.project, clip_id, c.position, c.position, c.track_index, target_track, "video")
            )
        if not getattr(c, "has_custom_pip", False):
            self.undo_stack.push(
                _SetPipGeometry(
                    self.project, clip_id,
                    pip_x=0.62, pip_y=0.60, pip_w=0.35, pip_h=0.35,
                    border_width=2, border_color=getattr(c, "pip_border_color", "#FFFFFF"),
                )
            )
        self.undo_stack.endMacro()
        self.timeline_changed.emit()

    def set_clip_as_main_screen(self, clip_id: str):
        """Move clip to base video track V1 and reset to full-screen main display."""
        c = self.project.clip_by_id(clip_id)
        if c is None or self.clip_kind(clip_id) != "video":
            return
        self.undo_stack.beginMacro("Set as Main Screen")
        if c.track_index != 0:
            self.undo_stack.push(
                _MoveClip(self.project, clip_id, c.position, c.position, c.track_index, 0, "video")
            )
        self.undo_stack.push(
            _SetPipGeometry(
                self.project, clip_id,
                pip_x=0.0, pip_y=0.0, pip_w=1.0, pip_h=1.0, border_width=0,
            )
        )
        self.undo_stack.endMacro()
        self.timeline_changed.emit()

    def find_pip_pair_at(self, time: float | None = None) -> tuple[TimelineClip | None, TimelineClip | None]:
        """Return (main_clip, sub_clip) at `time` or from current selection/timeline."""
        active: list[TimelineClip] = []
        if time is not None:
            active = self.project.video_clips_at(time)
        if len(active) >= 2:
            return active[0], active[-1]

        sel_video = [c for c in self.selected_clips() if self.clip_kind(c.id) == "video"]
        if len(sel_video) >= 2:
            sel_sorted = sorted(sel_video, key=lambda x: x.track_index)
            return sel_sorted[0], sel_sorted[-1]
        if len(sel_video) == 1:
            sc = sel_video[0]
            mid = sc.position + sc.duration * 0.5
            at_mid = self.project.video_clips_at(mid)
            if len(at_mid) >= 2:
                return at_mid[0], at_mid[-1]
            if sc.track_index > 0:
                return None, sc
            return sc, None

        if len(active) == 1:
            ac = active[0]
            if ac.track_index > 0:
                return None, ac
            return ac, None

        # Fallback: look for any overlapping pair across tracks
        if len(self.project.video_tracks) >= 2:
            base_clips = self.project.video_tracks[0].clips
            for upper_tr in reversed(self.project.video_tracks[1:]):
                for uc in upper_tr.clips:
                    mid = uc.position + uc.duration * 0.5
                    for bc in base_clips:
                        if bc.contains(mid):
                            return bc, uc
        return None, None

    def swap_pip_screens(self, time: float | None = None) -> bool:
        """Swap main screen (母畫面) and sub screen (子畫面) tracks and geometries."""
        main_c, sub_c = self.find_pip_pair_at(time)
        if main_c is None or sub_c is None or main_c.id == sub_c.id:
            return False

        m_geom = (
            getattr(main_c, "pip_x", 0.0),
            getattr(main_c, "pip_y", 0.0),
            getattr(main_c, "pip_w", 1.0),
            getattr(main_c, "pip_h", 1.0),
            getattr(main_c, "pip_border_width", 0),
            getattr(main_c, "pip_border_color", "#FFFFFF"),
        )
        s_geom = (
            getattr(sub_c, "pip_x", 0.62),
            getattr(sub_c, "pip_y", 0.60),
            getattr(sub_c, "pip_w", 0.35),
            getattr(sub_c, "pip_h", 0.35),
            getattr(sub_c, "pip_border_width", 2),
            getattr(sub_c, "pip_border_color", "#FFFFFF"),
        )
        m_track = main_c.track_index
        s_track = sub_c.track_index

        self.undo_stack.beginMacro("Swap Main and Sub Screens")
        if m_track != s_track:
            self.undo_stack.push(
                _MoveClip(self.project, main_c.id, main_c.position, main_c.position, m_track, s_track, "video")
            )
            self.undo_stack.push(
                _MoveClip(self.project, sub_c.id, sub_c.position, sub_c.position, s_track, m_track, "video")
            )
        self.undo_stack.push(
            _SetPipGeometry(
                self.project, main_c.id,
                pip_x=s_geom[0], pip_y=s_geom[1], pip_w=s_geom[2], pip_h=s_geom[3],
                border_width=s_geom[4], border_color=s_geom[5],
            )
        )
        self.undo_stack.push(
            _SetPipGeometry(
                self.project, sub_c.id,
                pip_x=m_geom[0], pip_y=m_geom[1], pip_w=m_geom[2], pip_h=m_geom[3],
                border_width=m_geom[4], border_color=m_geom[5],
            )
        )
        self.undo_stack.endMacro()
        self.timeline_changed.emit()
        return True

    def apply_pip_layout_preset(
        self,
        preset_id: str,
        time: float | None = None,
        target_clip_id: str | None = None,
    ) -> bool:
        """Apply a layout preset to both main screen (母畫面) and sub screen (子畫面)."""
        # Preset definitions: preset_id -> (main_box(x,y,w,h,bw), sub_box(x,y,w,h,bw))
        presets: dict[str, tuple[tuple[float, float, float, float, int], tuple[float, float, float, float, int]]] = {
            "pip_br": ((0.0, 0.0, 1.0, 1.0, 0), (0.62, 0.60, 0.35, 0.35, 2)),
            "pip_bl": ((0.0, 0.0, 1.0, 1.0, 0), (0.03, 0.60, 0.35, 0.35, 2)),
            "pip_tr": ((0.0, 0.0, 1.0, 1.0, 0), (0.62, 0.05, 0.35, 0.35, 2)),
            "pip_tl": ((0.0, 0.0, 1.0, 1.0, 0), (0.03, 0.05, 0.35, 0.35, 2)),
            "side_by_side": ((0.0, 0.0, 0.5, 1.0, 1), (0.5, 0.0, 0.5, 1.0, 1)),
            "side_by_side_swap": ((0.5, 0.0, 0.5, 1.0, 1), (0.0, 0.0, 0.5, 1.0, 1)),
            "main_left_70": ((0.0, 0.0, 0.70, 1.0, 1), (0.70, 0.20, 0.30, 0.60, 2)),
            "main_right_70": ((0.30, 0.0, 0.70, 1.0, 1), (0.0, 0.20, 0.30, 0.60, 2)),
            "top_bottom": ((0.0, 0.0, 1.0, 0.5, 1), (0.0, 0.5, 1.0, 0.5, 1)),
            "floating_dual": ((0.03, 0.05, 0.62, 0.62, 2), (0.42, 0.38, 0.55, 0.55, 2)),
            "reset_full": ((0.0, 0.0, 1.0, 1.0, 0), (0.0, 0.0, 1.0, 1.0, 0)),
        }
        if preset_id not in presets:
            return False

        main_box, sub_box = presets[preset_id]
        main_c, sub_c = self.find_pip_pair_at(time)
        target_c = self.project.clip_by_id(target_clip_id) if target_clip_id else None

        self.undo_stack.beginMacro(f"Apply PiP Layout {preset_id}")
        applied = False
        if main_c is not None and sub_c is not None:
            self.undo_stack.push(
                _SetPipGeometry(
                    self.project, main_c.id,
                    pip_x=main_box[0], pip_y=main_box[1], pip_w=main_box[2], pip_h=main_box[3],
                    border_width=main_box[4],
                )
            )
            self.undo_stack.push(
                _SetPipGeometry(
                    self.project, sub_c.id,
                    pip_x=sub_box[0], pip_y=sub_box[1], pip_w=sub_box[2], pip_h=sub_box[3],
                    border_width=sub_box[4],
                )
            )
            applied = True
        else:
            single = target_c or sub_c or main_c
            if single is not None and self.clip_kind(single.id) == "video":
                box = main_box if (preset_id == "reset_full") else (sub_box if single.track_index > 0 or preset_id.startswith("pip_") else main_box)
                self.undo_stack.push(
                    _SetPipGeometry(
                        self.project, single.id,
                        pip_x=box[0], pip_y=box[1], pip_w=box[2], pip_h=box[3],
                        border_width=box[4],
                    )
                )
                applied = True
        self.undo_stack.endMacro()
        if applied:
            self.timeline_changed.emit()
        return applied

    # ---------- subtitles ----------
    def add_subtitle(self, text: str, position: float, duration: float = 3.0) -> SubtitleClip:
        sub = SubtitleClip(text=text, position=position, duration=duration)
        self.undo_stack.push(_AddSubtitle(self.project, sub))
        return sub

    def remove_subtitle(self, sub_id: str):
        sub = self.project.subtitle_by_id(sub_id)
        if sub:
            self.undo_stack.push(_RemoveSubtitle(self.project, sub))

    def update_subtitle(self, sub_id: str, **kwargs):
        sub = self.project.subtitle_by_id(sub_id)
        if sub:
            self.undo_stack.push(_UpdateSubtitle(self.project, sub_id, kwargs))

    def import_srt(self, srt_path: str) -> int:
        with open(srt_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        parsed = parse_srt(content)
        if not parsed:
            return 0
        subs = [SubtitleClip(text=item["text"], position=item["position"], duration=item["duration"])
                for item in parsed]
        self.undo_stack.push(_ImportSRT(self.project, subs))
        return len(subs)

    def export_srt(self, srt_path: str):
        sorted_subs = sorted(self.project.subtitles, key=lambda s: s.position)
        lines = []
        for idx, s in enumerate(sorted_subs, 1):
            t_start = sec_to_srt_time(s.position)
            t_end = sec_to_srt_time(s.end)
            lines.append(f"{idx}\n{t_start} --> {t_end}\n{s.text}\n")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def add_auto_subtitles(self, subtitles: list[SubtitleClip]):
        if subtitles:
            self.undo_stack.push(_ImportAutoSubtitles(self.project, subtitles))

    def set_clip_object_removal(self, clip_id: str, enabled: bool | None = None, masks: list[dict] | None = None):
        self.undo_stack.push(_SetObjectRemoval(self.project, clip_id, enabled=enabled, masks=masks))

    def add_object_removal_mask(self, clip_id: str, mask: dict):
        c = self.project.clip_by_id(clip_id)
        if c:
            masks = list(getattr(c, "object_removal_masks", []))
            masks.append(mask)
            self.set_clip_object_removal(clip_id, enabled=True, masks=masks)

    def clear_object_removal_masks(self, clip_id: str):
        self.set_clip_object_removal(clip_id, enabled=False, masks=[])

    def track_clip_object_masks(self, clip_id: str):
        c = self.project.clip_by_id(clip_id)
        if not c:
            return
        media = self.project.clip_media(c)
        if not media or not media.path:
            return
        masks = getattr(c, "object_removal_masks", [])
        if not masks:
            return

        from ..core.ffmpeg import track_clip_object_masks
        tracked = track_clip_object_masks(
            media.path, masks, c.trim_in, c.duration
        )
        self.set_clip_object_removal(clip_id, enabled=True, masks=tracked)

    # ---------- save / load ----------
    def new_project(self, fps=30.0, width=1920, height=1080):
        self.project = Project(name="Untitled", fps=fps, width=width, height=height)
        self.undo_stack.clear()
        self.set_selection([])
        self.project_changed.emit()

    def load(self, project: Project):
        self.project = project
        self.undo_stack.clear()
        self.set_selection([])
        self.project_changed.emit()


def _track_of(project: Project, kind: str, idx: int):
    return project.track(kind, idx)


class _AddMedia(QUndoCommand):
    def __init__(self, project: Project, clips: list[MediaClip]):
        super().__init__("Import Media")
        self._project = project
        self._clips = clips

    def redo(self):
        self._project.media.extend(self._clips)

    def undo(self):
        ids = {c.id for c in self._clips}
        self._project.media = [m for m in self._project.media if m.id not in ids]


class _AddClip(QUndoCommand):
    def __init__(self, project: Project, clip: TimelineClip, kind: str):
        super().__init__("Add Clip")
        self._project = project
        self._clip = clip
        self._kind = kind

    def redo(self):
        track = _track_of(self._project, self._kind, self._clip.track_index)
        track.clips.append(self._clip)

    def undo(self):
        track = _track_of(self._project, self._kind, self._clip.track_index)
        track.clips = [c for c in track.clips if c.id != self._clip.id]


class _MoveClip(QUndoCommand):
    def __init__(self, project, clip_id, old_pos, new_pos, old_track, new_track, kind):
        super().__init__("Move Clip")
        self._p = project
        self._id = clip_id
        self._old_pos, self._new_pos = old_pos, new_pos
        self._old_track, self._new_track = old_track, new_track
        self._kind = kind

    def redo(self):
        self._apply(self._new_pos, self._new_track)

    def undo(self):
        self._apply(self._old_pos, self._old_track)

    def _apply(self, pos, track_idx):
        c = self._p.clip_by_id(self._id)
        if c is None:
            return
        old_tr = _track_of(self._p, self._kind, c.track_index)
        old_tr.clips = [x for x in old_tr.clips if x.id != self._id]
        c.position = max(pos, 0.0)
        c.track_index = track_idx
        new_tr = _track_of(self._p, self._kind, track_idx)
        new_tr.clips.append(c)


class _TrimClip(QUndoCommand):
    def __init__(self, project, clip_id, old_in, old_dur, new_in, new_dur, old_pos=None, new_pos=None):
        super().__init__("Trim Clip")
        self._p = project
        self._id = clip_id
        self._old_in, self._old_dur = old_in, old_dur
        self._new_in, self._new_dur = new_in, new_dur
        self._old_pos, self._new_pos = old_pos, new_pos

    def redo(self):
        self._apply(self._new_in, self._new_dur, self._new_pos)

    def undo(self):
        self._apply(self._old_in, self._old_dur, self._old_pos)

    def _apply(self, tin, dur, pos):
        c = self._p.clip_by_id(self._id)
        if c is None:
            return
        c.trim_in = max(tin, 0.0)
        c.duration = max(dur, 1e-3)
        if pos is not None:
            c.position = max(pos, 0.0)


class _RemoveClip(QUndoCommand):
    def __init__(self, project, clip_id, track_index, kind):
        super().__init__("Delete Clip")
        self._p = project
        self._id = clip_id
        self._track_index = track_index
        self._kind = kind
        self._clip: TimelineClip | None = None

    def redo(self):
        track = _track_of(self._p, self._kind, self._track_index)
        for i, c in enumerate(track.clips):
            if c.id == self._id:
                self._clip = c
                track.clips.pop(i)
                break

    def undo(self):
        if self._clip is None:
            return
        track = _track_of(self._p, self._kind, self._track_index)
        track.clips.append(self._clip)


class _SplitClip(QUndoCommand):
    def __init__(self, project, clip_id, time, kind):
        super().__init__("Split Clip")
        self._p = project
        self._id = clip_id
        self._time = time
        self._kind = kind
        self._orig: TimelineClip | None = None
        self._left: TimelineClip | None = None
        self._right: TimelineClip | None = None
        self._track_index = 0

    def redo(self):
        c = self._p.clip_by_id(self._id)
        if c is None:
            return
        if self._left is None:
            t = self._time
            self._orig = _clone_clip(c)
            self._track_index = c.track_index
            speed = getattr(c, "speed", 1.0)
            left_dur = t - c.position
            right_dur = c.end - t
            self._left = _clone_clip(
                c, duration=left_dur,
                fade_out_duration=0.0,
                fade_in_duration=min(getattr(c, "fade_in_duration", 0.0), left_dur),
                id=new_id())
            self._right = _clone_clip(
                c, position=t, duration=right_dur,
                trim_in=c.trim_in + left_dur * speed,
                fade_in_duration=0.0,
                fade_out_duration=min(getattr(c, "fade_out_duration", 0.0), right_dur),
                id=new_id())
        track = _track_of(self._p, self._kind, self._track_index)
        track.clips = [x for x in track.clips if x.id != self._id]
        track.clips.append(_clone_clip(self._left))
        track.clips.append(_clone_clip(self._right))

    def undo(self):
        if self._left is None or self._orig is None:
            return
        track = _track_of(self._p, self._kind, self._track_index)
        track.clips = [x for x in track.clips
                       if x.id not in (self._left.id, self._right.id)]
        track.clips.append(_clone_clip(self._orig))


class _CutIntervalsCommand(QUndoCommand):
    def __init__(self, project: Project, intervals: list[tuple[float, float]], ripple: bool = True):
        super().__init__("Cut Selected Segment")
        self._p = project
        self._before_video = [[_clone_clip(c) for c in tr.clips] for tr in project.video_tracks]
        self._before_audio = [[_clone_clip(c) for c in tr.clips] for tr in project.audio_tracks]
        self._before_subs = [_clone_subtitle(s) for s in project.subtitles]

        after_video = [[_clone_clip(c) for c in tr.clips] for tr in project.video_tracks]
        after_audio = [[_clone_clip(c) for c in tr.clips] for tr in project.audio_tracks]
        after_subs = [_clone_subtitle(s) for s in project.subtitles]

        changed = False
        for t0, t1 in sorted(intervals, key=lambda x: x[0], reverse=True):
            for idx, tr in enumerate(project.video_tracks):
                if tr.enabled:
                    new_clips, ch = self._cut_clips_list(after_video[idx], t0, t1, ripple)
                    after_video[idx] = new_clips
                    changed = changed or ch
            for idx, tr in enumerate(project.audio_tracks):
                if tr.enabled:
                    new_clips, ch = self._cut_clips_list(after_audio[idx], t0, t1, ripple)
                    after_audio[idx] = new_clips
                    changed = changed or ch
            after_subs, sub_ch = self._cut_subs_list(after_subs, t0, t1, ripple)
            changed = changed or sub_ch

        self._after_video = after_video
        self._after_audio = after_audio
        self._after_subs = after_subs
        self.has_changes = changed

    @staticmethod
    def _cut_clips_list(clips: list[TimelineClip], t0: float, t1: float, ripple: bool) -> tuple[list[TimelineClip], bool]:
        eps = 1e-4
        cut_dur = t1 - t0
        out: list[TimelineClip] = []
        changed = False
        for c in sorted(clips, key=lambda x: x.position):
            speed = getattr(c, "speed", 1.0)
            if c.end <= t0 + eps:
                out.append(c)
            elif c.position >= t1 - eps:
                if ripple:
                    out.append(_clone_clip(c, position=max(0.0, c.position - cut_dur)))
                    changed = True
                else:
                    out.append(c)
            elif c.position >= t0 - eps and c.end <= t1 + eps:
                changed = True
            elif c.position < t0 - eps and c.end > t1 + eps:
                left_dur = t0 - c.position
                right_dur = c.end - t1
                left = _clone_clip(
                    c, duration=left_dur,
                    fade_out_duration=0.0,
                    fade_in_duration=min(getattr(c, "fade_in_duration", 0.0), left_dur))
                right = _clone_clip(
                    c, id=new_id(),
                    position=t0 if ripple else t1,
                    duration=right_dur,
                    trim_in=c.trim_in + (t1 - c.position) * speed,
                    fade_in_duration=0.0,
                    fade_out_duration=min(getattr(c, "fade_out_duration", 0.0), right_dur))
                out.append(left)
                out.append(right)
                changed = True
            elif c.position < t0 - eps and t0 < c.end <= t1 + eps:
                new_dur = t0 - c.position
                out.append(_clone_clip(
                    c, duration=new_dur,
                    fade_out_duration=0.0,
                    fade_in_duration=min(getattr(c, "fade_in_duration", 0.0), new_dur)))
                changed = True
            elif t0 - eps <= c.position < t1 and c.end > t1 + eps:
                cut_head = t1 - c.position
                new_dur = c.end - t1
                out.append(_clone_clip(
                    c, position=t0 if ripple else t1,
                    duration=new_dur,
                    trim_in=c.trim_in + cut_head * speed,
                    fade_in_duration=0.0,
                    fade_out_duration=min(getattr(c, "fade_out_duration", 0.0), new_dur)))
                changed = True
        return out, changed

    @staticmethod
    def _cut_subs_list(subs: list[SubtitleClip], t0: float, t1: float, ripple: bool) -> tuple[list[SubtitleClip], bool]:
        eps = 1e-4
        cut_dur = t1 - t0
        out: list[SubtitleClip] = []
        changed = False
        for s in sorted(subs, key=lambda x: x.position):
            if s.end <= t0 + eps:
                out.append(s)
            elif s.position >= t1 - eps:
                if ripple:
                    out.append(_clone_subtitle(s, position=max(0.0, s.position - cut_dur)))
                    changed = True
                else:
                    out.append(s)
            elif s.position >= t0 - eps and s.end <= t1 + eps:
                changed = True
            elif s.position < t0 - eps and s.end > t1 + eps:
                left_dur = t0 - s.position
                right_dur = s.end - t1
                out.append(_clone_subtitle(s, duration=left_dur))
                out.append(_clone_subtitle(s, id=new_id(), position=t0 if ripple else t1, duration=right_dur))
                changed = True
            elif s.position < t0 - eps and t0 < s.end <= t1 + eps:
                out.append(_clone_subtitle(s, duration=t0 - s.position))
                changed = True
            elif t0 - eps <= s.position < t1 and s.end > t1 + eps:
                out.append(_clone_subtitle(s, position=t0 if ripple else t1, duration=s.end - t1))
                changed = True
        return out, changed

    def redo(self):
        for idx, tr in enumerate(self._p.video_tracks):
            if idx < len(self._after_video):
                tr.clips = [_clone_clip(c) for c in self._after_video[idx]]
        for idx, tr in enumerate(self._p.audio_tracks):
            if idx < len(self._after_audio):
                tr.clips = [_clone_clip(c) for c in self._after_audio[idx]]
        self._p.subtitles = [_clone_subtitle(s) for s in self._after_subs]

    def undo(self):
        for idx, tr in enumerate(self._p.video_tracks):
            if idx < len(self._before_video):
                tr.clips = [_clone_clip(c) for c in self._before_video[idx]]
        for idx, tr in enumerate(self._p.audio_tracks):
            if idx < len(self._before_audio):
                tr.clips = [_clone_clip(c) for c in self._before_audio[idx]]
        self._p.subtitles = [_clone_subtitle(s) for s in self._before_subs]


class _SetProp(QUndoCommand):
    def __init__(self, project, clip_id, attr, value):
        super().__init__(f"Set {attr}")
        self._p = project
        self._id = clip_id
        self._attr = attr
        self._value = value
        c = project.clip_by_id(clip_id)
        self._old = getattr(c, attr) if c else None

    def redo(self):
        c = self._p.clip_by_id(self._id)
        if c:
            setattr(c, self._attr, self._value)

    def undo(self):
        c = self._p.clip_by_id(self._id)
        if c and self._old is not None:
            setattr(c, self._attr, self._old)


class _SetTransition(QUndoCommand):
    def __init__(self, project, clip_id, fade_in_dur, fade_in_type, fade_out_dur, fade_out_type):
        super().__init__("Set Transition")
        self._p = project
        self._id = clip_id
        c = project.clip_by_id(clip_id)
        self._old_in_dur = c.fade_in_duration if c else 0.0
        self._old_in_type = c.fade_in_type if c else "fade"
        self._old_out_dur = c.fade_out_duration if c else 0.0
        self._old_out_type = c.fade_out_type if c else "fade"

        self._new_in_dur = fade_in_dur if fade_in_dur is not None else self._old_in_dur
        self._new_in_type = fade_in_type if fade_in_type is not None else self._old_in_type
        self._new_out_dur = fade_out_dur if fade_out_dur is not None else self._old_out_dur
        self._new_out_type = fade_out_type if fade_out_type is not None else self._old_out_type

    def redo(self):
        c = self._p.clip_by_id(self._id)
        if c:
            c.fade_in_duration = self._new_in_dur
            c.fade_in_type = self._new_in_type
            c.fade_out_duration = self._new_out_dur
            c.fade_out_type = self._new_out_type

    def undo(self):
        c = self._p.clip_by_id(self._id)
        if c:
            c.fade_in_duration = self._old_in_dur
            c.fade_in_type = self._old_in_type
            c.fade_out_duration = self._old_out_dur
            c.fade_out_type = self._old_out_type


def parse_srt(content: str) -> list[dict]:
    import re
    blocks = re.split(r'\n\s*\n', content.strip())
    subtitles = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) >= 2:
            time_line = lines[1] if '-->' in lines[1] else lines[0]
            if '-->' not in time_line:
                continue
            times = time_line.split('-->')
            if len(times) != 2:
                continue
            start_sec = _srt_time_to_sec(times[0].strip())
            end_sec = _srt_time_to_sec(times[1].strip())
            text_lines = lines[2:] if '-->' in lines[1] else lines[1:]
            text = "\n".join(text_lines)
            if end_sec > start_sec and text:
                subtitles.append({"position": start_sec, "duration": end_sec - start_sec, "text": text})
    return subtitles


def _srt_time_to_sec(ts: str) -> float:
    ts = ts.replace(',', '.')
    parts = ts.split(':')
    if len(parts) == 3:
        try:
            h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
            return h * 3600 + m * 60 + s
        except ValueError:
            pass
    return 0.0


def sec_to_srt_time(sec: float) -> str:
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class _AddSubtitle(QUndoCommand):
    def __init__(self, project: Project, subtitle: SubtitleClip):
        super().__init__("Add Subtitle")
        self._p = project
        self._sub = subtitle

    def redo(self):
        self._p.subtitles.append(self._sub)

    def undo(self):
        self._p.subtitles = [s for s in self._p.subtitles if s.id != self._sub.id]


class _RemoveSubtitle(QUndoCommand):
    def __init__(self, project: Project, subtitle: SubtitleClip):
        super().__init__("Remove Subtitle")
        self._p = project
        self._sub = subtitle

    def redo(self):
        self._p.subtitles = [s for s in self._p.subtitles if s.id != self._sub.id]

    def undo(self):
        self._p.subtitles.append(self._sub)


class _UpdateSubtitle(QUndoCommand):
    def __init__(self, project: Project, sub_id: str, updates: dict):
        super().__init__("Update Subtitle")
        self._p = project
        self._id = sub_id
        self._updates = updates
        sub = project.subtitle_by_id(sub_id)
        self._old = {k: getattr(sub, k) for k in updates if hasattr(sub, k)} if sub else {}

    def redo(self):
        sub = self._p.subtitle_by_id(self._id)
        if sub:
            for k, v in self._updates.items():
                if hasattr(sub, k):
                    setattr(sub, k, v)

    def undo(self):
        sub = self._p.subtitle_by_id(self._id)
        if sub:
            for k, v in self._old.items():
                setattr(sub, k, v)


class _ImportSRT(QUndoCommand):
    def __init__(self, project: Project, subtitles: list[SubtitleClip]):
        super().__init__("Import SRT Subtitles")
        self._p = project
        self._subs = subtitles

    def redo(self):
        self._p.subtitles.extend(self._subs)

    def undo(self):
        ids = {s.id for s in self._subs}
        self._p.subtitles = [s for s in self._p.subtitles if s.id not in ids]


class _ImportAutoSubtitles(QUndoCommand):
    def __init__(self, project: Project, subtitles: list[SubtitleClip]):
        super().__init__("Auto Generate Subtitles")
        self._p = project
        self._subs = subtitles

    def redo(self):
        self._p.subtitles.extend(self._subs)

    def undo(self):
        ids = {s.id for s in self._subs}
        self._p.subtitles = [s for s in self._p.subtitles if s.id not in ids]


class _SetChromaKey(QUndoCommand):
    def __init__(
        self, project: Project, clip_id: str,
        enabled: bool | None = None,
        color: str | None = None,
        similarity: float | None = None,
        smoothness: float | None = None,
    ):
        super().__init__("Set Chroma Key")
        self._p = project
        self._id = clip_id
        self._updates = {}
        if enabled is not None:
            self._updates["chroma_key_enabled"] = enabled
        if color is not None:
            self._updates["chroma_key_color"] = color
        if similarity is not None:
            self._updates["chroma_key_similarity"] = similarity
        if smoothness is not None:
            self._updates["chroma_key_smoothness"] = smoothness

        c = self._p.clip_by_id(self._id)
        self._old = {k: getattr(c, k) for k in self._updates if c and hasattr(c, k)}

    def redo(self):
        c = self._p.clip_by_id(self._id)
        if c:
            for k, v in self._updates.items():
                setattr(c, k, v)

    def undo(self):
        c = self._p.clip_by_id(self._id)
        if c:
            for k, v in self._old.items():
                setattr(c, k, v)


class _SetObjectRemoval(QUndoCommand):
    def __init__(self, project: Project, clip_id: str, enabled: bool | None = None, masks: list[dict] | None = None):
        super().__init__("Object Removal Eraser")
        self._p = project
        self._id = clip_id
        self._updates = {}
        if enabled is not None:
            self._updates["object_removal_enabled"] = enabled
        if masks is not None:
            self._updates["object_removal_masks"] = masks

        c = self._p.clip_by_id(self._id)
        self._old = {k: getattr(c, k) for k in self._updates if c and hasattr(c, k)}

    def redo(self):
        c = self._p.clip_by_id(self._id)
        if c:
            for k, v in self._updates.items():
                setattr(c, k, v)

    def undo(self):
        c = self._p.clip_by_id(self._id)
        if c:
            for k, v in self._old.items():
                setattr(c, k, v)


class _AddVideoTrack(QUndoCommand):
    def __init__(self, project: Project):
        super().__init__("Add Video Track")
        self._p = project
        self._idx: int | None = None

    def redo(self):
        tr = self._p.add_video_track()
        self._idx = tr.index

    def undo(self):
        if self._idx is not None and len(self._p.video_tracks) > 1:
            self._p.video_tracks = [t for t in self._p.video_tracks if t.index != self._idx]
            for i, t in enumerate(self._p.video_tracks):
                t.index = i


class _SetPipGeometry(QUndoCommand):
    def __init__(
        self,
        project: Project,
        clip_id: str,
        pip_x: float | None = None,
        pip_y: float | None = None,
        pip_w: float | None = None,
        pip_h: float | None = None,
        border_width: int | None = None,
        border_color: str | None = None,
    ):
        super().__init__("Set PiP Geometry")
        self._p = project
        self._id = clip_id
        self._updates: dict = {}
        if pip_x is not None:
            self._updates["pip_x"] = max(-1.0, min(float(pip_x), 1.0))
        if pip_y is not None:
            self._updates["pip_y"] = max(-1.0, min(float(pip_y), 1.0))
        if pip_w is not None:
            self._updates["pip_w"] = max(0.05, min(float(pip_w), 2.0))
        if pip_h is not None:
            self._updates["pip_h"] = max(0.05, min(float(pip_h), 2.0))
        if border_width is not None:
            self._updates["pip_border_width"] = max(0, min(int(border_width), 30))
        if border_color is not None:
            self._updates["pip_border_color"] = str(border_color)

        c = self._p.clip_by_id(self._id)
        self._old = {k: getattr(c, k) for k in self._updates if c and hasattr(c, k)}
        self.has_changes = any(
            abs(self._updates[k] - self._old.get(k, 0)) > 1e-5
            if isinstance(self._updates[k], (int, float))
            else self._updates[k] != self._old.get(k)
            for k in self._updates
        )

    def redo(self):
        c = self._p.clip_by_id(self._id)
        if c:
            for k, v in self._updates.items():
                setattr(c, k, v)

    def undo(self):
        c = self._p.clip_by_id(self._id)
        if c:
            for k, v in self._old.items():
                setattr(c, k, v)
