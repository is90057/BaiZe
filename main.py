import sys
import os

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("BaiZe")
    app.setOrganizationName("BaiZe")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()