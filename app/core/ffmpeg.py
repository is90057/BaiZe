from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

FFPROBE = shutil.which("ffprobe") or "ffprobe"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

THUMB_CACHE = Path(tempfile.gettempdir()) / "baize_thumbs"


def _run(args: list[str], timeout: int = 300) -> bytes:
    proc = subprocess.run(args, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed: {' '.join(args)}\n"
            f"{proc.stderr.decode(errors='replace')[-2000:]}")
    return proc.stdout


def probe(path: str) -> dict:
    args = [
        FFPROBE, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    out = _run(args)
    data = json.loads(out)
    fmt = data.get("format", {})
    ext = Path(path).suffix.lower()
    is_img_ext = ext in (".bmp", ".jpg", ".jpeg", ".png", ".webp")

    result = {
        "duration": float(fmt.get("duration", 0.0) or 0.0),
        "width": 0, "height": 0, "fps": 30.0,
        "has_video": False, "has_audio": False, "is_image": is_img_ext, "has_alpha": False,
        "codec": "", "audio_codec": "",
    }
    for s in data.get("streams", []):
        stype = s.get("codec_type")
        if stype == "video":
            result["has_video"] = True
            result["width"] = int(s.get("width", 0))
            result["height"] = int(s.get("height", 0))
            codec = s.get("codec_name", "")
            result["codec"] = codec
            pix_fmt = str(s.get("pix_fmt", "")).lower()
            if "alpha" in pix_fmt or "rgba" in pix_fmt or "bgra" in pix_fmt or "yuva" in pix_fmt or "pal8" in pix_fmt or ext in (".png", ".webp"):
                result["has_alpha"] = True
            if codec in ("png", "webp", "bmp", "mjpeg", "jpeg") or is_img_ext:
                result["is_image"] = True
            fps = s.get("r_frame_rate", "30/1")
            try:
                num, den = fps.split("/")
                den = float(den) or 1.0
                result["fps"] = float(num) / den
            except (ValueError, ZeroDivisionError):
                result["fps"] = 30.0
            if s.get("duration"):
                dur = float(s["duration"])
                if dur > 0:
                    result["duration"] = dur
        elif stype == "audio":
            result["has_audio"] = True
            result["audio_codec"] = s.get("codec_name", "")

    if result["is_image"]:
        result["has_video"] = True
        if result["duration"] <= 0.0:
            result["duration"] = 5.0

    if result["width"] % 2:
        result["width"] -= 1
    if result["height"] % 2:
        result["height"] -= 1
    return result


_CAP_CACHE: dict[str, tuple[any, float]] = {}
import threading
_CAP_LOCK = threading.Lock()


def _get_cv2_frame(path: str, time_sec: float, width: int, height: int, is_rgba: bool = False) -> np.ndarray | None:
    """Fast video frame decoding via OpenCV VideoCapture with caching."""
    if not os.path.exists(path):
        return None
    try:
        import cv2
        with _CAP_LOCK:
            cap = None
            if path in _CAP_CACHE:
                cap, _ = _CAP_CACHE[path]
                if cap is not None and not cap.isOpened():
                    cap = None
            if cap is None:
                cap = cv2.VideoCapture(path)
                if not cap.isOpened():
                    return None
                if len(_CAP_CACHE) > 10:
                    old_path, (old_cap, _) = next(iter(_CAP_CACHE.items()))
                    try:
                        old_cap.release()
                    except Exception:
                        pass
                    _CAP_CACHE.pop(old_path, None)
                _CAP_CACHE[path] = (cap, time_sec)

            time_ms = max(0.0, time_sec * 1000.0)
            cap.set(cv2.CAP_PROP_POS_MSEC, time_ms)
            ret, frame = cap.read()
            if not ret or frame is None:
                return None

            h, w = frame.shape[:2]
            scale = min(width / w, height / h)
            nw, nh = max(1, int(w * scale)), max(1, int(h * scale))

            if is_rgba:
                frame_conv = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
            else:
                frame_conv = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            resized = cv2.resize(frame_conv, (nw, nh), interpolation=cv2.INTER_LINEAR)
            channels = 4 if is_rgba else 3
            canvas = np.zeros((height, width, channels), dtype=np.uint8)
            if is_rgba:
                canvas[:, :, 3] = 255
            y0 = (height - nh) // 2
            x0 = (width - nw) // 2
            canvas[y0:y0+nh, x0:x0+nw] = resized
            return np.ascontiguousarray(canvas)
    except Exception:
        return None


def decode_frame(path: str, time_sec: float, width: int, height: int,
                 pix_fmt: str = "rgb24") -> np.ndarray:
    """Decode an accurate single frame to an HxWx3 uint8 numpy array."""
    ext = Path(path).suffix.lower()
    is_img = ext in (".bmp", ".jpg", ".jpeg", ".png", ".webp", ".gif")
    if not is_img:
        arr = _get_cv2_frame(path, time_sec, width, height, is_rgba=False)
        if arr is not None:
            return arr

    args = [
        FFMPEG, "-v", "error",
        "-ss", f"{max(time_sec, 0.0):.6f}",
        "-i", path,
        "-frames:v", "1",
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-f", "rawvideo",
        "-pix_fmt", pix_fmt,
        "-",
    ]
    try:
        data = _run(args)
        expected = width * height * 3
        if len(data) >= expected:
            return np.ascontiguousarray(np.frombuffer(data[:expected], dtype=np.uint8).reshape(height, width, 3))
    except Exception:
        pass
    return np.zeros((height, width, 3), dtype=np.uint8)


def decode_frame_rgba(path: str, time_sec: float, width: int, height: int, is_image: bool = False) -> np.ndarray:
    """Decode a single frame or image to an HxWx4 uint8 numpy array with Alpha channel."""
    if not is_image:
        arr = _get_cv2_frame(path, time_sec, width, height, is_rgba=True)
        if arr is not None:
            return arr

    args = [FFMPEG, "-v", "error"]
    if not is_image:
        args.extend(["-ss", f"{max(time_sec, 0.0):.6f}"])
    args.extend([
        "-i", path,
        "-frames:v", "1",
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-f", "rawvideo",
        "-pix_fmt", "rgba",
        "-",
    ])
    try:
        data = _run(args)
        expected = width * height * 4
        if len(data) >= expected:
            return np.ascontiguousarray(np.frombuffer(data[:expected], dtype=np.uint8).reshape(height, width, 4))
    except Exception:
        pass
    return np.zeros((height, width, 4), dtype=np.uint8)


def composite_alpha(base_rgb: np.ndarray, overlay_rgba: np.ndarray, opacity: float = 1.0) -> np.ndarray:
    """Composite an HxWx4 RGBA overlay image onto an HxWx3 RGB background using alpha blending."""
    if overlay_rgba.shape[:2] != base_rgb.shape[:2]:
        return base_rgb
    rgb = overlay_rgba[:, :, :3].astype(np.float32)
    alpha = (overlay_rgba[:, :, 3].astype(np.float32) / 255.0) * opacity
    alpha = np.expand_dims(alpha, axis=2)

    out = rgb * alpha + base_rgb.astype(np.float32) * (1.0 - alpha)
    return np.clip(out, 0, 255).astype(np.uint8)


def thumbnail(path: str, duration: float, out_size: int = 320) -> str:
    """Generate and cache a thumbnail jpg; returns the cache path ('' on fail)."""
    key = _cache_key(path, out_size)
    dest = THUMB_CACHE / f"{key}.jpg"
    if dest.exists():
        return str(dest)
    THUMB_CACHE.mkdir(parents=True, exist_ok=True)
    t = min(duration * 0.3, 1.0) if duration > 0 else 0.0
    tmp = THUMB_CACHE / f"{key}.tmp.jpg"
    args = [
        FFMPEG, "-y", "-v", "error",
        "-ss", f"{t:.3f}", "-i", path,
        "-frames:v", "1",
        "-vf", f"scale={out_size}:-2",
        "-q:v", "4", str(tmp),
    ]
    try:
        subprocess.run(args, capture_output=True, timeout=60, check=True)
    except Exception:
        return ""
    finally:
        if not (tmp.exists() and tmp.stat().st_size > 0):
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    if tmp.exists() and tmp.stat().st_size > 0:
        os.replace(tmp, dest)
        return str(dest)
    return ""


def _cache_key(path: str, size: int) -> str:
    try:
        st = os.stat(path)
        base = hashlib.md5(f"{path}:{st.st_mtime_ns}:{st.st_size}".encode()).hexdigest()
    except OSError:
        base = hashlib.md5(path.encode()).hexdigest()
    return f"{base}_{size}"


def sprite_strip(path: str, duration: float, thumb_h: int = 56,
                 frames: int = 10) -> str:
    """Contact sheet of `frames` evenly-spaced thumbnails; returns cached jpg path."""
    if duration <= 0:
        return ""
    thumb_h2 = thumb_h // 2 * 2
    thumb_w = max(int(thumb_h2 * 16 / 9) // 2 * 2, 32)
    key = hashlib.md5(
        f"{path}:{os.stat(path).st_mtime_ns}:{thumb_h}:{frames}".encode()).hexdigest()
    THUMB_CACHE.mkdir(parents=True, exist_ok=True)
    dest = THUMB_CACHE / f"strip_{key}.jpg"
    if dest.exists():
        return str(dest)
    tmp = THUMB_CACHE / f"strip_{key}.tmp.jpg"
    step = max(duration / frames, 1e-3)
    args = [
        FFMPEG, "-y", "-v", "error",
        "-i", path,
        "-vf",
        f"fps={1.0 / step},scale={thumb_w}:{thumb_h2}:force_original_aspect_ratio=decrease,"
        f"pad={thumb_w}:{thumb_h2}:(ow-iw)/2:(oh-ih)/2,tile={frames}x1",
        "-frames:v", "1", "-q:v", "5", str(tmp),
    ]
    try:
        subprocess.run(args, capture_output=True, timeout=120, check=True)
    except Exception:
        return ""
    if tmp.exists() and tmp.stat().st_size > 0:
        os.replace(tmp, dest)
        return str(dest)
    return ""


def _scale_vf(mode: str, width: int, height: int) -> str:
    if mode == "stretch":
        return f"scale={width}:{height},setsar=1"
    if mode == "crop":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1"
        )
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setdar={width}/{height},setsar=1"
    )


