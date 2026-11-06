"""
TSV → CSV 转换

依赖: 标准库 csv（无需第三方依赖）
"""

import csv

from core.utils import detect_text_encoding, get_output_path, validate_input_file


def convert(input_path: str, output_dir: str = "") -> str:
    """将 TSV 转换为 CSV（自动识别 UTF-8/GBK，输出带 BOM 的 UTF-8 便于 Excel 打开）"""
    src = validate_input_file(input_path, [".tsv"])
    dst = get_output_path(src, "csv", output_dir or None)

    # 用 detect_text_encoding：输入带 BOM 时会按 utf-8-sig 读取，
    # 否则 BOM 会残留在第一列表头里（'\\ufeffid'）
    encoding = detect_text_encoding(src)
    with open(str(src), encoding=encoding, newline="") as f_in:
        reader = csv.reader(f_in, delimiter="\t")
        with open(str(dst), "w", encoding="utf-8-sig", newline="") as f_out:
            writer = csv.writer(f_out)
            for row in reader:
                writer.writerow(row)
    return str(dst)
