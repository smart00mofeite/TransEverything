"""自定义控件：拖拽区、文件行、省略号标签。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.formats import BADGE_COLORS, human_size, kind_label


class ElidedLabel(QLabel):
    """按控件宽度自动在中间省略的标签（用于长文件名）。"""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setToolTip(text)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt 命名
        self._full = text
        self.setToolTip(text)
        self.update()

    def fullText(self) -> str:  # noqa: N802
        return self._full

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        color = self.palette().color(QPalette.ColorRole.WindowText)
        painter.setPen(QColor(color))
        metrics = self.fontMetrics()
        elided = metrics.elidedText(
            self._full, Qt.TextElideMode.ElideMiddle, max(10, self.width())
        )
        painter.drawText(self.rect(), int(self.alignment()), elided)


class DropArea(QFrame):
    """拖拽 / 点击选择文件的区域"""

    filesDropped = Signal(list)
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("dragging", False)
        self.setMinimumHeight(112)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        layout.addStretch(1)

        icon = QLabel("＋")
        icon.setObjectName("dropIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text = QLabel("把文件拖到这里，或点击选择")
        text.setObjectName("dropText")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel("支持 PDF / Word / TXT / Excel / CSV / TSV / PNG / SVG / JPG")
        hint.setObjectName("dropHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint = hint
        self._icon = icon
        self._text = text

        layout.addWidget(icon)
        layout.addWidget(text)
        layout.addWidget(hint)
        layout.addStretch(1)

    def set_compact(self, compact: bool) -> None:
        """列表已有文件时把拖拽区收成一条细条"""
        self._hint.setVisible(not compact)
        self._icon.setVisible(not compact)
        if compact:
            self.setMinimumHeight(56)
            self.setMaximumHeight(64)
        else:
            self.setMinimumHeight(150)
            self.setMaximumHeight(300)

    # ── 拖拽 ─────────────────────────────────────────────
    def _accept_event(self, event) -> bool:
        mime = event.mimeData()
        if mime.hasUrls() and any(url.isLocalFile() for url in mime.urls()):
            event.acceptProposedAction()
            return True
        event.ignore()
        return False

    def _set_dragging(self, value: bool) -> None:
        self.setProperty("dragging", value)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._accept_event(event):
            self._set_dragging(True)

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._set_dragging(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        self._set_dragging(False)
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class FileRow(QFrame):
    """文件列表中的一行"""

    removed = Signal(str)

    def __init__(self, path: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.path = path
        self.setObjectName("fileRow")
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(10)

        ext = path.suffix.lower().lstrip(".") or "file"
        bg, fg = BADGE_COLORS.get(ext, ("#F1F2F5", "#4B5563"))
        badge = QLabel(ext.upper()[:5])
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(QSize(42, 22))
        badge.setStyleSheet(
            f"background:{bg}; color:{fg}; border-radius:6px;"
            f"font-size:10px; font-weight:700;"
        )
        layout.addWidget(badge)

        info = QVBoxLayout()
        info.setSpacing(2)
        self.name_label = ElidedLabel(path.name)
        self.name_label.setObjectName("fileName")
        meta = QLabel(f"{kind_label(path)} · {human_size(path.stat().st_size if path.exists() else 0)}")
        meta.setObjectName("fileMeta")
        info.addWidget(self.name_label)
        info.addWidget(meta)
        layout.addLayout(info, 1)

        self.status_label = QLabel("等待")
        self.status_label.setObjectName("statusPending")
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.status_label)

        self.remove_btn = QLabel("×")
        self.remove_btn.setObjectName("removeBtn")
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.setToolTip("从列表移除")
        self.remove_btn.setFixedWidth(20)
        self.remove_btn.mouseReleaseEvent = self._on_remove  # type: ignore[assignment]
        layout.addWidget(self.remove_btn)

    def _on_remove(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton:
            self.removed.emit(str(self.path))

    def set_status(self, kind: str, text: str) -> None:
        names = {
            "pending": "statusPending",
            "running": "statusRunning",
            "ok": "statusOk",
            "fail": "statusFail",
        }
        self.status_label.setObjectName(names.get(kind, "statusPending"))
        self.status_label.setText(text)
        self.status_label.setToolTip(text)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def set_running(self) -> None:
        self.set_status("running", "转换中…")

    def set_result(self, ok: bool, message: str) -> None:
        if ok:
            self.set_status("ok", "完成")
            self.status_label.setToolTip(message)
        else:
            short = message if len(message) <= 24 else message[:22] + "…"
            self.set_status("fail", f"失败：{short}")
            self.status_label.setToolTip(message)
