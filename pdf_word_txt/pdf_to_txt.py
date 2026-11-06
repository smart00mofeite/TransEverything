"""
PDF → TXT 转换

依赖: pdfplumber
"""

from core.utils import (
    ensure_dependencies,
    extract_pdf_pages,
    get_output_path,
    validate_input_file,
    warn,
)

_NO_TEXT_HINT = (
    "没有提取到任何文本，该 PDF 很可能是扫描件（整页是图片），不含文本层。"
    "本项目当前不含 OCR，请先用 OCR 工具（PaddleOCR / RapidOCR / Acrobat 的"
    "「识别文本」）生成带文本层的 PDF。"
)


def convert(input_path: str, output_dir: str = "") -> str:
    """将 PDF 转换为 TXT（页与页之间空一行）"""
    ensure_dependencies("pdfplumber")

    src = validate_input_file(input_path, [".pdf"])
    dst = get_output_path(src, "txt", output_dir or None)

    pages = extract_pdf_pages(src)

    if not any(pages):
        raise ValueError(f"{src.name} 转换失败：{_NO_TEXT_HINT}")

    dst.write_text("\n\n".join(pages), encoding="utf-8")

    empty_pages = [i + 1 for i, text in enumerate(pages) if not text]
    if empty_pages:
        shown = ", ".join(str(p) for p in empty_pages[:10])
        more = " 等" if len(empty_pages) > 10 else ""
        warn(f"{len(empty_pages)} 页没有文本（第 {shown}{more} 页），这些页在 txt 中为空")

    return str(dst)
