"""
CSV → Excel (.xlsx) 转换

依赖: openpyxl；不再依赖 pandas
"""

import csv

from core.utils import (
    coerce_text_cell,
    detect_text_encoding,
    ensure_dependencies,
    get_output_path,
    validate_input_file,
    write_excel_rows,
)


def convert(input_path: str, output_dir: str = "") -> str:
    """将 CSV 转换为 Excel（自动识别 UTF-8/GBK，保留前导零）"""
    ensure_dependencies("openpyxl")

    src = validate_input_file(input_path, [".csv"])
    dst = get_output_path(src, "xlsx", output_dir or None)

    encoding = detect_text_encoding(src)
    with open(str(src), encoding=encoding, newline="") as f:
        rows = [[coerce_text_cell(cell) for cell in row] for row in csv.reader(f)]

    write_excel_rows(dst, rows)
    return str(dst)
