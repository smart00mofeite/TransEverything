"""
CSV → TSV 转换

依赖: 标准库 csv（无需第三方依赖）
"""

import csv

from core.utils import detect_text_encoding, get_output_path, validate_input_file


def convert(input_path: str, output_dir: str = "") -> str:
    """将 CSV 转换为 TSV（自动识别 UTF-8/GBK，输出无 BOM 的 UTF-8）"""
    src = validate_input_file(input_path, [".csv"])
    dst = get_output_path(src, "tsv", output_dir or None)

    encoding = detect_text_encoding(src)
    with open(str(src), encoding=encoding, newline="") as f_in:
        reader = csv.reader(f_in)
        with open(str(dst), "w", encoding="utf-8", newline="") as f_out:
            writer = csv.writer(f_out, delimiter="\t")
            for row in reader:
                writer.writerow(row)
    return str(dst)
