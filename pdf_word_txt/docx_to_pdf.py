"""
Word (DOCX) → PDF 转换

依赖: python-docx, fpdf2
"""

from core.utils import (
    ensure_dependencies,
    get_output_path,
    is_docx_table,
    iter_docx_blocks,
    open_docx,
    setup_pdf_font,
    validate_input_file,
)


def _heading_size(style_name: str) -> tuple[int, bool]:
    """按 Word 标题样式返回 (字号, 是否加粗)"""
    name = (style_name or "").strip()
    if name.startswith("Title"):
        return 16, True
    if name.startswith("Heading"):
        digits = [c for c in name if c.isdigit()]
        level = int(digits[0]) if digits else 1
        return {1: 15, 2: 13, 3: 12}.get(level, 11), True
    return 11, False


def convert(input_path: str, output_dir: str = "", font_size: int = 11) -> str:
    """将 Word (.docx) 转换为 PDF，保留段落、表格、标题层级与加粗"""
    ensure_dependencies("docx", "fpdf")

    from fpdf import FPDF

    src = validate_input_file(input_path, [".docx", ".doc"])
    dst = get_output_path(src, "pdf", output_dir or None)

    doc = open_docx(src)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    font = setup_pdf_font(pdf)
    family = font["family"]
    has_bold = font["bold"]

    # 显式宽度避免 fpdf2 multi_cell(w=0) 在换行后 x 未复位的 bug
    cell_w = pdf.w - pdf.r_margin - pdf.l_margin

    def write(text: str, size: float, bold: bool = False) -> None:
        if bold and has_bold:
            pdf.set_font(family, style="B", size=size)
        else:
            pdf.set_font(family, size=size)
        # new_x/new_y 显式复位：否则 multi_cell 结束后光标留在行尾，
        # 下一段会从右侧起写、内容跑到页外
        pdf.multi_cell(
            cell_w,
            round(size * 0.55, 2),
            text,
            wrapmode="WORD",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    for block in iter_docx_blocks(doc):
        if is_docx_table(block):
            for row_index, row in enumerate(block.rows):
                cells = [c.text.replace("\n", " ").strip() for c in row.cells]
                line = " | ".join(cells).strip(" |")
                if not line:
                    continue
                write(line, font_size - 0.5, bold=(row_index == 0))
            pdf.ln(3)
            continue

        text = (block.text or "").strip()
        if not text:
            pdf.ln(round(font_size * 0.5, 2))
            continue

        style_name = ""
        try:
            if block.style is not None:
                style_name = block.style.name or ""
        except Exception:
            style_name = ""

        size, bold = _heading_size(style_name)
        if size == 11:
            size = font_size
        write(text, size, bold=bold)
        if size > font_size:  # 标题后稍作留白
            pdf.ln(2)

    pdf.output(str(dst))
    return str(dst)
