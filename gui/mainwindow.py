"""主窗口：拖入文件 → 选择目标格式 → 转换 → 打开结果。"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import convert
from core.utils import is_dir_writable, resource_path, write_probe_failure_reason
from gui import formats
from gui.settings import Settings
from gui.widgets import DropArea, FileRow
from gui.worker import ConvertWorker, Job

logger = logging.getLogger(__name__)

VERSION = "1.0.0"
DPI_CHOICES = (100, 150, 200, 300)

FILE_FILTER = (
    "所有支持的文件 (" + " ".join(f"*{ext}" for ext in formats.SUPPORTED_EXTENSIONS) + ");;"
    "所有文件 (*.*)"
)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, initial_files: list[str] | None = None):
        super().__init__()
        self.settings = settings

        self._paths: list[Path] = []
        self._rows: dict[str, FileRow] = {}
        self._chips: dict[str, QPushButton] = {}
        self._chip_group: QButtonGroup | None = None
        self._target: str | None = None
        self._running = False
        self._thread = None  # 已改用 Python 线程，保留占位避免旧引用报错
        self._worker = None
        self._last_output: str = ""
        self._alert_timer = QTimer(self)
        self._alert_timer.setSingleShot(True)
        self._alert_timer.timeout.connect(self._hide_alert)

        self._build_ui()
        self._restore_state()
        self._check_write_permission()

        if initial_files:
            QTimer.singleShot(0, lambda: self.add_files(initial_files))

    # ── 启动自检 ─────────────────────────────────────────
    def _check_write_permission(self) -> None:
        """程序目录/配置目录不可写时，第一时间告诉用户，而不是等转换失败"""
        from core.utils import user_data_dir

        target = user_data_dir()
        if is_dir_writable(target):
            return
        reason = write_probe_failure_reason(target)
        self._show_alert(
            "程序当前没有文件写入权限"
            f"（{reason or '写入被拒绝'}），转换结果将无法保存。"
            "请把整个程序文件夹复制到本地磁盘（如桌面），"
            "然后在资源管理器里双击 TransEverything.exe 重新打开。",
            persist=True,
        )

    # ── 界面搭建 ─────────────────────────────────────────
    def _build_ui(self) -> None:
        self.setWindowTitle("TransEverything")
        self.resize(1040, 680)
        self.setMinimumSize(900, 600)
        icon_path = resource_path("assets", "app.ico")
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(12)

        outer.addLayout(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addLayout(self._build_left(), 1)
        body.addWidget(self._build_right())
        outer.addLayout(body, 1)

        outer.addLayout(self._build_footer())

        self.alert = QLabel()
        self.alert.setWordWrap(True)
        self.alert.setVisible(False)
        self.alert.setStyleSheet(
            "background:#FEF2F2; color:#B91C1C; border:1px solid #FECACA;"
            "border-radius:8px; padding:7px 10px; font-size:12px;"
        )
        outer.insertWidget(1, self.alert)

        self._refresh()

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        logo = QLabel()
        icon_path = resource_path("assets", "app.ico")
        if icon_path.is_file():
            logo.setPixmap(QIcon(str(icon_path)).pixmap(30, 30))
            logo.setFixedSize(30, 30)
        row.addWidget(logo)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel("TransEverything")
        title.setObjectName("appTitle")
        sub = QLabel("文件格式转换 · 拖入即用")
        sub.setObjectName("appSub")
        titles.addWidget(title)
        titles.addWidget(sub)
        row.addLayout(titles)
        row.addStretch(1)

        privacy = QLabel("本地处理 · 文件不会上传")
        privacy.setObjectName("privacy")
        row.addWidget(privacy)

        about = QPushButton("关于")
        about.setObjectName("ghost")
        about.setCursor(Qt.CursorShape.PointingHandCursor)
        about.clicked.connect(self._show_about)
        row.addWidget(about)
        return row

    def _build_left(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(10)

        self.drop = DropArea()
        self.drop.filesDropped.connect(self.add_files)
        self.drop.clicked.connect(self._choose_files)
        column.addWidget(self.drop)

        self.files_card = QFrame()
        self.files_card.setObjectName("card")
        card_layout = QVBoxLayout(self.files_card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        section = QLabel("文件列表")
        section.setObjectName("section")
        self.count_label = QLabel("0 个")
        self.count_label.setObjectName("hint")
        head.addWidget(section)
        head.addWidget(self.count_label)
        head.addStretch(1)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setObjectName("ghost")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_files)
        head.addWidget(self.clear_btn)
        card_layout.addLayout(head)

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(6)
        self.rows_layout.addStretch(1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.rows_container)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        card_layout.addWidget(self.scroll, 1)

        column.addWidget(self.files_card, 1)
        self.files_card.setVisible(False)
        return column

    def _build_right(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(300)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        target_title = QLabel("转换为")
        target_title.setObjectName("section")
        layout.addWidget(target_title)

        self.chips_container = QWidget()
        self.chips_layout = QVBoxLayout(self.chips_container)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(6)
        layout.addWidget(self.chips_container)

        self.target_hint = QLabel("先添加文件")
        self.target_hint.setObjectName("hint")
        self.target_hint.setWordWrap(True)
        layout.addWidget(self.target_hint)

        # 图片分辨率（仅在 PDF → PNG 时出现）
        self.dpi_row = QWidget()
        dpi_layout = QVBoxLayout(self.dpi_row)
        dpi_layout.setContentsMargins(0, 6, 0, 0)
        dpi_layout.setSpacing(6)
        dpi_title = QLabel("图片分辨率")
        dpi_title.setObjectName("section")
        dpi_layout.addWidget(dpi_title)

        dpi_buttons = QHBoxLayout()
        dpi_buttons.setSpacing(6)
        self._dpi_group = QButtonGroup(self)
        self._dpi_group.setExclusive(True)
        self._dpi_buttons: dict[int, QPushButton] = {}
        current_dpi = self.settings.dpi
        for value in DPI_CHOICES:
            button = QPushButton(str(value))
            button.setObjectName("chipSmall")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setChecked(value == current_dpi)
            button.clicked.connect(lambda _checked=False, v=value: self._set_dpi(v))
            self._dpi_group.addButton(button)
            dpi_buttons.addWidget(button)
            self._dpi_buttons[value] = button
        unit = QLabel("DPI")
        unit.setObjectName("hint")
        dpi_buttons.addWidget(unit)
        dpi_buttons.addStretch(1)
        dpi_layout.addLayout(dpi_buttons)
        layout.addWidget(self.dpi_row)
        self.dpi_row.setVisible(False)

        layout.addSpacing(6)

        out_title = QLabel("输出到")
        out_title.setObjectName("section")
        layout.addWidget(out_title)

        self.output_label = QLabel()
        self.output_label.setObjectName("hint")
        self.output_label.setWordWrap(True)
        layout.addWidget(self.output_label)

        out_buttons = QHBoxLayout()
        out_buttons.setSpacing(6)
        self.change_dir_btn = QPushButton("更改…")
        self.change_dir_btn.setObjectName("ghost")
        self.change_dir_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.change_dir_btn.clicked.connect(self._choose_output_dir)
        self.reset_dir_btn = QPushButton("恢复默认")
        self.reset_dir_btn.setObjectName("ghost")
        self.reset_dir_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_dir_btn.clicked.connect(self._reset_output_dir)
        out_buttons.addWidget(self.change_dir_btn)
        out_buttons.addWidget(self.reset_dir_btn)
        out_buttons.addStretch(1)
        layout.addLayout(out_buttons)

        layout.addStretch(1)

        self.primary_btn = QPushButton("开始转换")
        self.primary_btn.setObjectName("primary")
        self.primary_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.primary_btn.setMinimumHeight(42)
        self.primary_btn.clicked.connect(self._on_primary_clicked)
        layout.addWidget(self.primary_btn)

        self._refresh_output_label()
        return card

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        self.status_label = QLabel("准备就绪：拖入文件或点击上方区域选择")
        self.status_label.setObjectName("hint")
        row.addWidget(self.status_label, 1)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setFixedWidth(180)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        row.addWidget(self.progress)

        self.open_btn = QPushButton("打开文件夹")
        self.open_btn.setObjectName("ghost")
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._open_output_folder)
        row.addWidget(self.open_btn)
        return row

    # ── 状态恢复 ─────────────────────────────────────────
    def _restore_state(self) -> None:
        geometry = self.settings.geometry()
        if geometry and not geometry.isEmpty():
            self.restoreGeometry(geometry)

    def _save_state(self) -> None:
        self.settings.set_geometry(self.saveGeometry())
        self.settings.sync()

    # ── 文件管理 ─────────────────────────────────────────
    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择要转换的文件", "", FILE_FILTER)
        if files:
            self.add_files(files)

    def add_files(self, raw_paths: list[str]) -> None:
        """把文件（或文件夹里的文件）加入列表"""
        if self._running:
            return

        ignored: list[str] = []
        added = 0
        for raw in raw_paths:
            path = Path(raw)
            candidates: list[Path]
            if path.is_dir():
                try:
                    candidates = sorted(p for p in path.iterdir() if p.is_file())
                except OSError:
                    ignored.append(path.name)
                    continue
            elif path.is_file():
                candidates = [path]
            else:
                ignored.append(path.name)
                continue

            for candidate in candidates:
                if not formats.is_supported(candidate):
                    ignored.append(candidate.name)
                    continue
                key = str(candidate.resolve()).lower()
                if key in self._rows:
                    continue
                self._add_row(candidate)
                added += 1

        if ignored:
            shown = "、".join(ignored[:4])
            more = f" 等 {len(ignored)} 个" if len(ignored) > 4 else ""
            self._show_alert(f"已忽略不支持的文件：{shown}{more}")

        if added and not self._target:
            self.status_label.setText(f"已添加 {added} 个文件，请选择目标格式")
        self._refresh()
        if self._target:
            self.status_label.setText(
                f"{len(self._paths)} 个文件 → {formats.target_label(self._target)}"
            )

    def _add_row(self, path: Path) -> None:
        row = FileRow(path)
        row.removed.connect(self._remove_path)
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
        self._rows[str(path.resolve()).lower()] = row
        self._paths.append(path)

    def _remove_path(self, raw: str) -> None:
        if self._running:
            return
        key = raw.lower()
        row = self._rows.pop(key, None)
        if row is not None:
            self.rows_layout.removeWidget(row)
            self._dispose_widget(row)
        self._paths = [p for p in self._paths if str(p.resolve()).lower() != key]
        self._refresh()
        if not self._paths:
            self.status_label.setText("准备就绪：拖入文件或点击上方区域选择")

    def clear_files(self) -> None:
        if self._running:
            return
        for row in list(self._rows.values()):
            self.rows_layout.removeWidget(row)
            self._dispose_widget(row)
        self._rows.clear()
        self._paths.clear()
        self._target = None
        self._last_output = ""
        self.open_btn.setEnabled(False)
        self.progress.setVisible(False)
        self.status_label.setText("准备就绪：拖入文件或点击上方区域选择")
        self._refresh()

    # ── 控件销毁（确定性，避免延迟删除堆积到退出阶段）────
    @staticmethod
    def _dispose_widget(widget: QWidget | None) -> None:
        if widget is None:
            return
        widget.setParent(None)
        widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    # ── 刷新界面 ─────────────────────────────────────────
    def _refresh(self) -> None:
        count = len(self._paths)
        self.count_label.setText(f"{count} 个")
        self.files_card.setVisible(count > 0)
        self.drop.set_compact(count > 0)
        if count and self._target is None:
            self.status_label.setText("这些文件没有共同的目标格式，请移除部分文件后重试")
        self._rebuild_chips()
        self._update_primary_state()

    def _rebuild_chips(self) -> None:
        while self.chips_layout.count():
            item = self.chips_layout.takeAt(0)
            self._dispose_widget(item.widget())

        self._chips.clear()
        if self._chip_group is not None:
            self._dispose_widget(self._chip_group)
            self._chip_group = None
        self._chip_group = QButtonGroup(self)
        self._chip_group.setExclusive(True)

        targets = formats.common_targets(self._paths)
        if not self._paths:
            self._target = None
            self.target_hint.setText("先添加文件")
            self.target_hint.setVisible(True)
            self._update_dpi_visibility()
            return

        if not targets:
            self._target = None
            self.target_hint.setText("这些文件没有共同的目标格式，请移除部分文件后重试。")
            self.target_hint.setVisible(True)
            self._update_dpi_visibility()
            return

        self.target_hint.setVisible(False)
        if self._target not in targets:
            remembered = self.settings.last_target
            self._target = remembered if remembered in targets else targets[0]

        for target in targets:
            chip = QPushButton(formats.target_label(target))
            chip.setObjectName("chip")
            chip.setCheckable(True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setChecked(target == self._target)
            chip.clicked.connect(lambda _checked=False, t=target: self._on_target_changed(t))
            self._chip_group.addButton(chip)
            self.chips_layout.addWidget(chip)
            self._chips[target] = chip

        self._update_dpi_visibility()

    def _on_target_changed(self, target: str) -> None:
        self._target = target
        self.settings.last_target = target
        self._update_dpi_visibility()
        self._update_primary_state()
        if self._paths:
            self.status_label.setText(
                f"{len(self._paths)} 个文件 → {formats.target_label(target)}"
            )

    def _update_dpi_visibility(self) -> None:
        needs_dpi = self._target == "png" and any(
            p.suffix.lower() == ".pdf" for p in self._paths
        )
        self.dpi_row.setVisible(needs_dpi)

    def _on_dpi_changed(self, value: int) -> None:
        self.settings.dpi = int(value)

    def _set_dpi(self, value: int) -> None:
        self.settings.dpi = int(value)
        button = self._dpi_buttons.get(value)
        if button is not None and not button.isChecked():
            button.setChecked(True)

    def _update_primary_state(self) -> None:
        if self._running:
            self.primary_btn.setEnabled(True)
            return
        self.primary_btn.setEnabled(self._target is not None and bool(self._paths))

    # ── 输出位置 ─────────────────────────────────────────
    def _output_dir(self) -> str:
        if self.settings.output_mode == "custom":
            return self.settings.output_dir
        return ""

    def _refresh_output_label(self) -> None:
        if self.settings.output_mode == "custom" and self.settings.output_dir:
            self.output_label.setText(self.settings.output_dir)
            self.output_label.setToolTip(self.settings.output_dir)
        else:
            self.output_label.setText("与源文件相同")
            self.output_label.setToolTip("转换结果保存在原文件所在目录")

    def _choose_output_dir(self) -> None:
        start = self.settings.output_dir or str(Path.home())
        directory = QFileDialog.getExistingDirectory(self, "选择输出文件夹", start)
        if directory:
            self.settings.output_mode = "custom"
            self.settings.output_dir = directory
            self._refresh_output_label()

    def _reset_output_dir(self) -> None:
        self.settings.output_mode = "same"
        self._refresh_output_label()

    # ── 转换流程 ─────────────────────────────────────────
    def _on_primary_clicked(self) -> None:
        if self._running:
            self._cancel_conversion()
        else:
            self._start_conversion()

    def _start_conversion(self) -> None:
        if not self._paths or not self._target:
            return

        output_dir = self._output_dir()
        if output_dir:
            target_dir = Path(output_dir)
            if not target_dir.is_dir():
                self._show_alert(f"输出文件夹不存在：{output_dir}")
                return
            if not is_dir_writable(target_dir):
                reason = write_probe_failure_reason(target_dir)
                self._show_alert(
                    f"输出目录不可写：{output_dir}（{reason or '写入被拒绝'}）。"
                    "请点「更改…」换一个目录，或点「恢复默认」保存到源文件旁边。"
                )
                return

        pairs = [(p, self._target) for p in self._paths if formats.accepts_target(p, self._target)]
        skipped = len(self._paths) - len(pairs)
        if not pairs:
            self._show_alert("当前目标格式不适用于所选文件。")
            return
        if skipped:
            self._show_alert(f"有 {skipped} 个文件不支持该目标格式，已跳过。")

        try:
            jobs = ConvertWorker.jobs_from_pairs(pairs, convert.CONVERSION_MAP)
        except ValueError as exc:
            self._show_alert(str(exc))
            return

        for row in self._rows.values():
            row.set_status("pending", "等待")

        self._set_running(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, len(jobs))
        self.progress.setValue(0)
        self.status_label.setText(f"正在转换 0/{len(jobs)} …")
        self._last_output = ""

        self._worker = ConvertWorker(jobs, output_dir=output_dir, dpi=self.settings.dpi)
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        logger.info(
            "开始转换：%d 个文件，目标 %s，输出 %s",
            len(jobs),
            self._target,
            output_dir or "源目录",
        )
        self._worker.start()

    def _cancel_conversion(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.status_label.setText("正在取消…")
            self.primary_btn.setEnabled(False)

    def _on_file_started(self, path: str) -> None:
        row = self._rows.get(path.lower())
        if row is not None:
            row.set_running()

    def _on_file_done(self, path: str, ok: bool, message: str, output: str) -> None:
        row = self._rows.get(path.lower())
        if row is not None:
            row.set_result(ok, message)
        if ok and output:
            self._last_output = output

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setValue(done)
        if done < total:
            self.status_label.setText(f"正在转换 {done}/{total} …")

    def _on_finished(self, success: int, failed: int, cancelled: bool) -> None:
        if cancelled:
            for row in self._rows.values():
                if row.status_label.text() in ("等待", "转换中…"):
                    row.set_status("pending", "已取消")
            self.status_label.setText(f"已取消：成功 {success} 个，失败 {failed} 个")
        elif failed:
            self.status_label.setText(f"完成：成功 {success} 个，失败 {failed} 个（失败原因见列表）")
        else:
            self.status_label.setText(f"完成：{success} 个文件转换成功")
        self._set_running(False)
        self.progress.setVisible(False)
        self.open_btn.setEnabled(bool(self._last_output))
        if success:
            self._show_alert("转换完成，点击右下角「打开文件夹」查看结果。", kind="ok")
        self._cleanup_worker()

    def _cleanup_worker(self) -> None:
        """同步回收 worker：等线程真正结束、断开信号，再立即派发延迟删除。

        不能用 QTimer.singleShot 延迟清理——如果程序紧接着退出，那个延迟删除
        不会被处理，Qt 在销毁对象时可能触发访问冲突。
        """
        worker = self._worker
        if worker is None:
            return
        self._worker = None
        worker.wait(3000)
        for signal in (
            worker.file_started,
            worker.file_done,
            worker.progress,
            worker.finished,
        ):
            try:
                signal.disconnect()
            except (RuntimeError, TypeError):
                pass
        worker.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.drop.setEnabled(not running)
        self.clear_btn.setEnabled(not running)
        self.change_dir_btn.setEnabled(not running)
        self.reset_dir_btn.setEnabled(not running)
        for chip in self._chips.values():
            chip.setEnabled(not running)
        self.primary_btn.setText("取消转换" if running else "开始转换")
        self.primary_btn.setEnabled(True)

    # ── 其它 ─────────────────────────────────────────────
    def _open_output_folder(self) -> None:
        if not self._last_output:
            return
        target = Path(self._last_output)
        try:
            if target.is_dir():
                os.startfile(str(target))  # noqa: S606 - Windows 打开资源管理器
            elif target.is_file():
                subprocess.Popen(["explorer", "/select,", str(target)])
            else:
                self._show_alert("结果文件已被移动或删除。")
        except OSError as exc:
            self._show_alert(f"无法打开文件夹：{exc}")

    def _show_alert(self, message: str, kind: str = "warn", persist: bool = False) -> None:
        colors = (
            "background:#ECFDF3; color:#067647; border:1px solid #ABEFC6;"
            if kind == "ok"
            else "background:#FEF2F2; color:#B91C1C; border:1px solid #FECACA;"
        )
        self.alert.setStyleSheet(
            f"{colors} border-radius:8px; padding:7px 10px; font-size:12px;"
        )
        self.alert.setText(message)
        self.alert.setVisible(True)
        if persist:
            self._alert_timer.stop()
        else:
            self._alert_timer.start(6000)

    def _hide_alert(self) -> None:
        self.alert.setVisible(False)

    def _show_about(self) -> None:
        from core.utils import user_log_dir

        text = (
            f"<b>TransEverything {VERSION}</b><br><br>"
            "本地文件格式转换工具：PDF / Word / TXT、Excel / CSV / TSV、PNG / SVG / JPG。<br>"
            "所有转换都在本机完成，文件不会上传到网络。<br><br>"
            "内置字体：Noto Sans SC（SIL Open Font License 1.1）<br>"
            "界面：Qt for Python (PySide6, LGPL v3)<br><br>"
            f"日志目录：<br>{user_log_dir()}"
        )
        box = QMessageBox(self)
        box.setWindowTitle("关于 TransEverything")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    # ── 拖拽（窗口级兜底）────────────────────────────────
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime.hasUrls() and any(url.isLocalFile() for url in mime.urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.add_files(paths)
            event.acceptProposedAction()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._worker is not None and self._worker.running:
            self._worker.cancel()
            self._worker.wait(5000)
        self._save_state()
        super().closeEvent(event)
