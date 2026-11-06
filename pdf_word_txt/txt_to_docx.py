"""
TXT → Word (DOCX) 转换

依赖: python-docx
"""

from core.utils import (
    ensure_dependencies,
    get_output_path,
    read_text_auto,
    validate_input_file,
)


def convert(input_path: str, output_dir: str = "") -> str:
    """将 TXT 转换为 Word (.docx)（自动识别 UTF-8 / GBK 等编码）"""
    ensure_dependencies("docx")

    from docx import Document

    src = validate_input_file(input_path, [".txt"])
    dst = get_output_path(src, "docx", output_dir or None)

    text = read_text_auto(src)
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    doc.save(str(dst))
    return str(dst)
