"""
Word (DOCX) → TXT 转换

依赖: python-docx
"""

from core.utils import (
    ensure_dependencies,
    get_output_path,
    is_docx_table,
    iter_docx_blocks,
    open_docx,
    validate_input_file,
)


def convert(input_path: str, output_dir: str = "") -> str:
    """将 Word (.docx) 转换为 TXT，表格按行输出、单元格用制表符分隔"""
    ensure_dependencies("docx")

    src = validate_input_file(input_path, [".docx", ".doc"])
    dst = get_output_path(src, "txt", output_dir or None)

    doc = open_docx(src)

    lines: list[str] = []
    for block in iter_docx_blocks(doc):
        if is_docx_table(block):
            for row in block.rows:
                cells = [c.text.replace("\n", " ").strip() for c in row.cells]
                lines.append("\t".join(cells))
            lines.append("")
        else:
            lines.append(block.text or "")

    dst.write_text("\n".join(lines), encoding="utf-8")
    return str(dst)
