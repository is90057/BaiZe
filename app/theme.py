DARK_QSS = """
* {
    font-family: "Helvetica Neue", "Arial";
    font-size: 13px;
    color: #d6d6d8;
}
QMainWindow, QDialog, QWidget {
    background-color: #1b1b1f;
}
QWidget#transport {
    background-color: #222227;
    border-top: 1px solid #33333a;
}
QLabel#panelTitle {
    font-size: 14px;
    font-weight: bold;
    color: #ececf0;
    padding-bottom: 4px;
}
QLabel#dimText {
    color: #8a8a92;
}
QLabel#totalLabel, QLabel#markLabel {
    color: #b0b0b8;
}
QToolButton, QPushButton {
    background-color: #2c2c33;
    border: 1px solid #3a3a42;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e0e0e4;
}
QToolButton:hover, QPushButton:hover {
    background-color: #383844;
    border-color: #4a4a54;
}
QToolButton:pressed, QPushButton:pressed {
    background-color: #23232a;
}
QToolButton:checked {
    background-color: #3a6ea5;
    border-color: #5b8fc9;
}
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
    background-color: #26262c;
    border: 1px solid #3a3a42;
    border-radius: 4px;
    padding: 3px 6px;
    selection-background-color: #3a6ea5;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
    border-color: #5b8fc9;
}
QListWidget {
    background-color: #161619;
    border: 1px solid #33333a;
    border-radius: 4px;
}
QListWidget::item {
    padding: 4px;
    color: #cfcfd4;
}
QListWidget::item:selected {
    background-color: #3a6ea5;
    color: white;
}
QListWidget::item:hover {
    background-color: #2a4a6e;
}
QScrollArea {
    background-color: #1b1b1f;
    border: none;
}
QScrollBar:horizontal {
    background: #232329;
    height: 12px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #45454e;
    border-radius: 6px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: #555560; }
QScrollBar:vertical {
    background: #232329;
    width: 12px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #45454e;
    border-radius: 6px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #555560; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QGroupBox {
    border: 1px solid #33333a;
    border-radius: 5px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #bfc2c9;
}
QProgressBar {
    background-color: #26262c;
    border: 1px solid #3a3a42;
    border-radius: 4px;
    text-align: center;
    height: 16px;
}
QProgressBar::chunk {
    background-color: #3a6ea5;
    border-radius: 3px;
}
QMenuBar {
    background-color: #1f1f24;
    border-bottom: 1px solid #33333a;
}
QMenuBar::item {
    padding: 4px 10px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #3a6ea5;
}
QStatusBar {
    background-color: #1f1f24;
    border-top: 1px solid #33333a;
    color: #9a9aa2;
}
QSplitter::handle {
    background-color: #2e2e35;
}
QMessageBox {
    background-color: #1f1f24;
}
"""