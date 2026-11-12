from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import (
    Qt, QTimer, QThread, QPropertyAnimation, QEasingCurve,
    QRectF, QPointF, pyqtSignal, pyqtSlot,
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QPainterPath, QColor, QFont, QPen,
    QBrush, QLinearGradient, QMouseEvent,
)
from PyQt6.QtWidgets import QWidget, QApplication

from ..core.updater import (
    RELEASES_URL, UpdateCheckResult, get_current_version, check_github_updates,
)
from ..i18n import tr

USER_SPECIFIED_SPLASH_PATH = "/Users/james/Downloads/Gemini_Generated_Image_7cmr4q7cmr4q7cmr.jpeg"
REPO_ROOT = Path(__file__).resolve().parents[2]
FALLBACK_SPLASH_PATHS = [
    Path(USER_SPECIFIED_SPLASH_PATH),
    REPO_ROOT / "app" / "resources" / "Gemini_Generated_Image_7cmr4q7cmr4q7cmr.jpeg",
    REPO_ROOT / "app" / "resources" / "splash.jpeg",
]


class _UpdateCheckThread(QThread):
    finished_check = pyqtSignal(object)

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self.current_version = current_version

    def run(self):
        result = check_github_updates(self.current_version, timeout=4.0)
        self.finished_check.emit(result)


