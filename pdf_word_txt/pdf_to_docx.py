"""
PDF → Word (DOCX) 转换

依赖: pdfplumber, python-docx
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
    "「识别文本」）生成带文本层的 PDF，或先转成图片再 OCR。"
)


def convert(input_path: str, output_dir: str = "") -> str:
    """将 PDF 转换为 Word (.docx)，按页分页，逐行成段"""
    ensure_dependencies("pdfplumber", "docx")

    from docx import Document

    src = validate_input_file(input_path, [".pdf"])
    dst = get_output_path(src, "docx", output_dir or None)

    pages = extract_pdf_pages(src)
    if not any(pages):
        raise ValueError(f"{src.name} 转换失败：{_NO_TEXT_HINT}")

    doc = Document()
    empty_pages: list[int] = []
    for index, text in enumerate(pages):
        if index > 0:
            doc.add_page_break()
        if not text:
            empty_pages.append(index + 1)
            continue
        for line in text.splitlines():
            doc.add_paragraph(line)

    doc.save(str(dst))

    if empty_pages:
        shown = ", ".join(str(p) for p in empty_pages[:10])
        more = " 等" if len(empty_pages) > 10 else ""
        warn(f"{len(empty_pages)} 页没有文本（第 {shown}{more} 页），已保留为空白页")

    return str(dst)
