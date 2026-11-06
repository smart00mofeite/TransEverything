"""
公共工具函数：依赖检查、文件验证、路径处理、编码/字体/Excel 读写辅助
"""

import importlib
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Windows 终端编码兼容
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


# ── 路径与资源（源码运行 / PyInstaller 打包后都适用）──────


def _resolve_base_dir() -> Path:
    """
    资源根目录：
    - 源码运行：项目根目录（trans_everything/）
    - PyInstaller 打包后：sys._MEIPASS（onedir 时即程序目录）
    """
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        return Path(frozen_base)
    return Path(__file__).resolve().parent.parent


BASE_DIR = _resolve_base_dir()
PROJECT_ROOT = BASE_DIR  # 兼容旧引用
FONT_DIR = BASE_DIR / "fonts"


def resource_path(*parts: str) -> Path:
    """获取随程序分发的只读资源路径（字体、图标、许可文本等）"""
    return BASE_DIR.joinpath(*parts)


def _try_make_dir(target: Path) -> bool:
    try:
        target.mkdir(parents=True, exist_ok=True)
        return target.is_dir()
    except OSError:
        return False


def _pick_writable_dir(candidates: list[Path]) -> Path:
    """依次尝试候选目录，全部失败时退回系统临时目录（不抛异常）"""
    for candidate in candidates:
        if _try_make_dir(candidate):
            return candidate
    fallback = Path(tempfile.gettempdir()) / "TransEverything"
    _try_make_dir(fallback)
    return fallback


def is_dir_writable(directory: Path) -> bool:
    """真实写一个探测文件来判断目录可写（比 os.access 可靠）"""
    probe = directory / ".te_write_probe"
    try:
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        try:
            probe.unlink()
        except OSError:
            pass
        return False


def write_probe_failure_reason(directory: Path) -> str:
    """返回写探测失败的原因（给用户看的简短中文）"""
    probe = directory / ".te_write_probe"
    try:
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        return ""
    except PermissionError:
        return "拒绝访问（目录只读、被占用，或被安全软件拦截）"
    except FileNotFoundError:
        return "目录不存在"
    except OSError as exc:
        return f"{exc.strerror or exc}"
    finally:
        try:
            probe.unlink()
        except OSError:
            pass


def user_data_dir(app_name: str = "TransEverything", subdir: str = "") -> Path:
    """可写的用户数据目录：%APPDATA%\\TransEverything（不可写时自动降级）"""
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    target = Path(base) / app_name
    if subdir:
        target = target / subdir
    return _pick_writable_dir([target])


def user_log_dir(app_name: str = "TransEverything") -> Path:
    """日志目录：%LOCALAPPDATA%\\TransEverything\\logs（不可写时自动降级）"""
    base = (
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("APPDATA")
        or str(Path.home())
    )
    return _pick_writable_dir([Path(base) / app_name / "logs"])



DEPENDENCIES = {
    "pdfplumber": {"pip_name": "pdfplumber", "label": "PDF 文本提取"},
    "fpdf": {"pip_name": "fpdf2", "label": "PDF 生成"},
    "docx": {"pip_name": "python-docx", "label": "Word 文档处理"},
    # Excel/CSV
    "openpyxl": {"pip_name": "openpyxl", "label": "Excel 读写"},
    "python_calamine": {"pip_name": "python-calamine", "label": "旧版 .xls 读取"},
    # 图片
    "PIL": {"pip_name": "Pillow", "label": "图片处理"},
    "cairosvg": {"pip_name": "cairosvg", "label": "SVG 转换（旧方案，可选）"},
    "resvg_py": {"pip_name": "resvg_py", "label": "SVG 渲染"},
    "pypdfium2": {"pip_name": "pypdfium2", "label": "PDF 页面渲染"},
}


# ── 输出提示 ──────────────────────────────────────────────


def warn(message: str) -> None:
    """打印警告到 stderr（不因终端编码问题而崩溃）"""
    try:
        sys.stderr.write(f"[!] {message}\n")
        sys.stderr.flush()
    except Exception:
        pass


def check_dependency(module_name: str) -> bool:
    """检查单个模块是否可导入，返回 True/False"""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def check_dependencies(*names: str) -> dict[str, bool]:
    """
    批量检查依赖。返回 {模块名: 是否可用}
    如果不传参数则检查所有已注册的依赖。
    """
    if not names:
        names = tuple(DEPENDENCIES.keys())
    return {n: check_dependency(n) for n in names}


