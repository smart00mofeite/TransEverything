"""用户设置的持久化：存成 %APPDATA%\\TransEverything\\settings.json。

不用 QSettings/注册表：JSON 文件可移植、可查看、卸载时随目录一起删除，
也不受注册表权限策略影响（企业电脑上常见被锁）。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6.QtCore import QByteArray

from core.utils import user_data_dir

logger = logging.getLogger(__name__)

DEFAULTS = {
    "window_geometry": "",
    "output_mode": "same",   # same = 与源文件同目录；custom = 指定目录
    "output_dir": "",
    "dpi": 150,
    "last_target": "",
}


class Settings:
    def __init__(self, path: Path | None = None):
        self._path = Path(path) if path else user_data_dir() / "settings.json"
        self._data = dict(DEFAULTS)
        self._load()

    # ── 存取 ─────────────────────────────────────────────
    def _load(self) -> None:
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                self._data.update({k: v for k, v in data.items() if k in DEFAULTS})
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            logger.warning("读取设置失败，使用默认值：%s", exc)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp = self._path.with_suffix(".json.tmp")
            temp.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temp.replace(self._path)
        except OSError as exc:
            logger.warning("保存设置失败：%s", exc)

    def sync(self) -> None:
        self._save()

    # ── 窗口 ─────────────────────────────────────────────
    def geometry(self) -> QByteArray:
        value = str(self._data.get("window_geometry") or "")
        if not value:
            return QByteArray()
        try:
            return QByteArray.fromHex(value.encode("ascii"))
        except Exception:
            return QByteArray()

    def set_geometry(self, data: QByteArray) -> None:
        self._data["window_geometry"] = bytes(data).hex()

    # ── 输出位置 ─────────────────────────────────────────
    @property
    def output_mode(self) -> str:
        mode = str(self._data.get("output_mode") or "same")
        return mode if mode in ("same", "custom") else "same"

    @output_mode.setter
    def output_mode(self, mode: str) -> None:
        self._data["output_mode"] = "custom" if mode == "custom" else "same"
        self._save()

    @property
    def output_dir(self) -> str:
        return str(self._data.get("output_dir") or "")

    @output_dir.setter
    def output_dir(self, path: str) -> None:
        self._data["output_dir"] = str(path or "")
        self._save()

    # ── 其它 ─────────────────────────────────────────────
    @property
    def dpi(self) -> int:
        try:
            value = int(self._data.get("dpi") or 150)
        except (TypeError, ValueError):
            value = 150
        return value if 72 <= value <= 600 else 150

    @dpi.setter
    def dpi(self, value: int) -> None:
        self._data["dpi"] = int(value)
        self._save()

    @property
    def last_target(self) -> str:
        return str(self._data.get("last_target") or "")

    @last_target.setter
    def last_target(self, target: str) -> None:
        self._data["last_target"] = str(target or "")
        self._save()
