from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

import sys
from ..models.media import SubtitleClip
from . import ffmpeg as fx


def _load_whisper_module():
    try:
        import whisper
        return whisper
    except ImportError:
        pass

    extra_paths = [
        "/Users/james/anaconda3/lib/python3.13/site-packages",
        "/Users/james/anaconda3/lib/python3.12/site-packages",
        "/Users/james/anaconda3/lib/python3.11/site-packages",
        "/opt/homebrew/lib/python3.14/site-packages",
        "/opt/homebrew/lib/python3.13/site-packages",
        "/opt/homebrew/lib/python3.12/site-packages",
    ]
    for p in extra_paths:
        if os.path.exists(p) and p not in sys.path:
            sys.path.insert(0, p)
            try:
                import whisper
                return whisper
            except ImportError:
                pass

    import subprocess
    cmd = [sys.executable, "-m", "pip", "install", "--break-system-packages", "openai-whisper", "SpeechRecognition"]
    subprocess.check_call(cmd)
    import whisper
    return whisper


class AutoSubtitleThread(QThread):
    progress_changed = pyqtSignal(int, str)  # (percent 0-100, message)
    finished_success = pyqtSignal(list)       # list of SubtitleClip
    failed_error = pyqtSignal(str)           # error message

    def __init__(
        self,
        project,
        model_name: str = "base",
        language: str = "auto",
        start_time: float = 0.0,
        end_time: float | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.project = project
        self.model_name = model_name
        self.language = language if language != "auto" else None
        self.start_time = start_time
        self.end_time = end_time
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        wav_path = ""
        try:
            self.progress_changed.emit(10, "Extracting audio from timeline...")
            tmp_dir = Path(tempfile.gettempdir()) / "baize_asr"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            wav_path = str(tmp_dir / f"asr_{os.getpid()}_{id(self)}.wav")

            fx.extract_audio_for_asr(
                self.project, wav_path, start=self.start_time, end=self.end_time
            )

            if self._cancelled:
                return

            self.progress_changed.emit(30, f"Loading AI Speech Model '{self.model_name}'...")
            whisper = _load_whisper_module()

            model = whisper.load_model(self.model_name)

            if self._cancelled:
                return

            self.progress_changed.emit(60, "Transcribing speech into text...")
            transcribe_kwargs = {}
            if self.language:
                transcribe_kwargs["language"] = self.language

            result = model.transcribe(wav_path, **transcribe_kwargs)

            if self._cancelled:
                return

            self.progress_changed.emit(90, "Processing subtitle timing...")
            segments = result.get("segments", [])
            clips: list[SubtitleClip] = []

            for seg in segments:
                t_start = float(seg.get("start", 0.0)) + self.start_time
                t_end = float(seg.get("end", 0.0)) + self.start_time
                text = str(seg.get("text", "")).strip()

                if text and t_end > t_start:
                    clips.append(
                        SubtitleClip(
                            text=text,
                            position=t_start,
                            duration=max(0.5, t_end - t_start),
                        )
                    )

            self.progress_changed.emit(100, f"Done! Generated {len(clips)} subtitles.")
            self.finished_success.emit(clips)

        except Exception as exc:
            self.failed_error.emit(str(exc))
        finally:
            if wav_path and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass
