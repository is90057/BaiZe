from __future__ import annotations

import os
import json
from dataclasses import dataclass, field

from .media import MediaClip, Track, TimelineClip, SubtitleClip, new_id


@dataclass
class Project:
    name: str = "Untitled"
    fps: float = 30.0
    width: int = 1920
    height: int = 1080
    video_tracks: list[Track] = field(default_factory=lambda: [Track("video", 0)])
    audio_tracks: list[Track] = field(default_factory=lambda: [Track("audio", 0)])
    subtitles: list[SubtitleClip] = field(default_factory=list)
    media: list[MediaClip] = field(default_factory=list)
    filepath: str = ""

    def all_tracks(self) -> list[Track]:
        return self.video_tracks + self.audio_tracks

    def track(self, kind: str, idx: int) -> Track:
        tracks = self.video_tracks if kind == "video" else self.audio_tracks
        return tracks[idx]

    def add_video_track(self) -> Track:
        t = Track("video", index=len(self.video_tracks),
                  name=f"V{len(self.video_tracks) + 1}")
        self.video_tracks.append(t)
        return t

    def add_audio_track(self) -> Track:
        t = Track("audio", index=len(self.audio_tracks),
                  name=f"A{len(self.audio_tracks) + 1}")
        self.audio_tracks.append(t)
        return t

    def media_by_id(self, media_id: str) -> MediaClip | None:
        for m in self.media:
            if m.id == media_id:
                return m
        return None

    def clip_by_id(self, clip_id: str) -> TimelineClip | None:
        for tr in self.all_tracks():
            for c in tr.clips:
                if c.id == clip_id:
                    return c
        return None

    def clip_media(self, clip: TimelineClip) -> MediaClip | None:
        return self.media_by_id(clip.media_id)

    def active_clip_at(self, kind: str, time: float) -> TimelineClip | None:
        """Topmost (highest index) enabled clip covering `time`."""
        tracks = self.video_tracks if kind == "video" else self.audio_tracks
        best: TimelineClip | None = None
        best_idx = -1
        for tr in tracks:
            if not tr.enabled:
                continue
            for c in tr.clips:
                if c.contains(time) and tr.index >= best_idx:
                    best, best_idx = c, tr.index
        return best

    def video_clips_at(self, time: float) -> list[TimelineClip]:
        """All visible video clips covering `time`, topmost last."""
        out: list[TimelineClip] = []
        for tr in self.video_tracks:
            if not tr.enabled:
                continue
            for c in tr.clips:
                if c.contains(time):
                    out.append(c)
        return out

    def audio_clips_at(self, time: float) -> list[TimelineClip]:
        out: list[TimelineClip] = []
        for tr in self.audio_tracks:
            if not tr.enabled or tr.muted:
                continue
            for c in tr.clips:
                if c.contains(time):
                    out.append(c)
        return out

    def subtitle_by_id(self, sub_id: str) -> SubtitleClip | None:
        for s in self.subtitles:
            if s.id == sub_id:
                return s
        return None

    def subtitles_at(self, time: float) -> list[SubtitleClip]:
        return [s for s in self.subtitles if s.contains(time)]

    def duration(self) -> float:
        end = 0.0
        for tr in self.all_tracks():
            for c in tr.clips:
                end = max(end, c.end)
        for s in self.subtitles:
            end = max(end, s.end)
        return end or 0.0

    # ---------- persistence ----------

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "media": [
                {"id": m.id, "path": m.path, "name": m.name,
                 "duration": m.duration, "width": m.width, "height": m.height,
                 "fps": m.fps, "has_video": m.has_video, "has_audio": m.has_audio,
                 "thumbnail": m.thumbnail}
                for m in self.media
            ],
            "video_tracks": [self._track_dict(t) for t in self.video_tracks],
            "audio_tracks": [self._track_dict(t) for t in self.audio_tracks],
            "subtitles": [
                {"id": s.id, "text": s.text, "position": s.position, "duration": s.duration,
                 "font_family": s.font_family, "font_size": s.font_size,
                 "font_color": s.font_color, "bg_color": s.bg_color,
                 "stroke_color": s.stroke_color, "stroke_width": s.stroke_width,
                 "alignment": s.alignment,
                 "animation_effect": getattr(s, "animation_effect", "none"),
                 "animation_duration": getattr(s, "animation_duration", 0.5)}
                for s in self.subtitles
            ],
        }

    @staticmethod
    def _track_dict(t: Track) -> dict:
        return {
            "kind": t.kind, "index": t.index, "name": t.name, "muted": t.muted,
            "enabled": t.enabled,
            "clips": [
                {"id": c.id, "media_id": c.media_id, "position": c.position,
                 "duration": c.duration, "trim_in": c.trim_in,
                 "track_index": c.track_index, "name": c.name,
                 "volume": c.volume, "opacity": c.opacity,
                 "fade_in_duration": c.fade_in_duration, "fade_in_type": c.fade_in_type,
                 "fade_out_duration": c.fade_out_duration, "fade_out_type": c.fade_out_type,
                 "chroma_key_enabled": getattr(c, "chroma_key_enabled", False),
                 "chroma_key_color": getattr(c, "chroma_key_color", "#00FF00"),
                 "chroma_key_similarity": getattr(c, "chroma_key_similarity", 0.3),
                 "chroma_key_smoothness": getattr(c, "chroma_key_smoothness", 0.1),
                 "video_fx": getattr(c, "video_fx", "none"),
                 "speed": getattr(c, "speed", 1.0),
                 "brightness": getattr(c, "brightness", 0.0),
                 "contrast": getattr(c, "contrast", 1.0),
                 "saturation": getattr(c, "saturation", 1.0),
                 "blur_amount": getattr(c, "blur_amount", 0.0),
                 "focus_mode": getattr(c, "focus_mode", "none"),
                 "object_removal_enabled": getattr(c, "object_removal_enabled", False),
                 "object_removal_masks": getattr(c, "object_removal_masks", [])}
                for c in t.clips
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        p = cls(name=d.get("name", "Untitled"),
                fps=d.get("fps", 30.0),
                width=d.get("width", 1920),
                height=d.get("height", 1080))
        p.media = [MediaClip(**m) for m in d.get("media", [])]
        p.video_tracks = [cls._track_from_dict(i, t) for i, t in enumerate(d.get("video_tracks", []))]
        p.audio_tracks = [cls._track_from_dict(i, t) for i, t in enumerate(d.get("audio_tracks", []))]
        
        valid_sub_keys = {
            "id", "text", "position", "duration", "font_family", "font_size",
            "font_color", "bg_color", "stroke_color", "stroke_width",
            "alignment", "animation_effect", "animation_duration"
        }
        sub_objs = []
        for sd in d.get("subtitles", []):
            filtered = {k: v for k, v in sd.items() if k in valid_sub_keys}
            sub_objs.append(SubtitleClip(**filtered))
        p.subtitles = sub_objs
        if not p.video_tracks:
            p.video_tracks = [Track("video", 0)]
        if not p.audio_tracks:
            p.audio_tracks = [Track("audio", 0)]
        return p

    @staticmethod
    def _track_from_dict(idx: int, d: dict) -> Track:
        kind = d.get("kind", "video")
        t = Track(kind, index=idx)
        t.name = d.get("name", "")
        t.muted = d.get("muted", False)
        t.enabled = d.get("enabled", True)
        for cd in d.get("clips", []):
            c = TimelineClip(
                media_id=cd["media_id"], position=cd.get("position", 0.0),
                duration=cd.get("duration", 0.0), trim_in=cd.get("trim_in", 0.0),
                track_index=idx, name=cd.get("name", ""),
                volume=cd.get("volume", 1.0), opacity=cd.get("opacity", 1.0),
                fade_in_duration=cd.get("fade_in_duration", 0.0),
                fade_in_type=cd.get("fade_in_type", "fade"),
                fade_out_duration=cd.get("fade_out_duration", 0.0),
                fade_out_type=cd.get("fade_out_type", "fade"),
                chroma_key_enabled=cd.get("chroma_key_enabled", False),
                chroma_key_color=cd.get("chroma_key_color", "#00FF00"),
                chroma_key_similarity=cd.get("chroma_key_similarity", 0.3),
                chroma_key_smoothness=cd.get("chroma_key_smoothness", 0.1),
                video_fx=cd.get("video_fx", "none"),
                speed=cd.get("speed", 1.0),
                brightness=cd.get("brightness", 0.0),
                contrast=cd.get("contrast", 1.0),
                saturation=cd.get("saturation", 1.0),
                blur_amount=cd.get("blur_amount", 0.0),
                focus_mode=cd.get("focus_mode", "none"),
                object_removal_enabled=cd.get("object_removal_enabled", False),
                object_removal_masks=cd.get("object_removal_masks", []),
                id=cd.get("id", new_id())
            )
            t.clips.append(c)
        return t


def save_project(project: Project, path: str) -> None:
    data = project.to_dict()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    project.filepath = path


def load_project(path: str) -> Project:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    p = Project.from_dict(data)
    p.filepath = path
    return p