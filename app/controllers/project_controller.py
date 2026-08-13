from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QUndoStack, QUndoCommand

from ..models.media import MediaClip, TimelineClip, SubtitleClip, new_id
from ..models.project import Project


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

    def trim_clip(self, clip_id: str, new_trim_in: float, new_duration: float):
        c = self.project.clip_by_id(clip_id)
        if c is None:
            return
        self.undo_stack.push(
            _TrimClip(self.project, clip_id, c.trim_in, c.duration,
                      new_trim_in, new_duration))

    def remove_clip(self, clip_id: str, kind: str):
        c = self.project.clip_by_id(clip_id)
        if c is None:
            return
        self.undo_stack.push(_RemoveClip(self.project, clip_id, c.track_index, kind))

    def split_clip(self, clip_id: str, time: float, kind: str):
        c = self.project.clip_by_id(clip_id)
        if c is None or not (c.position < time < c.end - 1e-3):
            return
        self.undo_stack.push(_SplitClip(self.project, clip_id, time, kind))

    def set_clip_volume(self, clip_id: str, volume: float):
        self._set_clip_prop(clip_id, "volume", volume)

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
    def __init__(self, project, clip_id, old_in, old_dur, new_in, new_dur):
        super().__init__("Trim Clip")
        self._p = project
        self._id = clip_id
        self._old_in, self._old_dur = old_in, old_dur
        self._new_in, self._new_dur = new_in, new_dur

    def redo(self):
        self._apply(self._new_in, self._new_dur)

    def undo(self):
        self._apply(self._old_in, self._old_dur)

    def _apply(self, tin, dur):
        c = self._p.clip_by_id(self._id)
        if c is None:
            return
        c.trim_in = max(tin, 0.0)
        c.duration = max(dur, 1e-3)


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
        self._left: TimelineClip | None = None
        self._right: TimelineClip | None = None
        self._track_index = 0

    def redo(self):
        c = self._p.clip_by_id(self._id)
        if c is None:
            return
        if self._left is None:
            t = self._time
            self._track_index = c.track_index
            self._left = TimelineClip(
                media_id=c.media_id, position=c.position, duration=t - c.position,
                trim_in=c.trim_in, volume=c.volume, opacity=c.opacity,
                name=c.name, track_index=c.track_index, id=new_id())
            self._right = TimelineClip(
                media_id=c.media_id, position=t, duration=c.end - t,
                trim_in=c.trim_in + (t - c.position), volume=c.volume,
                opacity=c.opacity, name=c.name, track_index=c.track_index,
                id=new_id())
        track = _track_of(self._p, self._kind, self._track_index)
        track.clips = [x for x in track.clips if x.id != self._id]
        track.clips.append(self._left)
        track.clips.append(self._right)

    def undo(self):
        if self._left is None:
            return
        track = _track_of(self._p, self._kind, self._track_index)
        track.clips = [x for x in track.clips
                       if x.id not in (self._left.id, self._right.id)]
        c = TimelineClip(
            media_id=self._left.media_id, position=self._left.position,
            duration=self._left.duration + self._right.duration,
            trim_in=self._left.trim_in, volume=self._left.volume,
            opacity=self._left.opacity, name=self._left.name,
            track_index=self._track_index, id=self._id)
        track.clips.append(c)


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