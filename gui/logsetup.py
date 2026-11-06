"""日志：写到 %LOCALAPPDATA%\\TransEverything\\logs\\app.log，按天滚动保留 7 天。"""

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from core.utils import user_log_dir

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> Path:
    log_file = user_log_dir() / "app.log"
    root = logging.getLogger()
    root.setLevel(level)

    already = any(
        isinstance(handler, TimedRotatingFileHandler)
        and Path(getattr(handler, "baseFilename", "")).name == log_file.name
        for handler in root.handlers
    )
    if not already:
        try:
            handler = TimedRotatingFileHandler(
                str(log_file), when="midnight", backupCount=7, encoding="utf-8"
            )
            handler.setFormatter(logging.Formatter(_FORMAT))
            root.addHandler(handler)
        except OSError:
            # 日志目录不可写时不能影响程序启动
            root.warning("无法写入日志文件 %s，本次运行不记录文件日志", log_file)

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(stream)

    return log_file
