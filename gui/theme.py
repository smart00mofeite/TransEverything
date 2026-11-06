"""界面配色、字体与全局样式表。"""

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from core.utils import resource_path

# ── 配色 ──────────────────────────────────────────────────
BG = "#F5F6F8"
CARD = "#FFFFFF"
BORDER = "#E6E8EC"
TEXT = "#111827"
MUTED = "#6B7280"
PRIMARY = "#4F7CFF"
PRIMARY_HOVER = "#3D6BEB"
PRIMARY_SOFT = "#EEF3FF"
SUCCESS = "#16A34A"
DANGER = "#DC2626"

QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans SC", "PingFang SC", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}

QWidget#root {{ background: {BG}; }}

QLabel#appTitle {{ font-size: 19px; font-weight: 700; }}
QLabel#appSub {{ color: {MUTED}; font-size: 12px; }}
QLabel#privacy {{ color: {MUTED}; font-size: 12px; }}

QFrame#card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QLabel#section {{ color: {MUTED}; font-size: 12px; font-weight: 600; }}
QLabel#hint {{ color: {MUTED}; font-size: 12px; }}

QFrame#dropArea {{
    background: #FAFBFC;
    border: 2px dashed #CBD5E1;
    border-radius: 12px;
}}
QFrame#dropArea[dragging="true"] {{
    background: {PRIMARY_SOFT};
    border-color: {PRIMARY};
}}
QLabel#dropIcon {{ color: {PRIMARY}; font-size: 22px; font-weight: 700; }}
QLabel#dropText {{ color: #374151; font-size: 14px; font-weight: 600; }}
QLabel#dropHint {{ color: {MUTED}; font-size: 12px; }}

QFrame#fileRow {{
    background: #FBFCFD;
    border: 1px solid #EDF0F4;
    border-radius: 10px;
}}
QLabel#fileName {{ font-size: 13px; font-weight: 600; }}
QLabel#fileMeta {{ color: {MUTED}; font-size: 11px; }}
QLabel#statusPending {{ color: {MUTED}; font-size: 12px; }}
QLabel#statusRunning {{ color: {PRIMARY}; font-size: 12px; }}
QLabel#statusOk {{ color: {SUCCESS}; font-size: 12px; }}
QLabel#statusFail {{ color: {DANGER}; font-size: 12px; }}

QPushButton#primary {{
    background: {PRIMARY};
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 11px 16px;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton#primary:disabled {{ background: #C7D2FE; color: #F8FAFC; }}

QPushButton#ghost {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 12px;
    color: #374151;
}}
QPushButton#ghost:hover {{ background: #F3F4F6; }}
QPushButton#ghost:disabled {{ color: #B6BCC6; background: #FAFAFB; }}

QPushButton#chip {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 9px 10px;
    color: #374151;
    text-align: left;
}}
QPushButton#chip:hover {{ border-color: #C7D2FE; background: #F5F7FF; }}
QPushButton#chip:checked {{
    border: 1px solid {PRIMARY};
    background: {PRIMARY_SOFT};
    color: #2B4CD7;
    font-weight: 600;
}}

QPushButton#chipSmall {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    color: #374151;
    font-size: 12px;
}}
QPushButton#chipSmall:hover {{ border-color: #C7D2FE; background: #F5F7FF; }}
QPushButton#chipSmall:checked {{
    border: 1px solid {PRIMARY};
    background: {PRIMARY_SOFT};
    color: #2B4CD7;
    font-weight: 600;
}}

QLabel#removeBtn {{ color: #9AA1AC; font-size: 17px; padding: 0 2px; }}
QLabel#removeBtn:hover {{ color: {DANGER}; }}

QProgressBar {{
    background: #E9EBF0;
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 3px; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ width: 10px; background: transparent; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #D5D9E0; border-radius: 4px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: #C2C8D2; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QComboBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 8px;
    min-width: 84px;
}}
QComboBox:hover {{ border-color: #C7D2FE; }}
QComboBox QAbstractItemView {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {CARD};
    selection-background-color: {PRIMARY_SOFT};
    selection-color: #2B4CD7;
}}

QToolTip {{
    background: #1F2937;
    color: #FFFFFF;
    border: none;
    padding: 6px 8px;
    border-radius: 6px;
}}
"""


def load_fonts() -> None:
    """注册随包分发的 Noto Sans SC，保证英文系统上也有中文字形。"""
    for name in ("NotoSansSC-Regular.ttf", "NotoSansSC-Bold.ttf"):
        path = resource_path("fonts", name)
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))


def apply_theme(app: QApplication) -> None:
    load_fonts()
    families = set(QFontDatabase.families())
    for candidate in ("Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans SC"):
        if candidate in families:
            app.setFont(QFont(candidate, 9))
            break
    app.setStyleSheet(QSS)