def _resolve_cuts(clips, start: float, end: float):
    """Resolve a list of clips into ordered non-overlapping (clip, t0, t1)
    segments covering [start, end]. Overlaps keep the latest-starting clip."""
    eps = 1e-4
    pts: set[float] = {start, end}
    for c in clips:
        a, b = max(c.position, start), min(c.end, end)
        if b - a > eps:
            pts.add(a)
            pts.add(b)
    pts = sorted(p for p in pts if start - eps <= p <= end + eps)
    out: list[tuple] = []
    for i in range(len(pts) - 1):
        t0, t1 = pts[i], pts[i + 1]
        mid = (t0 + t1) / 2.0
        cover = [c for c in clips if c.position <= mid < c.end]
        if not cover:
            continue
        top = max(cover, key=lambda c: (c.position, c.end))
        if out and out[-1][0].id == top.id and abs(out[-1][2] - t0) < eps:
            out[-1] = (top, out[-1][1], t1)
        else:
            out.append((top, t0, t1))
    return out


def _has_drawtext() -> bool:
    """Check if ffmpeg build has the drawtext filter enabled."""
    try:
        proc = subprocess.run([FFMPEG, "-filters"], capture_output=True, text=True, timeout=5)
        return "drawtext" in proc.stdout
    except Exception:
        return False


