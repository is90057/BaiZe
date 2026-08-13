from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class MediaClip:
    """A source asset imported into the media library."""

    path: str
    name: str = ""
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 30.0
    has_video: bool = True
    has_audio: bool = False
    is_image: bool = False
    has_alpha: bool = False
    thumbnail: str = ""
    id: str = field(default_factory=new_id)

    def filepath(self) -> Path:
        return Path(self.path)

    @property
    def resolution(self) -> str:
        if self.width and self.height:
            return f"{self.width}×{self.height}"
        return "—"


@dataclass
class TimelineClip:
    """An instance of a MediaClip placed on the timeline."""

    media_id: str
    position: float = 0.0          # timeline start (sec)
    duration: float = 0.0          # visible duration (sec)
    trim_in: float = 0.0           # offset into source (sec)
    track_index: int = 0
    name: str = ""
    volume: float = 1.0
    opacity: float = 1.0
    fade_in_duration: float = 0.0
    fade_in_type: str = "fade"
    fade_out_duration: float = 0.0
    fade_out_type: str = "fade"
    chroma_key_enabled: bool = False
    chroma_key_color: str = "#00FF00"
    chroma_key_similarity: float = 0.3
    chroma_key_smoothness: float = 0.1
    video_fx: str = "none"
    speed: float = 1.0            # speed multiplier (0.25x ~ 4.0x)
    brightness: float = 0.0       # -1.0 ~ 1.0 (0.0 default)
    contrast: float = 1.0         # 0.1 ~ 3.0 (1.0 default)
    saturation: float = 1.0       # 0.0 ~ 3.0 (1.0 default)
    blur_amount: float = 0.0      # 0.0 ~ 20.0 (0.0 default)
    focus_mode: str = "none"      # "none" | "gaussian_blur" | "center_focus" | "tilt_shift"
    object_removal_enabled: bool = False
    object_removal_masks: list[dict] = field(default_factory=list)
    id: str = field(default_factory=new_id)

    @property
    def end(self) -> float:
        return self.position + self.duration

    @property
    def trim_out(self) -> float:
        return self.trim_in + self.duration * self.speed

    def contains(self, time: float) -> bool:
        return self.position <= time < self.end


@dataclass
class Track:
    kind: str            # "video" | "audio"
    index: int = 0
    name: str = ""
    muted: bool = False
    enabled: bool = True
    clips: list[TimelineClip] = field(default_factory=list)

    def sorted_clips(self) -> list[TimelineClip]:
        return sorted(self.clips, key=lambda c: c.position)


@dataclass
class SubtitleClip:
    """A subtitle or text overlay clip on the timeline."""

    text: str = ""
    position: float = 0.0          # timeline start (sec)
    duration: float = 3.0          # visible duration (sec)
    font_family: str = "Arial"
    font_size: int = 36
    font_color: str = "#FFFFFF"
    bg_color: str = "#00000080"
    stroke_color: str = "#000000"
    stroke_width: int = 2
    alignment: str = "bottom_center"
    animation_effect: str = "none" # "none" | "fly" | "fade" | "typewriter"
    animation_duration: float = 0.5
    id: str = field(default_factory=new_id)

    @property
    def end(self) -> float:
        return self.position + self.duration

    def contains(self, time: float) -> bool:
        return self.position <= time < self.end