def ensure_dependencies(*names: str) -> None:
    """
    确保所需依赖已安装，缺失则打印提示并退出。
    """
    if not names:
        names = tuple(DEPENDENCIES.keys())

    missing = []
    for name in names:
        if not check_dependency(name):
            info = DEPENDENCIES.get(name, {})
            pip_name = info.get("pip_name", name)
            label = info.get("label", name)
            missing.append((name, pip_name, label))

    if missing:
        msg = ["[!] 缺少以下依赖库：\n"]
        for mod, pip_name, label in missing:
            msg.append(f"   - {label} ({mod}) -> pip install {pip_name}")
        msg.append(
            f"\n请运行以下命令安装所有依赖：\n"
            f"   pip install -r requirements.txt\n"
        )
        sys.stderr.write("\n".join(msg))
        sys.exit(1)


def validate_input_file(path: str, expected_extensions: list[str]) -> Path:
    """
    验证输入文件存在且扩展名匹配，返回 Path 对象。
    expected_extensions 如 ['.pdf', '.PDF']
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    if not p.is_file():
        raise ValueError(f"路径不是文件: {path}")
    ext = p.suffix.lower()
    if ext not in [e.lower() for e in expected_extensions]:
        raise ValueError(
            f"不支持的文件格式 '{p.suffix}'，"
            f"期望: {', '.join(expected_extensions)}"
        )
    return p


def get_output_path(
    input_path: Path,
    target_ext: str,
    output_dir: Optional[str] = None,
    suffix: str = "",
) -> Path:
    """
    生成输出文件路径。
    - 如果指定 output_dir，则输出到该目录；否则与输入文件同目录。
    - suffix 可用于添加 _converted 等标记。
    """
    stem = input_path.stem
    out_name = f"{stem}{suffix}.{target_ext.lstrip('.')}"
    if output_dir:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = input_path.parent
    dst = out_dir / out_name
    # 绝不允许覆盖源文件本身
    try:
        if dst.exists() and dst.resolve() == input_path.resolve():
            raise ValueError(f"输出路径与源文件相同，拒绝覆盖: {dst}")
    except OSError:
        pass
    return dst


# ── 文本编码 ──────────────────────────────────────────────


def detect_text_encoding(path: Path, sample_bytes: int = 1 << 16) -> str:
    """
    猜测文本编码，返回可供 open()/pandas 使用的编码名。
    优先 UTF-8（含 BOM），其次 UTF-16（按 BOM），最后按 GB18030（兼容 GBK/GB2312）。
    """
    with open(path, "rb") as f:
        raw = f.read(sample_bytes)
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "gb18030"


def read_text_auto(path: Path) -> str:
    """
    读取文本文件，自动识别 UTF-8 / UTF-8-BOM / UTF-16 / GB18030(GBK)。
    无法识别时抛出带指引的 UnicodeDecodeError。
    """
    encoding = detect_text_encoding(path)
    try:
        return path.read_text(encoding=encoding)
    except UnicodeDecodeError as e:
        raise UnicodeDecodeError(
            e.encoding,
            e.object,
            e.start,
            e.end,
            f"无法识别 {path.name} 的文本编码（已尝试 utf-8 / utf-16 / gb18030）。"
            f"请另存为 UTF-8 后重试。",
        ) from e


def is_encrypted_pdf(path: Path) -> bool:
    """粗略判断 PDF 是否加密：加密文件的 trailer 里一定有 /Encrypt"""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 4096))
            return b"/Encrypt" in f.read()
    except OSError:
        return False


def extract_pdf_pages(path: Path) -> list[str]:
    """
    按页提取 PDF 文本（已 strip）。加密或损坏的 PDF 会给出可读错误，
    而不是 pdfminer 的空消息异常。
    """
    import pdfplumber

    try:
        with pdfplumber.open(str(path)) as pdf:
            return [(page.extract_text() or "").strip() for page in pdf.pages]
    except Exception as e:
        if is_encrypted_pdf(path):
            raise ValueError(
                f"{path.name} 已加密（需要打开密码），请先用 PDF 工具去除密码后再转换。"
            ) from e
        raise ValueError(
            f"无法解析 PDF {path.name}：{e or type(e).__name__}。"
            "文件可能已损坏，或并非标准 PDF。"
        ) from e


# ── Word 文档 ─────────────────────────────────────────────


def open_docx(source: Path):
    """
    打开 .docx。对旧版 .doc 给出可执行的指引，而不是 python-docx 的
    PackageNotFoundError 原始报错。
    """
    from docx import Document

    if source.suffix.lower() == ".doc":
        raise ValueError(
            f"无法读取旧版 Word 格式 {source.name}：.doc 是二进制格式，"
            "python-docx 只支持 .docx。请用 Word/WPS 打开后「另存为 .docx」，"
            "或执行 soffice --headless --convert-to docx 后重试。"
        )
    try:
        return Document(str(source))
    except Exception as e:
        raise ValueError(
            f"无法打开 Word 文件 {source.name}：{e}。"
            "文件可能已损坏，或实际不是 .docx（例如把 .doc 改名为 .docx）。"
        ) from e


def iter_docx_blocks(document):
    """
    按文档顺序依次产出段落与表格。
    旧版 python-docx 没有 iter_inner_content 时退化为先段落后表格。
    """
    inner = getattr(document, "iter_inner_content", None)
    if callable(inner):
        return inner()
    return list(document.paragraphs) + list(document.tables)


def is_docx_table(block) -> bool:
    """判断 iter_docx_blocks 产出的对象是表格还是段落"""
    return hasattr(block, "rows") and hasattr(block, "columns")


# ── PDF 字体 ──────────────────────────────────────────────


# 优先使用带中文字形的字体；顺序按「内置字体 → 微软雅黑 → 宋体 → 其他」排列
# 内置 Noto Sans SC（OFL 协议）保证在任何 Windows 上都能正确显示中文
_CJK_FONT_CANDIDATES = (
    "NotoSansSC-Regular.ttf",        # 项目内置（OFL）
    "NotoSansSC-Regular.otf",
    "msyh.ttc", "msyh.ttf",          # 微软雅黑
    "simsun.ttc", "simsun.ttf",      # 宋体
    "simhei.ttf",                    # 黑体
    "Deng.ttf",                      # 等线
    "simkai.ttf", "simfang.ttf",     # 楷体 / 仿宋
    "SourceHanSansSC-Regular.otf",
    "NotoSansCJKsc-Regular.otf",
    "NotoSansCJK-Regular.ttc",
)
_BOLD_FONT_CANDIDATES = (
    "NotoSansSC-Bold.ttf",           # 项目内置（OFL）
    "NotoSansSC-Bold.otf",
    "msyhbd.ttc", "msyhbd.ttf",
    "simhei.ttf",
    "Dengb.ttf",
    "NotoSansCJKsc-Bold.otf",
)
_LATIN_FONT_CANDIDATES = ("DejaVuSans.ttf", "arial.ttf")


def _font_search_dirs() -> list[Path]:
    dirs: list[Path] = [FONT_DIR, PROJECT_ROOT]
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        dirs.append(Path(windir) / "Fonts")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    else:
        dirs += [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path("/System/Library/Fonts"),
            Path.home() / ".fonts",
        ]
    return dirs


def find_pdf_font(bold: bool = False) -> tuple[Optional[Path], bool]:
    """
    查找可嵌入 PDF 的字体。
    返回 (字体路径, 是否含中文字形)。
    可用环境变量 TRANS_EVERYTHING_FONT 指定字体文件的绝对路径。
    """
    override = os.environ.get("TRANS_EVERYTHING_FONT")
    if override:
        p = Path(override)
        if p.is_file():
            return p, True

    names = _BOLD_FONT_CANDIDATES if bold else _CJK_FONT_CANDIDATES
    for directory in _font_search_dirs():
        if not directory.is_dir():
            continue
        for name in names:
            p = directory / name
            if p.is_file():
                return p, True

    for directory in _font_search_dirs():
        if not directory.is_dir():
            continue
        for name in _LATIN_FONT_CANDIDATES:
            p = directory / name
            if p.is_file():
                return p, False
    return None, False


def setup_pdf_font(pdf):
    """
    为 FPDF 实例注册正文字体（族名 Body），并尽量注册粗体。
    返回 {"family": 族名, "cjk": 是否含中文字形, "bold": 是否有粗体}。
    """
    # 嵌入微软雅黑等商业字体会触发 fontTools 的 "MERG NOT subset" 噪音，
    # 它只是提示部分表不可子集化，不影响产物，这里静音。
    import logging

    logging.getLogger("fontTools").setLevel(logging.ERROR)

    info = {"family": "Body", "cjk": False, "bold": False}

    regular, cjk = find_pdf_font(bold=False)
    if regular is None:
        warn("未找到可用字体，回退到 Helvetica（无法显示中文）")
        pdf.set_font("Helvetica", size=11)
        info["family"] = "Helvetica"
        return info

    try:
        pdf.add_font("Body", "", str(regular))
    except Exception as e:
        warn(f"字体加载失败（{regular.name}）：{e}；回退到 Helvetica")
        pdf.set_font("Helvetica", size=11)
        info["family"] = "Helvetica"
        return info

    bold_path, _ = find_pdf_font(bold=True)
    if bold_path is not None and bold_path != regular:
        try:
            pdf.add_font("Body", "B", str(bold_path))
            info["bold"] = True
        except Exception:
            info["bold"] = False

    info["cjk"] = cjk
    pdf.set_font("Body", size=11)
    if not cjk:
        warn(
            f"当前字体 {regular.name} 不含中文字形，中文会显示为空白。"
            "请把中文字体（如 msyh.ttc / simhei.ttf）放到 fonts\\ 目录，"
            "或用环境变量 TRANS_EVERYTHING_FONT 指定字体文件。"
        )
    return info


# ── Excel / 表格 ──────────────────────────────────────────


def _is_blank_cell(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _trim_rows(rows: list[list]) -> list[list]:
    """去掉尾部整行为空的行、以及尾部整列为空的列（对齐 pandas 的输出习惯）"""
    rows = [list(row) for row in rows]
    while rows and all(_is_blank_cell(v) for v in rows[-1]):
        rows.pop()
    if not rows:
        return []
    width = max(len(row) for row in rows)
    if any(len(row) < width for row in rows):
        rows = [row + [None] * (width - len(row)) for row in rows]
    while width > 0 and all(_is_blank_cell(row[width - 1]) for row in rows):
        width -= 1
    return [row[:width] for row in rows]


def read_excel_rows(source: Path, sheet: str | int = 0) -> list[list]:
    """
    读取 Excel 为二维单元格值（不依赖 pandas，保留原始类型）：
    "00123" 仍是字符串、10.5 仍是数字、日期仍是 datetime。
    .xls 用 python-calamine，.xlsx 用 openpyxl。
    """
    if source.suffix.lower() == ".xls":
        ensure_dependencies("python_calamine")
        from python_calamine import CalamineWorkbook

        workbook = CalamineWorkbook.from_path(str(source))
        try:
            names = list(workbook.sheet_names)
            if isinstance(sheet, str) and sheet:
                if sheet not in names:
                    raise ValueError(
                        f"工作簿中没有名为「{sheet}」的工作表，现有：{', '.join(names)}"
                    )
                worksheet = workbook.get_sheet_by_name(sheet)
            else:
                index = int(sheet or 0)
                if index >= len(names):
                    raise ValueError(f"工作表序号越界：共 {len(names)} 个")
                worksheet = workbook.get_sheet_by_index(index)
            rows = worksheet.to_python(skip_empty_area=False)
        finally:
            try:
                workbook.close()
            except Exception:
                pass
        return _trim_rows(rows)

    ensure_dependencies("openpyxl")
    from openpyxl import load_workbook

    workbook = load_workbook(str(source), read_only=True, data_only=True)
    try:
        if isinstance(sheet, str) and sheet:
            if sheet not in workbook.sheetnames:
                raise ValueError(
                    f"工作簿中没有名为「{sheet}」的工作表，"
                    f"现有：{', '.join(workbook.sheetnames)}"
                )
            worksheet = workbook[sheet]
        else:
            index = int(sheet or 0)
            if index >= len(workbook.worksheets):
                raise ValueError(f"工作表序号越界：共 {len(workbook.worksheets)} 个")
            worksheet = workbook.worksheets[index]
        rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
    finally:
        workbook.close()
    return _trim_rows(rows)


def excel_sheet_names(source: Path) -> list[str]:
    """列出工作簿中的 sheet 名（失败时返回空列表）"""
    try:
        if source.suffix.lower() == ".xls":
            from python_calamine import CalamineWorkbook

            return list(CalamineWorkbook.from_path(str(source)).sheet_names)
        from openpyxl import load_workbook

        wb = load_workbook(str(source), read_only=True, data_only=True)
        try:
            return list(wb.sheetnames)
        finally:
            wb.close()
    except Exception:
        return []


# 形如 123 / -1.5 / 0.25，且不允许前导零（00123 必须保持文本）
_NUMERIC_PATTERN = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")


def format_cell_text(value) -> str:
    """单元格值转 CSV/TSV 文本：None→空串、3.0→"3"、日期用 ISO 格式"""
    import datetime as _dt
    import math

    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, _dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, (_dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return str(int(value))
        return format(value, ".15g")
    return str(value)


def coerce_text_cell(text: str):
    """
    纯文本单元格转数字：只有「无前导零的规范数字」才转，
    00123 / 身份证号 / 1e5 一律保持文本。
    """
    if not isinstance(text, str) or not text:
        return text
    if _NUMERIC_PATTERN.match(text):
        return float(text) if "." in text else int(text)
    return text


_INVALID_SHEET_CHARS = set('[]:*?/\\')


def write_excel_rows(target: Path, rows: list[list], title: str = "Sheet1") -> None:
    """把二维值写入 .xlsx（不依赖 pandas）"""
    ensure_dependencies("openpyxl")
    from openpyxl import Workbook

    workbook = Workbook()
    worksheet = workbook.active
    safe_title = "".join(ch for ch in (title or "Sheet1") if ch not in _INVALID_SHEET_CHARS)
    worksheet.title = (safe_title or "Sheet1")[:31]
    wrote_any = False
    for row in rows:
        values = list(row)
        if not values:
            continue
        worksheet.append(values)
        wrote_any = True
    if not wrote_any:
        worksheet.append([""])
    workbook.save(str(target))