class SplashScreen(QWidget):
    """Modern Startup Splash Screen featuring custom artwork, version badge,

    real-time GitHub update check, and smooth animated transition.
    """

    def __init__(self, custom_image_path: str | None = None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._version = get_current_version()
        self._image_path = self._resolve_image_path(custom_image_path)
        self._pixmap = self._load_pixmap()

        self._w = 760
        self._h = 428
        self.setFixedSize(self._w, self._h)

        self._status_text = f"🔄 {tr('Checking for updates…')}"
        self._progress_val = 0.0
        self._update_result: UpdateCheckResult | None = None
        self._min_time_passed = False
        self._check_done = False
        self._main_window = None
        self._animating_close = False

        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._on_progress_tick)
        self._progress_timer.start(25)

        self._min_timer = QTimer(self)
        self._min_timer.setSingleShot(True)
        self._min_timer.timeout.connect(self._on_min_timer)
        self._min_timer.start(1800)

        self._max_timer = QTimer(self)
        self._max_timer.setSingleShot(True)
        self._max_timer.timeout.connect(self._on_max_timeout)
        self._max_timer.start(4500)

        self._worker = _UpdateCheckThread(self._version, self)
        self._worker.finished_check.connect(self._on_update_result)
        self._worker.start()

        self._center_on_screen()

    def _resolve_image_path(self, custom: str | None) -> str:
        if custom and os.path.exists(custom):
            return custom
        for p in FALLBACK_SPLASH_PATHS:
            if p.exists():
                return str(p)
        return ""

    def _load_pixmap(self) -> QPixmap | None:
        if self._image_path and os.path.exists(self._image_path):
            pm = QPixmap(self._image_path)
            if not pm.isNull():
                return pm
        return None

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self._w) // 2
            y = geo.y() + (geo.height() - self._h) // 2
            self.move(x, y)

    @pyqtSlot()
    def _on_progress_tick(self):
        if self._progress_val < 0.90:
            self._progress_val += 0.012
        elif self._check_done and self._progress_val < 1.0:
            self._progress_val += 0.04
        self.update()

    @pyqtSlot(object)
    def _on_update_result(self, result: UpdateCheckResult):
        self._update_result = result
        self._check_done = True
        cur = result.current_version or self._version

        if result.has_update and result.latest_version:
            self._status_text = (
                f"🎉 {tr('Update Available')}: {result.latest_version} "
                f"({tr('Current')}: {cur})"
            )
        elif result.latest_version:
            self._status_text = (
                f"✅ {tr('You are already on the latest version!')} ({cur})"
            )
        else:
            self._status_text = f"✅ {tr('Ready')} ({cur})"

        self.update()
        if self._min_time_passed:
            self._finish_and_open()

    @pyqtSlot()
    def _on_min_timer(self):
        self._min_time_passed = True
        if self._check_done:
            self._finish_and_open()

    @pyqtSlot()
    def _on_max_timeout(self):
        if not self._check_done:
            self._check_done = True
            if self._update_result is None:
                self._update_result = UpdateCheckResult(current_version=self._version)
        self._min_time_passed = True
        self._finish_and_open()

    def set_main_window(self, win):
        self._main_window = win
        if self._min_time_passed and self._check_done:
            self._finish_and_open()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._finish_and_open()

    def _finish_and_open(self):
        if self._animating_close:
            return
        self._animating_close = True
        self._progress_timer.stop()
        self._min_timer.stop()
        self._max_timer.stop()

        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(350)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._anim.finished.connect(self._on_fade_finished)
        self._anim.start()

    def _on_fade_finished(self):
        if self._main_window is not None:
            if hasattr(self._main_window, "handle_splash_update_result"):
                self._main_window.handle_splash_update_result(self._update_result)
            self._main_window.show()
            self._main_window.raise_()
            self._main_window.activateWindow()
        self.close()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = float(self._w), float(self._h)
        radius = 16.0
        rect = QRectF(0.0, 0.0, w, h)

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        p.setClipPath(path)

        if self._pixmap is not None and not self._pixmap.isNull():
            p.drawPixmap(
                0, 0, int(w), int(h),
                self._pixmap.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            p.fillRect(rect, QColor(22, 25, 34))

        top_grad = QLinearGradient(0.0, 0.0, 0.0, 110.0)
        top_grad.setColorAt(0.0, QColor(10, 12, 16, 210))
        top_grad.setColorAt(0.7, QColor(10, 12, 16, 120))
        top_grad.setColorAt(1.0, QColor(10, 12, 16, 0))
        p.fillRect(QRectF(0.0, 0.0, w, 110.0), top_grad)

        bottom_h = 135.0
        bot_grad = QLinearGradient(0.0, h - bottom_h, 0.0, h)
        bot_grad.setColorAt(0.0, QColor(8, 10, 14, 0))
        bot_grad.setColorAt(0.3, QColor(8, 10, 14, 180))
        bot_grad.setColorAt(0.7, QColor(8, 10, 14, 235))
        bot_grad.setColorAt(1.0, QColor(8, 10, 14, 250))
        p.fillRect(QRectF(0.0, h - bottom_h, w, bottom_h), bot_grad)

        title_font = QFont("Helvetica", 28, QFont.Weight.Bold)
        p.setFont(title_font)
        p.setPen(QColor(0, 0, 0, 160))
        p.drawText(QRectF(29.0, 23.0, 300.0, 42.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "BaiZe")
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRectF(28.0, 22.0, 300.0, 42.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "BaiZe")

        sub_font = QFont("Helvetica", 11)
        p.setFont(sub_font)
        p.setPen(QColor(190, 205, 225, 210))
        p.drawText(QRectF(29.0, 60.0, 450.0, 22.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tr("Professional Video Editor"))

        badge_w, badge_h = 100.0, 28.0
        badge_x, badge_y = w - badge_w - 24.0, 24.0
        badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)
        p.setBrush(QColor(18, 24, 38, 220))
        p.setPen(QPen(QColor(70, 130, 200, 160), 1.0))
        p.drawRoundedRect(badge_rect, 14.0, 14.0)

        badge_font = QFont("Helvetica", 10, QFont.Weight.Bold)
        p.setFont(badge_font)
        p.setPen(QColor(140, 205, 255))
        p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, self._version)

        status_font = QFont("Helvetica", 11, QFont.Weight.Bold)
        p.setFont(status_font)
        if self._update_result and self._update_result.has_update:
            p.setPen(QColor(80, 225, 140))
        else:
            p.setPen(QColor(230, 235, 245))
        p.drawText(QRectF(28.0, h - 70.0, w - 56.0, 24.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._status_text)

        url_font = QFont("Helvetica", 9)
        p.setFont(url_font)
        p.setPen(QColor(130, 145, 170))
        p.drawText(QRectF(28.0, h - 28.0, w - 56.0, 20.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, RELEASES_URL)

        click_tip = tr("Click to continue")
        p.drawText(QRectF(28.0, h - 28.0, w - 56.0, 20.0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"• {click_tip}")

        bar_x = 28.0
        bar_y = h - 40.0
        bar_w = w - 56.0
        bar_h = 4.0
        bg_bar_rect = QRectF(bar_x, bar_y, bar_w, bar_h)
        p.setBrush(QColor(40, 48, 65, 180))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(bg_bar_rect, 2.0, 2.0)

        prog_w = max(6.0, min(bar_w, bar_w * self._progress_val))
        fill_rect = QRectF(bar_x, bar_y, prog_w, bar_h)
        grad = QLinearGradient(bar_x, 0.0, bar_x + prog_w, 0.0)
        if self._update_result and self._update_result.has_update:
            grad.setColorAt(0.0, QColor(46, 204, 113))
            grad.setColorAt(1.0, QColor(52, 152, 219))
        else:
            grad.setColorAt(0.0, QColor(52, 152, 219))
            grad.setColorAt(1.0, QColor(155, 89, 182))
        p.setBrush(grad)
        p.drawRoundedRect(fill_rect, 2.0, 2.0)

        p.setClipping(False)
        border_pen = QPen(QColor(255, 255, 255, 35), 1.2)
        p.setPen(border_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.6, 0.6, w - 1.2, h - 1.2), radius, radius)

