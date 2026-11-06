"""
Excel (.xlsx/.xls) → CSV 转换

依赖: openpyxl（.xlsx）/ python-calamine（.xls）；不再依赖 pandas
"""

import csv

from core.utils import (
    ensure_dependencies,
    excel_sheet_names,
    format_cell_text,
    get_output_path,
    read_excel_rows,
    validate_input_file,
    warn,
)


def convert(input_path: str, output_dir: str = "", sheet_name: str = "") -> str:
    """将 Excel 转换为 CSV（默认第一个 sheet，保留 00123 这类文本）"""
    src = validate_input_file(input_path, [".xlsx", ".xls"])
    if src.suffix.lower() == ".xls":
        ensure_dependencies("python_calamine")
    else:
        ensure_dependencies("openpyxl")

    dst = get_output_path(src, "csv", output_dir or None)
    rows = read_excel_rows(src, sheet_name or 0)

    names = excel_sheet_names(src)
    if len(names) > 1 and not sheet_name:
        warn(
            f"工作簿包含 {len(names)} 个 sheet（{', '.join(names)}），"
            f"默认只导出第一个；需要其他 sheet 请加 --sheet"
        )

    with open(str(dst), "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow([format_cell_text(value) for value in row])
    return str(dst)
