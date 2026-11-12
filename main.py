import sys
import os

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.views.splash_screen import SplashScreen


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("BaiZe")
    app.setOrganizationName("BaiZe")

    splash = SplashScreen()
    splash.show()
    app.processEvents()

    win = MainWindow(splash=splash)
    splash.set_main_window(win)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()