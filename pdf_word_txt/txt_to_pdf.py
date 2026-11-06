"""
TXT → PDF 转换

依赖: fpdf2
"""

from core.utils import (
    ensure_dependencies,
    get_output_path,
    read_text_auto,
    setup_pdf_font,
    validate_input_file,
)


def convert(input_path: str, output_dir: str = "", font_size: int = 11) -> str:
    """将 TXT 转换为 PDF（自动识别编码，长行按文字宽度换行）"""
    ensure_dependencies("fpdf")

    from fpdf import FPDF

    src = validate_input_file(input_path, [".txt"])
    dst = get_output_path(src, "pdf", output_dir or None)

    text = read_text_auto(src)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    font = setup_pdf_font(pdf)
    family = font["family"]
    pdf.set_font(family, size=font_size)

    # 显式宽度避免 fpdf2 multi_cell(w=0) 在换行后 x 未复位的 bug
    cell_w = pdf.w - pdf.r_margin - pdf.l_margin
    line_h = round(font_size * 0.5, 2)

    for line in text.splitlines():
        if not line.strip():
            pdf.ln(line_h)
            continue
        # multi_cell + WORD 换行：超长行（含无空格的中文）不会再被截断
        # new_x/new_y 必须显式指定：multi_cell 默认把光标留在上一个位置，
        # 会导致下一行从右侧起写、内容跑到页外（排版错乱）
        pdf.multi_cell(
            cell_w, line_h, line, wrapmode="WORD", new_x="LMARGIN", new_y="NEXT"
        )

    pdf.output(str(dst))
    return str(dst)