def _render_subtitle_png(s, W: int, H: int, out_path: str) -> str:
    """Render subtitle clip into a transparent PNG overlay image for FFmpeg overlay."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font_size = max(12, int(s.font_size * (H / 720.0)))

        font = None
        for font_path in [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "C:/Windows/Fonts/msjh.ttc",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except Exception:
                    pass
        if font is None:
            font = ImageFont.load_default()

        lines = s.text.splitlines() or [""]
        line_bboxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
        text_w = max((b[2] - b[0] for b in line_bboxes), default=100)
        line_h = max((b[3] - b[1] for b in line_bboxes), default=font_size) + 6
        text_h = line_h * len(lines)

        margin_x, margin_y = 20, int(H * 0.08)
        if s.alignment == "top_center":
            x, y = (W - text_w) // 2, margin_y
        elif s.alignment == "center":
            x, y = (W - text_w) // 2, (H - text_h) // 2
        elif s.alignment == "bottom_left":
            x, y = margin_x, H - margin_y - text_h
        elif s.alignment == "bottom_right":
            x, y = W - margin_x - text_w, H - margin_y - text_h
        else:  # bottom_center
            x, y = (W - text_w) // 2, H - margin_y - text_h

        if s.bg_color:
            bg_hex = s.bg_color.lstrip("#")
            if len(bg_hex) == 6:
                r, g, b = int(bg_hex[:2], 16), int(bg_hex[2:4], 16), int(bg_hex[4:6], 16)
                bg_rgba = (r, g, b, 180)
            elif len(bg_hex) == 8:
                r, g, b, a = int(bg_hex[:2], 16), int(bg_hex[2:4], 16), int(bg_hex[4:6], 16), int(bg_hex[6:8], 16)
                bg_rgba = (r, g, b, a)
            else:
                bg_rgba = (0, 0, 0, 160)
            pad = 10
            draw.rectangle([x - pad, y - pad, x + text_w + pad, y + text_h + pad], fill=bg_rgba)

        font_hex = s.font_color.lstrip("#")
        if len(font_hex) == 6:
            font_rgba = (int(font_hex[:2], 16), int(font_hex[2:4], 16), int(font_hex[4:6], 16), 255)
        else:
            font_rgba = (255, 255, 255, 255)

        stroke_w = getattr(s, "stroke_width", 0)
        stroke_rgba = (0, 0, 0, 255)
        if getattr(s, "stroke_color", ""):
            st_hex = s.stroke_color.lstrip("#")
            if len(st_hex) == 6:
                stroke_rgba = (int(st_hex[:2], 16), int(st_hex[2:4], 16), int(st_hex[4:6], 16), 255)

        for idx, line in enumerate(lines):
            ly = y + idx * line_h
            if stroke_w > 0:
                draw.text((x, ly), line, font=font, fill=font_rgba, stroke_width=stroke_w, stroke_fill=stroke_rgba)
            else:
                draw.text((x, ly), line, font=font, fill=font_rgba)

        img.save(out_path)
        return out_path
    except Exception:
        return ""


def build_ffmpeg_cmd(
    project,
    output: str,
    start: float = 0.0,
    end: float | None = None,
    fps: float | None = None,
    resolution: tuple[int, int] | None = None,
    scale_mode: str = "fit",
    video_bitrate: str = "",
    audio_bitrate: str = "192k",
    crf: int = 18,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
) -> list[str]:
    """Build the full ffmpeg command that renders the timeline to `output`."""
    out_fps = float(fps or project.fps)
    W, H = resolution or (project.width, project.height)
    timeline_end = project.duration()
    end = timeline_end if end is None or end <= 0 else min(end, timeline_end)
    play_len = max(end - start, 0.0)

    media_by_id = {m.id: m for m in project.media}

    def media_of(c):
        return media_by_id.get(c.media_id)

    vid: dict[int, list] = {}
    for tr in project.video_tracks:
        if not tr.enabled:
            continue
        clips = [c for c in tr.clips
                 if media_of(c) is not None and media_of(c).has_video]
        if clips:
            vid[tr.index] = clips

    aud: dict[int, list] = {}
    for tr in project.audio_tracks:
        if not tr.enabled or tr.muted:
            continue
        clips = [c for c in tr.clips
                 if media_of(c) is not None and media_of(c).has_audio]
        if clips:
            aud[tr.index] = clips

    cmd: list[str] = [FFMPEG, "-y", "-v", "error", "-stats"]
    fil: list[str] = []
    used_labels: set[str] = set()
    n_inputs = 0

    def new_input(path: str, src_time: float, duration: float, is_image: bool = False) -> int:
        nonlocal n_inputs
        if is_image:
            cmd.extend(["-loop", "1", "-t", f"{duration:.6f}", "-i", path])
        else:
            cmd.extend(["-ss", f"{src_time:.6f}", "-t", f"{duration:.6f}", "-i", path])
        idx = n_inputs
        n_inputs += 1
        return idx

    def new_label(prefix: str) -> str:
        i = len(used_labels)
        lbl = f"{prefix}{i}"
        while lbl in used_labels:
            i += 1
            lbl = f"{prefix}{i}"
        used_labels.add(lbl)
        return lbl

    def add_gap_label(dur: float) -> str:
        gl = new_label("g")
        fil.append(
            f"color=black:s={W}x{H}:r={out_fps:.3f}:d={dur:.6f},"
            f"setsar=1,setpts=PTS-STARTPTS[{gl}];"
        )
        return gl

    def clip_src_time(c, t: float) -> float:
        speed = getattr(c, "speed", 1.0)
        return c.trim_in + (t - c.position) * speed

    scale_vf = _scale_vf(scale_mode, W, H)

    # ---------- video: cut-resolve per track, concat, then overlay ----------
    track_outs: list[str] = []
    for ti in sorted(vid):
        cuts = _resolve_cuts(vid[ti], start, end)
        if not cuts:
            continue
        seg_outs: list[str] = []
        cursor = start
        for c, t0, t1 in cuts:
            gap = t0 - cursor
            if gap > 1e-3:
                seg_outs.append(add_gap_label(gap))
            m = media_of(c)
            c_speed = getattr(c, "speed", 1.0)
            seg_len = t1 - t0
            src_len = seg_len * c_speed
            inp = new_input(m.path, clip_src_time(c, t0), src_len, is_image=m.is_image if m else False)
            ol = new_label("v")
            trans_vf = _build_clip_transition_vf(c, seg_len)
            ck_vf = ""
            is_ck = getattr(c, "chroma_key_enabled", False)
            if is_ck:
                ck_col = getattr(c, "chroma_key_color", "#00FF00").replace("#", "0x")
                ck_sim = getattr(c, "chroma_key_similarity", 0.3)
                ck_sm = getattr(c, "chroma_key_smoothness", 0.1)
                ck_vf = f",colorkey={ck_col}:{ck_sim:.2f}:{ck_sm:.2f}"

            br = getattr(c, "brightness", 0.0)
            ct = getattr(c, "contrast", 1.0)
            sat = getattr(c, "saturation", 1.0)
            cc_vf = ""
            if abs(br) > 1e-3 or abs(ct - 1.0) > 1e-3 or abs(sat - 1.0) > 1e-3:
                cc_vf = f",eq=brightness={br:.2f}:contrast={ct:.2f}:saturation={sat:.2f}"

            focus_mode = getattr(c, "focus_mode", "none")
            blur_amt = getattr(c, "blur_amount", 0.0)
            bf_vf = ""
            if focus_mode == "gaussian_blur" or (focus_mode == "none" and blur_amt > 0):
                bf_vf = f",boxblur=luma_radius={max(1, int(blur_amt or 5))}:luma_power=1"
            elif focus_mode == "center_focus":
                bf_vf = f",vignette=angle=0.5"
            elif focus_mode == "tilt_shift":
                bf_vf = f",boxblur=luma_radius={max(1, int(blur_amt or 6))}:luma_power=1"

            fx_vf = ""
            fx_id = getattr(c, "video_fx", "none")
            if fx_id == "explosion":
                fx_vf = ",eq=contrast=1.45:brightness=0.15,vignette=angle=0.4"
            elif fx_id == "flash":
                fx_vf = ",eq=brightness=0.35:contrast=1.5,hue=s=1.2"
            elif fx_id == "particles":
                fx_vf = ",eq=contrast=1.2:saturation=1.4,colorbalance=rs=0.25:gs=0.15:bs=-0.15"
            elif fx_id == "cyber_particles":
                fx_vf = ",eq=contrast=1.25:saturation=1.5,colorbalance=rs=0.1:gs=-0.1:bs=0.25"
            elif fx_id == "warm_film":
                fx_vf = ",colorchannelmixer=1.15:0:0:0:0:1.05:0:0:0:0:0.85:0,eq=contrast=1.15:saturation=1.15"
            elif fx_id == "cool_cyber":
                fx_vf = ",colorchannelmixer=0.8:0:0:0:0:1.1:0:0:0:0:1.3:0,eq=contrast=1.2:saturation=1.2"
            elif fx_id == "teal_orange":
                fx_vf = ",colorbalance=rs=0.15:gs=0.0:bs=-0.15:rh=-0.1:gh=0.0:bh=0.15"
            elif fx_id == "center_focus":
                fx_vf = ",vignette=angle=0.5"
            elif fx_id == "tilt_shift":
                fx_vf = ",boxblur=luma_radius=6:luma_power=1"
            elif fx_id == "grayscale":
                fx_vf = ",hue=s=0"
            elif fx_id == "sepia":
                fx_vf = ",colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131"
            elif fx_id == "invert":
                fx_vf = ",negate"
            elif fx_id == "vivid":
                fx_vf = ",eq=contrast=1.35:saturation=1.4"
            elif fx_id == "blur":
                fx_vf = ",boxblur=4:1"
            elif fx_id == "mirror_h":
                fx_vf = ",hflip"
            elif fx_id == "vignette":
                fx_vf = ",vignette"

            removal_vf = ""
            if getattr(c, "object_removal_enabled", False):
                masks = getattr(c, "object_removal_masks", [])
                delogo_filters = []
                for m in masks:
                    cx = int(m.get("x", 0.5) * W)
                    cy = int(m.get("y", 0.5) * H)
                    r = max(4, int(m.get("radius", 0.05) * min(W, H)))
                    x0 = max(0, cx - r)
                    y0 = max(0, cy - r)
                    w0 = min(W - x0, r * 2)
                    h0 = min(H - y0, r * 2)
                    if w0 > 0 and h0 > 0:
                        delogo_filters.append(f"delogo=x={x0}:y={y0}:w={w0}:h={h0}")
                if delogo_filters:
                    removal_vf = "," + ",".join(delogo_filters)

            speed_vf = f",setpts=PTS/{c_speed:.4f}" if abs(c_speed - 1.0) > 1e-3 else ""

            fmt_str = "format=rgba" if (is_ck or (m and (m.has_alpha or m.is_image))) else "format=yuv420p"
            fil.append(
                f"[{inp}:v]{scale_vf}{trans_vf}{ck_vf}{cc_vf}{bf_vf}{fx_vf}{removal_vf}{speed_vf},fps={out_fps:.3f},"
                f"{fmt_str},setpts=PTS-STARTPTS[{ol}];"
            )
            seg_outs.append(ol)
            cursor = t1
        if play_len - (cursor - start) > 1e-3:
            seg_outs.append(add_gap_label(play_len - (cursor - start)))
        tl = new_label("t")
        if len(seg_outs) > 1:
            srcs = "".join(f"[{s}]" for s in seg_outs)
            fil.append(f"{srcs}concat=n={len(seg_outs)}:v=1:a=0[{tl}];")
        else:
            fil.append(f"[{seg_outs[0]}]null[{tl}];")
        track_outs.append(tl)

    if not track_outs:
        base = new_label("b")
        fil.append(
            f"color=black:s={W}x{H}:r={out_fps:.3f}:d={play_len:.6f},"
            f"setsar=1[{base}];"
        )
    else:
        base = track_outs[0]
        for upper in track_outs[1:]:
            ol = new_label("ov")
            fil.append(f"[{base}][{upper}]overlay=format=auto:eof_action=pass[{ol}];")
            base = ol

    # ---------- subtitles: drawtext or PNG overlay ----------
    if project.subtitles:
        use_drawtext = _has_drawtext()
        for idx_sub, s in enumerate(sorted(project.subtitles, key=lambda x: x.position)):
            if s.end <= start or s.position >= end or not s.text.strip():
                continue
            st = max(0.0, s.position - start)
            et = max(st, s.end - start)
            dur = max(0.1, et - st)

            if use_drawtext:
                for dt_filter in _build_drawtext_filters(s, W, H):
                    dt_label = new_label("dt")
                    fil.append(f"[{base}]{dt_filter}[{dt_label}];")
                    base = dt_label
            else:
                tmp_png = os.path.join(tempfile.gettempdir(), f"baize_sub_{s.id}_{idx_sub}.png")
                _render_subtitle_png(s, W, H, tmp_png)
                if os.path.exists(tmp_png):
                    sub_inp = new_input(tmp_png, 0.0, dur, is_image=True)
                    ol_lbl = new_label("subov")
                    fil.append(f"[{base}][{sub_inp}:v]overlay=enable='between(t,{st:.6f},{et:.6f})':format=auto[{ol_lbl}];")
                    base = ol_lbl

    # ---------- audio: cut-resolve per track, concat gaps, amix across tracks ----------
    audio_map: str | None = None
    a_track_streams: list[str] = []
    for ti in sorted(aud):
        cuts = _resolve_cuts(aud[ti], start, end)
        if not cuts:
            continue
        seg_outs: list[str] = []
        cursor = start
        for c, t0, t1 in cuts:
            gap = t0 - cursor
            if gap > 1e-3:
                gl = new_label("sil")
                fil.append(
                    f"anullsrc=r=48000:cl=stereo:d={gap:.6f},"
                    f"asetpts=N/SR/TB[{gl}];"
                )
                seg_outs.append(gl)
            m = media_of(c)
            vol = min(max(c.volume, 0.0), 1.0)
            c_speed = getattr(c, "speed", 1.0)
            seg_len = t1 - t0
            src_len = seg_len * c_speed
            inp = new_input(m.path, clip_src_time(c, t0), src_len)
            al = new_label("a")
            atempo_vf = _build_atempo_filter(c_speed)
            fil.append(
                f"[{inp}:a]aresample=48000{atempo_vf},volume={vol:.4f}[{al}];"
            )
            seg_outs.append(al)
            cursor = t1
        if play_len - (cursor - start) > 1e-3:
            gl = new_label("sil")
            fil.append(
                f"anullsrc=r=48000:cl=stereo:d={play_len - (cursor - start):.6f},"
                f"asetpts=N/SR/TB[{gl}];"
            )
            seg_outs.append(gl)
        tl = new_label("at")
        if len(seg_outs) > 1:
            srcs = "".join(f"[{s}]" for s in seg_outs)
            fil.append(f"{srcs}concat=n={len(seg_outs)}:v=0:a=1[{tl}];")
        else:
            fil.append(f"[{seg_outs[0]}]anull[{tl}];")
        a_track_streams.append(tl)

    if a_track_streams:
        if len(a_track_streams) > 1:
            mix = new_label("amix")
            srcs = "".join(f"[{s}]" for s in a_track_streams)
            fil.append(
                f"{srcs}amix=inputs={len(a_track_streams)}:normalize=0:"
                f"duration=longest,atrim=0:{play_len:.6f}[{mix}];"
            )
            audio_map = mix
        else:
            audio_map = a_track_streams[0]

    cmd += ["-filter_complex", "".join(fil)]
    cmd += ["-map", f"[{base}]"]
    if audio_map is not None:
        cmd += ["-map", f"[{audio_map}]", "-c:a", audio_codec, "-b:a", audio_bitrate, "-ar", "48000"]
    cmd += [
        "-r", f"{out_fps:.3f}",
        "-c:v", video_codec, "-preset", "medium", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
    ]
    if video_bitrate:
        cmd += ["-b:v", video_bitrate]
    else:
        cmd += ["-crf", str(crf)]
    cmd.append(output)
    return cmd


def export_video(
    project,
    output: str,
    *,
    start: float = 0.0,
    end: float | None = None,
    fps: float | None = None,
    resolution: tuple[int, int] | None = None,
    scale_mode: str = "fit",
    video_bitrate: str = "",
    audio_bitrate: str = "192k",
    crf: int = 18,
    progress_hook=None,
) -> str:
    """Build and run the export command; returns output path or raises."""
    cmd = build_ffmpeg_cmd(
        project, output, start=start, end=end, fps=fps,
        resolution=resolution, scale_mode=scale_mode,
        video_bitrate=video_bitrate, audio_bitrate=audio_bitrate, crf=crf,
    )
    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    tail: list[str] = []
    for line in proc.stderr:
        if progress_hook is not None:
            progress_hook(line)
        tail.append(line)
        if len(tail) > 40:
            tail.pop(0)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"Export failed:\n{''.join(tail[-20:])}")
    return output


def parse_ffmpeg_progress(line: str) -> dict | None:
    """Parse a `-stats` stderr line into {frame, fps, time, size, bitrate}."""
    import re
    m = re.search(r"frame=\s*(\d+)", line)
    f = re.search(r"time=\s*(\d+):(\d+):(\d+\.?\d*)", line)
    b = re.search(r"bitrate=\s*([\d.]+)kbits/s", line)
    sz = re.search(r"size=\s*(\d+\w+)", line)
    out: dict = {}
    if not m or not f:
        return None
    out["frame"] = int(m.group(1))
    hs, ms, ss = f.group(1), f.group(2), f.group(3)
    out["time"] = int(hs) * 3600 + int(ms) * 60 + float(ss)
    if b:
        out["bitrate"] = float(b.group(1))
    if sz:
        out["size"] = sz.group(1)
    return out


def _build_atempo_filter(speed: float) -> str:
    if abs(speed - 1.0) < 1e-3:
        return ""
    filters = []
    rem = speed
    while rem > 2.0:
        filters.append("atempo=2.0")
        rem /= 2.0
    while rem < 0.5:
        filters.append("atempo=0.5")
        rem /= 0.5
    if abs(rem - 1.0) >= 1e-3:
        filters.append(f"atempo={rem:.4f}")
    return ("," + ",".join(filters)) if filters else ""


def ffmpeg_version() -> str:
    out = subprocess.run([FFMPEG, "-version"], capture_output=True, text=True, timeout=30)
    return out.stdout.splitlines()[0] if out.stdout else "ffmpeg"


def _build_clip_transition_vf(c, seg_dur: float) -> str:
    filters = []
    in_dur = getattr(c, "fade_in_duration", 0.0)
    in_type = getattr(c, "fade_in_type", "fade")
    if in_dur > 0:
        dur = min(in_dur, seg_dur)
        if in_type == "white":
            filters.append(f"fade=t=in:st=0:d={dur:.3f}:color=white")
        elif in_type == "black":
            filters.append(f"fade=t=in:st=0:d={dur:.3f}:color=black")
        else:
            filters.append(f"fade=t=in:st=0:d={dur:.3f}")

    out_dur = getattr(c, "fade_out_duration", 0.0)
    out_type = getattr(c, "fade_out_type", "fade")
    if out_dur > 0:
        dur = min(out_dur, seg_dur)
        st = max(0.0, seg_dur - dur)
        if out_type == "white":
            filters.append(f"fade=t=out:st={st:.3f}:d={dur:.3f}:color=white")
        elif out_type == "black":
            filters.append(f"fade=t=out:st={st:.3f}:d={dur:.3f}:color=black")
        else:
            filters.append(f"fade=t=out:st={st:.3f}:d={dur:.3f}")

    return ("," + ",".join(filters)) if filters else ""


def process_frame_transition(arr: np.ndarray, clip, current_time: float) -> np.ndarray:
    """Apply active entry/exit transition effect to decoded numpy frame."""
    if arr is None or arr.size == 0:
        return arr

    in_dur = getattr(clip, "fade_in_duration", 0.0)
    in_type = getattr(clip, "fade_in_type", "fade")
    clip_elapsed = current_time - clip.position
    if in_dur > 0 and 0 <= clip_elapsed < in_dur:
        progress = max(0.0, min(1.0, clip_elapsed / in_dur))
        arr = _apply_transition_effect(arr, in_type, progress, is_entry=True)

    out_dur = getattr(clip, "fade_out_duration", 0.0)
    out_type = getattr(clip, "fade_out_type", "fade")
    clip_remaining = clip.end - current_time
    if out_dur > 0 and 0 <= clip_remaining < out_dur:
        progress = max(0.0, min(1.0, clip_remaining / out_dur))
        arr = _apply_transition_effect(arr, out_type, progress, is_entry=False)

    return arr


def _apply_transition_effect(arr: np.ndarray, trans_type: str, progress: float, is_entry: bool) -> np.ndarray:
    if progress >= 0.999:
        return arr
    if progress <= 0.001:
        if trans_type == "white":
            return np.full_like(arr, 255)
        return np.zeros_like(arr)

    arr_f = arr.astype(np.float32)
    h, w = arr.shape[:2]

    if trans_type in ("fade", "black"):
        arr_f = arr_f * progress
    elif trans_type == "white":
        arr_f = (1.0 - progress) * 255.0 + progress * arr_f
    elif trans_type == "wipe_right":
        cutoff = int(w * progress)
        arr_f[:, cutoff:, :] = 0
    elif trans_type == "wipe_left":
        cutoff = int(w * (1.0 - progress))
        arr_f[:, :cutoff, :] = 0
    elif trans_type == "wipe_up":
        cutoff = int(h * (1.0 - progress))
        arr_f[:cutoff, :, :] = 0
    elif trans_type == "wipe_down":
        cutoff = int(h * progress)
        arr_f[cutoff:, :, :] = 0
    elif trans_type == "slide_right":
        offset = int(w * (1.0 - progress))
        shifted = np.zeros_like(arr_f)
        if offset < w:
            shifted[:, offset:] = arr_f[:, :w - offset]
        arr_f = shifted
    elif trans_type == "slide_left":
        offset = int(w * (1.0 - progress))
        shifted = np.zeros_like(arr_f)
        if offset < w:
            shifted[:, :w - offset] = arr_f[:, offset:]
        arr_f = shifted
    elif trans_type == "slide_up":
        offset = int(h * (1.0 - progress))
        shifted = np.zeros_like(arr_f)
        if offset < h:
            shifted[:h - offset, :] = arr_f[offset:, :]
        arr_f = shifted
    elif trans_type == "slide_down":
        offset = int(h * (1.0 - progress))
        shifted = np.zeros_like(arr_f)
        if offset < h:
            shifted[offset:, :] = arr_f[:h - offset, :]
        arr_f = shifted
    elif trans_type == "zoom_in":
        scale = max(0.02, progress)
        nh, nw = max(1, int(h * scale)), max(1, int(w * scale))
        sub_y = np.linspace(0, h - 1, nh, dtype=int)
        sub_x = np.linspace(0, w - 1, nw, dtype=int)
        scaled = arr_f[np.ix_(sub_y, sub_x)]
        shifted = np.zeros_like(arr_f)
        y_start = (h - nh) // 2
        x_start = (w - nw) // 2
        shifted[y_start:y_start + nh, x_start:x_start + nw] = scaled
        arr_f = shifted
    elif trans_type == "circle_crop":
        cy, cx = h / 2.0, w / 2.0
        max_r = np.sqrt(cx * cx + cy * cy) * progress
        y_idx, x_idx = np.ogrid[:h, :w]
        dist = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)
        arr_f[dist > max_r] = 0

    return np.clip(arr_f, 0, 255).astype(np.uint8)


def _build_drawtext_filters(s, W: int, H: int) -> list[str]:
    font_size = max(12, int(s.font_size * (H / 720.0)))
    st = max(0.0, s.position)
    et = max(st, s.end)
    effect = getattr(s, "animation_effect", "none")
    anim_dur = getattr(s, "animation_duration", 0.5)

    base_x = "(w-text_w)/2"
    base_y = "h-text_h-h*0.08"

    if s.alignment == "top_center":
        base_x = "(w-text_w)/2"
        base_y = "h*0.08"
    elif s.alignment == "center":
        base_x = "(w-text_w)/2"
        base_y = "(h-text_h)/2"
    elif s.alignment == "bottom_left":
        base_x = "40"
        base_y = "h-text_h-h*0.08"
    elif s.alignment == "bottom_right":
        base_x = "w-text_w-40"
        base_y = "h-text_h-h*0.08"

    color_hex = s.font_color.replace("#", "0x")
    border_hex = s.stroke_color.replace("#", "0x")

    def _make_opts(txt: str, enable_expr: str, y_expr: str, alpha_expr: str = "") -> str:
        escaped_text = txt.replace(":", "\\:").replace("'", "'\\\\''").replace("\n", "\\n")
        opts = [
            f"text='{escaped_text}'",
            f"fontsize={font_size}",
            f"fontcolor={color_hex}",
            f"x={base_x}",
            f"y={y_expr}",
            f"enable='{enable_expr}'"
        ]
        if alpha_expr:
            opts.append(f"alpha='{alpha_expr}'")
        if s.stroke_width > 0:
            opts.append(f"borderw={s.stroke_width}")
            opts.append(f"bordercolor={border_hex}")
        if s.bg_color:
            opts.append("box=1")
            opts.append("boxcolor=0x000000@0.5")
        return "drawtext=" + ":".join(opts)

    filters = []

    if effect == "typewriter":
        total_chars = len(s.text)
        if total_chars > 0:
            type_dur = max(0.1, min((et - st) * 0.8, total_chars * 0.08, anim_dur * 2))
            char_dur = type_dur / total_chars
            for i in range(1, total_chars + 1):
                step_st = st + (i - 1) * char_dur
                step_et = st + i * char_dur if i < total_chars else et
                txt = s.text[:i]
                enable_str = f"between(t,{step_st:.3f},{step_et:.3f})"
                alpha_str = ""
                if i == total_chars and anim_dur > 0:
                    alpha_str = f"if(gt(t,{et:.3f}-{anim_dur:.3f}),({et:.3f}-t)/{anim_dur:.3f},1)"
                filters.append(_make_opts(txt, enable_str, base_y, alpha_str))
        else:
            filters.append(_make_opts(s.text, f"between(t,{st:.3f},{et:.3f})", base_y))

    elif effect == "fly":
        y_expr = f"({base_y})+if(lt(t,{st:.3f}+{anim_dur:.3f}),(1-(t-{st:.3f})/{anim_dur:.3f})*(h*0.12),if(gt(t,{et:.3f}-{anim_dur:.3f}),(1-({et:.3f}-t)/{anim_dur:.3f})*(h*0.12),0))"
        alpha_expr = f"if(lt(t,{st:.3f}+{anim_dur:.3f}),(t-{st:.3f})/{anim_dur:.3f},if(gt(t,{et:.3f}-{anim_dur:.3f}),({et:.3f}-t)/{anim_dur:.3f},1))"
        filters.append(_make_opts(s.text, f"between(t,{st:.3f},{et:.3f})", y_expr, alpha_expr))

    elif effect == "fade":
        alpha_expr = f"if(lt(t,{st:.3f}+{anim_dur:.3f}),(t-{st:.3f})/{anim_dur:.3f},if(gt(t,{et:.3f}-{anim_dur:.3f}),({et:.3f}-t)/{anim_dur:.3f},1))"
        filters.append(_make_opts(s.text, f"between(t,{st:.3f},{et:.3f})", base_y, alpha_expr))

    else: # none
        filters.append(_make_opts(s.text, f"between(t,{st:.3f},{et:.3f})", base_y))

    return filters


def extract_audio_for_asr(project, output_wav: str, start: float = 0.0, end: float | None = None) -> str:
    """Extract 16kHz mono WAV audio from project timeline for speech recognition."""
    timeline_end = project.duration()
    end = timeline_end if end is None or end <= 0 else min(end, timeline_end)
    play_len = max(end - start, 0.0)
    if play_len <= 0:
        raise ValueError("Selected range has zero duration")

    aud: dict[int, list] = {}
    media_by_id = {m.id: m for m in project.media}
    for tr in project.audio_tracks:
        if not tr.enabled or tr.muted:
            continue
        clips = [c for c in tr.clips
                 if c.media_id in media_by_id and media_by_id[c.media_id].has_audio]
        if clips:
            aud[tr.index] = clips

    if not aud:
        for tr in project.video_tracks:
            if not tr.enabled:
                continue
            clips = [c for c in tr.clips
                     if c.media_id in media_by_id and media_by_id[c.media_id].has_audio]
            if clips:
                aud[tr.index] = clips

    if not aud:
        raise ValueError("No audio content found on timeline")

    cmd: list[str] = [FFMPEG, "-y", "-v", "error"]
    fil: list[str] = []
    n_inputs = 0
    used_labels: set[str] = set()

    def new_input(path: str, src_time: float, duration: float) -> int:
        nonlocal n_inputs
        cmd.extend(["-ss", f"{src_time:.6f}", "-t", f"{duration:.6f}", "-i", path])
        idx = n_inputs
        n_inputs += 1
        return idx

    def new_label(prefix: str) -> str:
        i = len(used_labels)
        lbl = f"{prefix}{i}"
        while lbl in used_labels:
            i += 1
            lbl = f"{prefix}{i}"
        used_labels.add(lbl)
        return lbl

    a_track_streams: list[str] = []
    for ti in sorted(aud):
        cuts = _resolve_cuts(aud[ti], start, end)
        if not cuts:
            continue
        seg_outs: list[str] = []
        cursor = start
        for c, t0, t1 in cuts:
            gap = t0 - cursor
            if gap > 1e-3:
                gl = new_label("sil")
                fil.append(f"anullsrc=r=16000:cl=mono:d={gap:.6f},asetpts=N/SR/TB[{gl}];")
                seg_outs.append(gl)
            m = media_by_id[c.media_id]
            vol = min(max(c.volume, 0.0), 1.0)
            inp = new_input(m.path, c.trim_in + (t0 - c.position), t1 - t0)
            al = new_label("a")
            fil.append(f"[{inp}:a]aresample=16000,aformat=sample_fmts=s16:channel_layouts=mono,volume={vol:.4f}[{al}];")
            seg_outs.append(al)
            cursor = t1
        if play_len - (cursor - start) > 1e-3:
            gl = new_label("sil")
            fil.append(f"anullsrc=r=16000:cl=mono:d={play_len - (cursor - start):.6f},asetpts=N/SR/TB[{gl}];")
            seg_outs.append(gl)
        tl = new_label("at")
        if len(seg_outs) > 1:
            srcs = "".join(f"[{s}]" for s in seg_outs)
            fil.append(f"{srcs}concat=n={len(seg_outs)}:v=0:a=1[{tl}];")
        else:
            fil.append(f"[{seg_outs[0]}]anull[{tl}];")
        a_track_streams.append(tl)

    if not a_track_streams:
        raise ValueError("No audio content to extract")

    if len(a_track_streams) > 1:
        mix = new_label("amix")
        srcs = "".join(f"[{s}]" for s in a_track_streams)
        fil.append(f"{srcs}amix=inputs={len(a_track_streams)}:normalize=0:duration=longest,atrim=0:{play_len:.6f}[{mix}];")
        audio_map = mix
    else:
        audio_map = a_track_streams[0]

    cmd += ["-filter_complex", "".join(fil), "-map", f"[{audio_map}]", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", output_wav]
    _run(cmd)
    return output_wav


def apply_object_removal_inpainting(
    arr: np.ndarray, masks: list[dict]
) -> np.ndarray:
    """Apply OpenCV Telea/Navier-Stokes Content-Aware Inpainting to remove target object masks."""
    if arr is None or arr.size == 0 or not masks:
        return arr

    h, w, c = arr.shape
    try:
        import cv2
        binary_mask = np.zeros((h, w), dtype=np.uint8)
        step = max(1, len(masks) // 80)
        for m in masks[::step]:
            cx = int(m.get("x", 0.5) * w)
            cy = int(m.get("y", 0.5) * h)
            r = max(3, int(m.get("radius", 0.05) * min(w, h)))
            cv2.circle(binary_mask, (cx, cy), r, 255, -1)

        if np.count_nonzero(binary_mask) == 0:
            return arr

        has_alpha = (c == 4)
        rgb = arr[:, :, :3]

        inpainted = cv2.inpaint(rgb, binary_mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)

        if has_alpha:
            out = arr.copy()
            out[:, :, :3] = inpainted
            return out
        return inpainted
    except Exception:
        return arr


def track_clip_object_masks(
    media_path: str, initial_masks: list[dict], trim_in: float, duration: float, target_w: int = 640, target_h: int = 360
) -> list[dict]:
    """Track painted object masks across video clip frames using OpenCV Farneback Optical Flow."""
    if not initial_masks or not os.path.exists(media_path):
        return initial_masks

    try:
        import cv2
        cap = cv2.VideoCapture(media_path)
        if not cap.isOpened():
            return initial_masks

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        start_frame = int(trim_in * fps)
        total_frames = int(min(duration, 10.0) * fps)  # Track up to 10 seconds per run

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        ret, prev_frame = cap.read()
        if not ret or prev_frame is None:
            cap.release()
            return initial_masks

        prev_frame = cv2.resize(prev_frame, (target_w, target_h))
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

        tracked_masks = [dict(m) for m in initial_masks]
        current_coords = [[m.get("x", 0.5) * target_w, m.get("y", 0.5) * target_h, m.get("radius", 0.05) * min(target_w, target_h)] for m in initial_masks]

        frame_idx = 0
        while frame_idx < total_frames and cap.isOpened():
            ret, curr_frame = cap.read()
            if not ret or curr_frame is None:
                break
            curr_frame = cv2.resize(curr_frame, (target_w, target_h))
            curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )

            for i, (cx, cy, r) in enumerate(current_coords):
                x_min = max(0, int(cx - r))
                x_max = min(target_w, int(cx + r))
                y_min = max(0, int(cy - r))
                y_max = min(target_h, int(cy + r))

                if x_max > x_min and y_max > y_min:
                    dx = np.mean(flow[y_min:y_max, x_min:x_max, 0])
                    dy = np.mean(flow[y_min:y_max, x_min:x_max, 1])
                    if not np.isnan(dx) and not np.isnan(dy):
                        current_coords[i][0] = max(0.0, min(float(target_w), cx + dx))
                        current_coords[i][1] = max(0.0, min(float(target_h), cy + dy))
                        tracked_masks.append({
                            "x": current_coords[i][0] / target_w,
                            "y": current_coords[i][1] / target_h,
                            "radius": initial_masks[i].get("radius", 0.05)
                        })

            prev_gray = curr_gray
            frame_idx += 1

        cap.release()
        return tracked_masks
    except Exception:
        return initial_masks


def apply_chroma_key(
    rgba_frame: np.ndarray, key_color_hex: str = "#00FF00",
    similarity: float = 0.3, smoothness: float = 0.1
) -> np.ndarray:
    """Apply Chroma Keying (Green/Blue Screen Keyer) onto an HxWx4 RGBA array.
    Modifies the alpha channel (4th channel) based on color distance."""
    if rgba_frame is None or rgba_frame.size == 0 or rgba_frame.shape[2] < 4:
        return rgba_frame

    hex_clean = key_color_hex.lstrip("#")
    if len(hex_clean) == 6:
        r_target = int(hex_clean[0:2], 16)
        g_target = int(hex_clean[2:4], 16)
        b_target = int(hex_clean[4:6], 16)
    else:
        r_target, g_target, b_target = 0, 255, 0

    target = np.array([r_target, g_target, b_target], dtype=np.float32) / 255.0
    rgb = rgba_frame[:, :, :3].astype(np.float32) / 255.0

    dist = np.linalg.norm(rgb - target, axis=2)

    thresh = similarity * 1.732
    smooth = max(smoothness * 1.732, 1e-4)

    matte = np.clip((dist - thresh) / smooth, 0.0, 1.0)

    out = rgba_frame.copy()
    out[:, :, 3] = (out[:, :, 3].astype(np.float32) * matte).astype(np.uint8)
    return out


def process_color_correction(
    arr: np.ndarray, brightness: float = 0.0, contrast: float = 1.0, saturation: float = 1.0
) -> np.ndarray:
    """Apply brightness, contrast, and saturation adjustments to an uint8 image array."""
    if arr is None or arr.size == 0:
        return arr
    if abs(brightness) < 1e-4 and abs(contrast - 1.0) < 1e-4 and abs(saturation - 1.0) < 1e-4:
        return arr

    out = arr.copy()
    rgb = out[:, :, :3].astype(np.float32)

    if abs(brightness) >= 1e-4:
        rgb += brightness * 255.0

    if abs(contrast - 1.0) >= 1e-4:
        rgb = (rgb - 128.0) * contrast + 128.0

    if abs(saturation - 1.0) >= 1e-4:
        gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
        gray_3ch = np.stack([gray, gray, gray], axis=2)
        rgb = gray_3ch + (rgb - gray_3ch) * saturation

    out[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    return out


def process_blur_focus(
    arr: np.ndarray, focus_mode: str = "none", blur_amount: float = 0.0
) -> np.ndarray:
    """Apply blur and focus effects (Gaussian Blur, Center Focus, Tilt Shift) to an uint8 image array."""
    if arr is None or arr.size == 0 or (focus_mode in ("none", "", None) and blur_amount <= 0):
        return arr

    h, w, c = arr.shape
    out = arr.copy()
    amt = max(1.0, blur_amount if blur_amount > 0 else 6.0)
    k_size = max(3, int(amt) | 1)
    half_k = k_size // 2

    padded = np.pad(out[:, :, :3], ((half_k, half_k), (half_k, half_k), (0, 0)), mode="edge")
    blur_rgb = np.zeros((h, w, 3), dtype=np.float32)
    step = max(1, k_size // 3)
    count = 0
    for dy in range(0, k_size, step):
        for dx in range(0, k_size, step):
            blur_rgb += padded[dy:dy+h, dx:dx+w, :3].astype(np.float32)
            count += 1
    blur_rgb /= max(1, count)

    if focus_mode == "gaussian_blur" or (focus_mode == "none" and blur_amount > 0):
        out[:, :, :3] = np.clip(blur_rgb, 0, 255).astype(np.uint8)

    elif focus_mode == "center_focus":
        cy, cx = h / 2.0, w / 2.0
        max_dist = np.sqrt(cx * cx + cy * cy)
        y_idx, x_idx = np.ogrid[:h, :w]
        dist = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)
        blur_mask = np.clip((dist / (max_dist * 0.45)) ** 1.5, 0.0, 1.0)
        blur_mask = np.expand_dims(blur_mask, axis=2)
        blended = out[:, :, :3].astype(np.float32) * (1.0 - blur_mask) + blur_rgb * blur_mask
        out[:, :, :3] = np.clip(blended, 0, 255).astype(np.uint8)

    elif focus_mode == "tilt_shift":
        y_idx, _ = np.ogrid[:h, :w]
        cy = h / 2.0
        dist_y = np.abs(y_idx - cy)
        blur_mask = np.clip((dist_y / (h * 0.25)) ** 2, 0.0, 1.0)
        blur_mask = np.expand_dims(blur_mask, axis=2)
        blended = out[:, :, :3].astype(np.float32) * (1.0 - blur_mask) + blur_rgb * blur_mask
        out[:, :, :3] = np.clip(blended, 0, 255).astype(np.uint8)

    return out


def process_video_effect(arr: np.ndarray, fx_id: str, current_time: float = 0.0) -> np.ndarray:
    """Apply preset video effect filter to an HxWx3 or HxWx4 uint8 numpy array."""
    if arr is None or arr.size == 0 or fx_id in ("none", "", None):
        return arr

    h, w, c = arr.shape
    out = arr.copy()
    rgb = out[:, :, :3].astype(np.float32)

    if fx_id == "explosion":
        period = 1.2
        phase = max(0.0, min(1.0, (current_time % period) / period))
        cy, cx = h / 2.0, w / 2.0
        max_dist = np.sqrt(cx * cx + cy * cy)
        r = phase * max_dist * 0.95
        y_idx, x_idx = np.ogrid[:h, :w]
        dist = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)

        center_flash = max(0.0, 1.0 - phase / 0.3) * np.clip(1.0 - (dist / (max_dist * 0.3)), 0.0, 1.0)
        center_flash = np.expand_dims(center_flash, axis=2)

        ring_w = 40.0 + phase * 60.0
        ring = np.exp(-((dist - r) / ring_w) ** 2) * (1.0 - phase * 0.6)
        ring = np.expand_dims(ring, axis=2)

        fire_rgb = np.zeros_like(rgb)
        fire_rgb[:, :, 0] = 255.0
        fire_rgb[:, :, 1] = 140.0
        fire_rgb[:, :, 2] = 30.0

        rgb = rgb * (1.0 + ring * 0.5) + fire_rgb * ring * 0.8 + center_flash * 220.0
        out[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)

    elif fx_id == "flash":
        period = 0.8
        phase = max(0.0, min(1.0, (current_time % period) / period))
        flash_int = max(0.0, 1.0 - phase / 0.25) ** 2
        cy, cx = h / 2.0, w / 2.0
        y_idx, x_idx = np.ogrid[:h, :w]
        dist = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)
        max_dist = np.sqrt(cx * cx + cy * cy)
        vign = np.clip(1.0 - (dist / max_dist) * 0.4, 0.6, 1.0)
        vign = np.expand_dims(vign, axis=2)

        flash_rgb = rgb * 1.3 + flash_int * 220.0 * vign
        out[:, :, :3] = np.clip(flash_rgb, 0, 255).astype(np.uint8)

    elif fx_id == "particles":
        n_p = 60
        part_layer = np.zeros((h, w, 3), dtype=np.float32)

        for i in range(n_p):
            seed = (i + 1) * 1013
            px0 = (seed * 37) % w
            py0 = (seed * 59) % h
            speed = 35.0 + (seed % 30)
            rad = float(2 + (seed % 3))
            R = int(rad * 4.0)

            py = int((py0 - current_time * speed) % h)
            px = int((px0 + np.sin(current_time * 2.5 + i) * 16.0) % w)

            shine = 0.6 + 0.4 * np.sin(current_time * 5.0 + i * 1.7)

            x_min = max(0, px - R)
            x_max = min(w, px + R + 1)
            y_min = max(0, py - R)
            y_max = min(h, py + R + 1)

            if x_max > x_min and y_max > y_min:
                y_grid, x_grid = np.ogrid[y_min:y_max, x_min:x_max]
                dist_p = np.sqrt((x_grid - px) ** 2 + (y_grid - py) ** 2)
                glow = np.clip((1.0 - dist_p / (rad * 2.5)) ** 2, 0.0, 1.0) * shine

                part_layer[y_min:y_max, x_min:x_max, 0] += glow * 255.0
                part_layer[y_min:y_max, x_min:x_max, 1] += glow * 215.0
                part_layer[y_min:y_max, x_min:x_max, 2] += glow * 60.0

        rgb = rgb + part_layer * 0.95
        out[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)

    elif fx_id == "cyber_particles":
        n_p = 60
        part_layer = np.zeros((h, w, 3), dtype=np.float32)

        for i in range(n_p):
            seed = (i + 1) * 709
            px0 = (seed * 43) % w
            py0 = (seed * 71) % h
            speed = 40.0 + (seed % 35)
            rad = float(2 + (seed % 3))
            R = int(rad * 4.0)

            py = int((py0 - current_time * speed) % h)
            px = int((px0 + np.cos(current_time * 3.0 + i) * 20.0) % w)

            shine = 0.5 + 0.5 * np.sin(current_time * 6.0 + i)

            x_min = max(0, px - R)
            x_max = min(w, px + R + 1)
            y_min = max(0, py - R)
            y_max = min(h, py + R + 1)

            if x_max > x_min and y_max > y_min:
                y_grid, x_grid = np.ogrid[y_min:y_max, x_min:x_max]
                dist_p = np.sqrt((x_grid - px) ** 2 + (y_grid - py) ** 2)
                glow = np.clip((1.0 - dist_p / (rad * 2.5)) ** 2, 0.0, 1.0) * shine

                if i % 2 == 0:
                    part_layer[y_min:y_max, x_min:x_max, 1] += glow * 240.0
                    part_layer[y_min:y_max, x_min:x_max, 2] += glow * 255.0
                else:
                    part_layer[y_min:y_max, x_min:x_max, 0] += glow * 255.0
                    part_layer[y_min:y_max, x_min:x_max, 2] += glow * 255.0

        rgb = rgb * 1.1 + part_layer * 0.90
        out[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)

    elif fx_id == "warm_film":
        rgb[:, :, 0] *= 1.15
        rgb[:, :, 1] *= 1.05
        rgb[:, :, 2] *= 0.85
        rgb = (rgb - 128.0) * 1.15 + 128.0
        out[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)

    elif fx_id == "cool_cyber":
        rgb[:, :, 0] *= 0.80
        rgb[:, :, 1] *= 1.10
        rgb[:, :, 2] *= 1.30
        rgb = (rgb - 128.0) * 1.20 + 128.0
        out[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)

    elif fx_id == "teal_orange":
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        r_new = np.where(lum > 128, r * 1.2, r * 0.8)
        g_new = g * 1.0
        b_new = np.where(lum > 128, b * 0.8, b * 1.25)
        out[:, :, 0] = np.clip(r_new, 0, 255).astype(np.uint8)
        out[:, :, 1] = np.clip(g_new, 0, 255).astype(np.uint8)
        out[:, :, 2] = np.clip(b_new, 0, 255).astype(np.uint8)

    elif fx_id == "center_focus":
        return process_blur_focus(arr, "center_focus", 6.0)

    elif fx_id == "tilt_shift":
        return process_blur_focus(arr, "tilt_shift", 8.0)

    elif fx_id == "grayscale":
        gray = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]).astype(np.uint8)
        out[:, :, 0] = gray
        out[:, :, 1] = gray
        out[:, :, 2] = gray

    elif fx_id == "sepia":
        r = 0.393 * rgb[:, :, 0] + 0.769 * rgb[:, :, 1] + 0.189 * rgb[:, :, 2]
        g = 0.349 * rgb[:, :, 0] + 0.686 * rgb[:, :, 1] + 0.168 * rgb[:, :, 2]
        b = 0.272 * rgb[:, :, 0] + 0.534 * rgb[:, :, 1] + 0.131 * rgb[:, :, 2]
        out[:, :, 0] = np.clip(r, 0, 255).astype(np.uint8)
        out[:, :, 1] = np.clip(g, 0, 255).astype(np.uint8)
        out[:, :, 2] = np.clip(b, 0, 255).astype(np.uint8)

    elif fx_id == "invert":
        out[:, :, :3] = 255 - out[:, :, :3]

    elif fx_id == "vivid":
        out_vivid = (rgb - 128.0) * 1.35 + 128.0
        out[:, :, :3] = np.clip(out_vivid, 0, 255).astype(np.uint8)

    elif fx_id == "blur":
        return process_blur_focus(arr, "gaussian_blur", 5.0)

    elif fx_id == "mirror_h":
        out[:, :, :3] = np.fliplr(out[:, :, :3])

    elif fx_id == "vignette":
        cy, cx = h / 2.0, w / 2.0
        max_dist = np.sqrt(cx * cx + cy * cy)
        y_idx, x_idx = np.ogrid[:h, :w]
        dist = np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)
        vignette_mask = np.clip(1.0 - (dist / max_dist) ** 1.8, 0.25, 1.0)
        vignette_mask = np.expand_dims(vignette_mask, axis=2)
        out[:, :, :3] = np.clip(rgb * vignette_mask, 0, 255).astype(np.uint8)

    return out