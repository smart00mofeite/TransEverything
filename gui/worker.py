"""后台转换：Python 线程执行转换，通过 Qt 信号回到主线程更新界面。

不使用 QThread：在本项目里 QThread 的 C++ 对象与 worker 的销毁顺序容易在退出时
触发访问冲突（0xC0000005）。Python 线程 + QObject 信号桥更简单也更稳。
"""

from __future__ import annotations

import importlib
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


@dataclass
class Job:
    """一个待转换文件"""

    path: Path
    target: str
    module: str


def humanize_error(exc: BaseException) -> str:
    """把异常翻译成用户看得懂的一句话（尽量带上出错路径）"""
    if isinstance(exc, FileNotFoundError):
        name = getattr(exc, "filename", "") or ""
        return f"文件不存在或已被移动：{name}" if name else "文件不存在或已被移动"
    if isinstance(exc, PermissionError):
        name = getattr(exc, "filename", "") or ""
        where = f"（{name}）" if name else ""
        return f"没有写入权限{where}：目标目录只读、被占用，或被安全软件拦截"
    if isinstance(exc, IsADirectoryError):
        return "选中的是文件夹，无法转换"
    if isinstance(exc, UnicodeDecodeError):
        return "文本编码无法识别，请另存为 UTF-8 后重试"
    if isinstance(exc, MemoryError):
        return "文件太大，内存不足"
    if isinstance(exc, OSError) and getattr(exc, "strerror", ""):
        name = getattr(exc, "filename", "") or ""
        where = f"（{name}）" if name else ""
        return f"读写失败{where}：{exc.strerror}"
    message = str(exc).strip()
    if message:
        return message
    return f"转换失败（{type(exc).__name__}）"


class ConvertWorker(QObject):
    """在后台线程里串行执行转换任务"""

    file_started = Signal(str)               # 文件路径
    file_done = Signal(str, bool, str, str)  # 路径, 成功, 说明, 输出路径
    progress = Signal(int, int)              # 已完成数, 总数
    finished = Signal(int, int, bool)        # 成功数, 失败数, 是否被取消

    def __init__(self, jobs: list[Job], output_dir: str = "", dpi: int = 150):
        super().__init__()
        self._jobs = list(jobs)
        self._output_dir = output_dir or ""
        self._dpi = dpi
        self._cancel_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ── 控制 ─────────────────────────────────────────────
    def start(self) -> None:
        if self._thread is not None or not self._jobs:
            return
        self._thread = threading.Thread(
            target=self._run, name="TransEverythingConvert", daemon=True
        )
        self._thread.start()

    def cancel(self) -> None:
        self._cancel_event.set()

    def wait(self, timeout_ms: int = 5000) -> bool:
        """等待后台线程结束，返回是否已经结束"""
        if self._thread is None:
            return True
        self._thread.join(timeout_ms / 1000.0)
        return not self._thread.is_alive()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── 执行 ─────────────────────────────────────────────
    def _run(self) -> None:
        total = len(self._jobs)
        success = 0
        failed = 0
        cancelled = False

        try:
            for index, job in enumerate(self._jobs, start=1):
                if self._cancel_event.is_set():
                    cancelled = True
                    logger.info("用户取消转换，剩余 %d 个文件未处理", total - index + 1)
                    break

                self.file_started.emit(str(job.path))
                started = time.perf_counter()
                try:
                    module = importlib.import_module(job.module)
                    result = module.convert(
                        str(job.path),
                        output_dir=self._output_dir,
                        **self._extra_kwargs(job),
                    )
                    output = Path(result)
                    detail = self._describe_output(output)
                    logger.info(
                        "转换成功 %s -> %s（%.2fs）",
                        job.path.name,
                        output,
                        time.perf_counter() - started,
                    )
                    success += 1
                    self.file_done.emit(str(job.path), True, detail, str(output))
                except Exception as exc:  # noqa: BLE001 - 单条失败不影响整批
                    failed += 1
                    detail = humanize_error(exc)
                    logger.exception("转换失败 %s -> .%s", job.path.name, job.target)
                    self.file_done.emit(str(job.path), False, detail, "")

                self.progress.emit(index, total)
        except Exception:  # noqa: BLE001 - 兜底，保证 finished 一定会发出
            logger.exception("转换线程异常退出")
        finally:
            self.finished.emit(success, failed, cancelled)

    def _extra_kwargs(self, job: Job) -> dict:
        extra: dict = {}
        if job.path.suffix.lower() == ".pdf" and job.target == "png":
            extra["dpi"] = self._dpi
        return extra

    @staticmethod
    def _describe_output(output: Path) -> str:
        if output.is_dir():
            count = len(list(output.glob("*.png")))
            return f"已生成 {count} 张图片"
        return output.name

    @staticmethod
    def jobs_from_pairs(
        pairs: list[tuple[Path, str]], module_map: dict[str, str]
    ) -> list[Job]:
        """把 (文件, 目标格式) 转成 Job 列表；不支持的组合直接抛错"""
        jobs: list[Job] = []
        for path, target in pairs:
            key = f"{path.suffix.lower().lstrip('.')}_{target}"
            module = module_map.get(key)
            if module is None:
                raise ValueError(f"不支持的转换：{path.name} → {target}")
            jobs.append(Job(path=path, target=target, module=module))
        return jobs
