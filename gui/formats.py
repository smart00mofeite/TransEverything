"""格式矩阵：源扩展名 → 可选目标格式（中文标签），与 convert.py 的 CONVERSION_MAP 对应。"""

from pathlib import Path

# 目标格式 → (中文名, 简短说明)
TARGET_LABELS = {
    "docx": ("Word 文档", ".docx"),
    "pdf": ("PDF 文档", ".pdf"),
    "txt": ("纯文本", ".txt"),
    "png": ("PNG 图片", ".png"),
    "jpg": ("JPEG 图片", ".jpg"),
    "svg": ("SVG 矢量图", ".svg"),
    "xlsx": ("Excel 工作簿", ".xlsx"),
    "csv": ("CSV 表格", ".csv"),
    "tsv": ("TSV 表格", ".tsv"),
}

# 源扩展名 → 允许的目标格式（顺序即界面展示顺序）
SOURCE_TARGETS: dict[str, tuple[str, ...]] = {
    ".pdf": ("docx", "txt", "png"),
    ".docx": ("pdf", "txt"),
    ".doc": ("pdf", "txt"),
    ".txt": ("pdf", "docx"),
    ".xlsx": ("csv", "tsv"),
    ".xls": ("csv", "tsv"),
    ".csv": ("xlsx", "tsv"),
    ".tsv": ("xlsx", "csv"),
    ".png": ("jpg", "svg"),
    ".jpg": ("png", "svg"),
    ".jpeg": ("png", "svg"),
    ".svg": ("png", "jpg"),
}

# 扩展名 → 中文类型名
KIND_LABELS = {
    ".pdf": "PDF 文档",
    ".docx": "Word 文档",
    ".doc": "Word 文档（旧版）",
    ".txt": "纯文本",
    ".xlsx": "Excel 工作簿",
    ".xls": "Excel 工作簿（旧版）",
    ".csv": "CSV 表格",
    ".tsv": "TSV 表格",
    ".png": "PNG 图片",
    ".jpg": "JPEG 图片",
    ".jpeg": "JPEG 图片",
    ".svg": "SVG 矢量图",
}

# 扩展名 → 徽标颜色
BADGE_COLORS = {
    "pdf": ("#FDECEC", "#C0392B"),
    "docx": ("#E8F0FE", "#1A56DB"),
    "doc": ("#E8F0FE", "#1A56DB"),
    "xlsx": ("#E7F6EC", "#16794A"),
    "xls": ("#E7F6EC", "#16794A"),
    "csv": ("#E7F6EC", "#16794A"),
    "tsv": ("#E7F6EC", "#16794A"),
    "txt": ("#F1F2F5", "#4B5563"),
    "png": ("#F3E8FF", "#7E22CE"),
    "jpg": ("#F3E8FF", "#7E22CE"),
    "jpeg": ("#F3E8FF", "#7E22CE"),
    "svg": ("#FFF4E5", "#B45309"),
}

SUPPORTED_EXTENSIONS = tuple(SOURCE_TARGETS.keys())


def extension_of(path: Path) -> str:
    return path.suffix.lower()


def is_supported(path: Path) -> bool:
    return extension_of(path) in SOURCE_TARGETS


def kind_label(path: Path) -> str:
    return KIND_LABELS.get(extension_of(path), "未知类型")


def target_label(target: str) -> str:
    name, ext = TARGET_LABELS.get(target, (target.upper(), f".{target}"))
    return f"{name} {ext}"


def common_targets(paths: list[Path]) -> list[str]:
    """所有文件都支持的目标格式（取交集），保持稳定顺序。"""
    valid = [extension_of(p) for p in paths if is_supported(p)]
    if not valid:
        return []

    common = set(SOURCE_TARGETS[valid[0]])
    for ext in valid[1:]:
        common &= set(SOURCE_TARGETS[ext])

    ordered: list[str] = []
    for ext in valid:
        for target in SOURCE_TARGETS[ext]:
            if target in common and target not in ordered:
                ordered.append(target)
    return ordered


def accepts_target(path: Path, target: str) -> bool:
    return target in SOURCE_TARGETS.get(extension_of(path), ())


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
