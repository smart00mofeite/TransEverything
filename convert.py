#!/usr/bin/env python3
"""
trans_everything - 通用文件格式转换工具（命令行）

一键互转：
  PDF ↔ Word(DOCX) ↔ TXT
  Excel(XLSX) ↔ CSV ↔ TSV
  PNG ↔ SVG ↔ JPG

用法:
  python convert.py <源格式> <目标格式> <输入文件> [选项]

示例:
  python convert.py pdf docx 报告.pdf
  python convert.py xlsx csv 数据表.xlsx --sheet Sheet1
  python convert.py png jpg 图片.png -o ./output/ -q 90
  python convert.py --list          # 列出支持的转换
"""

import argparse
import importlib
import os
import sys

# Windows 终端编码兼容
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# 确保项目根目录在模块搜索路径中
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 支持的转换映射表
# 格式: { "源格式_目标格式": "模块路径" }
CONVERSION_MAP = {
    # PDF ↔ Word ↔ TXT（doc 走同一个模块，由模块给出"请另存为 docx"的明确提示）
    "pdf_docx":   "pdf_word_txt.pdf_to_docx",
    "pdf_txt":    "pdf_word_txt.pdf_to_txt",
    "pdf_png":    "pdf_word_txt.pdf_to_png",
    "docx_pdf":   "pdf_word_txt.docx_to_pdf",
    "docx_txt":   "pdf_word_txt.docx_to_txt",
    "doc_pdf":    "pdf_word_txt.docx_to_pdf",
    "doc_txt":    "pdf_word_txt.docx_to_txt",
    "txt_pdf":    "pdf_word_txt.txt_to_pdf",
    "txt_docx":   "pdf_word_txt.txt_to_docx",
    # Excel ↔ CSV ↔ TSV
    "xlsx_csv":   "excel_csv_tsv.excel_to_csv",
    "csv_xlsx":   "excel_csv_tsv.csv_to_excel",
    "xlsx_tsv":   "excel_csv_tsv.excel_to_tsv",
    "tsv_xlsx":   "excel_csv_tsv.tsv_to_excel",
    "csv_tsv":    "excel_csv_tsv.csv_to_tsv",
    "tsv_csv":    "excel_csv_tsv.tsv_to_csv",
    "xls_csv":    "excel_csv_tsv.excel_to_csv",
    "xls_tsv":    "excel_csv_tsv.excel_to_tsv",
    # PNG ↔ SVG ↔ JPG
    "png_svg":    "image.png_to_svg",
    "svg_png":    "image.svg_to_png",
    "png_jpg":    "image.png_to_jpg",
    "jpg_png":    "image.jpg_to_png",
    "svg_jpg":    "image.svg_to_jpg",
    "jpg_svg":    "image.jpg_to_svg",
}

# 格式别名（标准化）
FORMAT_ALIASES = {
    "word": "docx",
    "excel": "xlsx",
    "jpeg": "jpg",
    "text": "txt",
}

# 各格式对应的人类可读描述
FORMAT_DESCRIPTIONS = {
    "pdf":  "PDF 文档",
    "docx": "Word 文档 (.docx)",
    "doc":  "Word 文档 (.doc)",
    "txt":  "纯文本 (.txt)",
    "xlsx": "Excel 工作簿 (.xlsx)",
    "xls":  "Excel 工作簿 (.xls)",
    "csv":  "CSV 表格 (.csv)",
    "tsv":  "TSV 表格 (.tsv)",
    "png":  "PNG 图片",
    "jpg":  "JPEG 图片",
    "svg":  "SVG 矢量图",
}


def normalize_format(fmt: str) -> str:
    """标准化格式名称"""
    fmt = fmt.lower().lstrip(".")
    return FORMAT_ALIASES.get(fmt, fmt)


def list_conversions() -> str:
    """列出所有支持的转换"""
    lines = ["=" * 62, "  trans_everything - Supported Conversions", "=" * 62, ""]

    groups = [
        ("[PDF / Word / TXT]", ["pdf", "docx", "doc", "txt"]),
        ("[PDF 页面渲染]", ["pdf", "png"]),
        ("[Excel / CSV / TSV]", ["xlsx", "xls", "csv", "tsv"]),
        ("[PNG / SVG / JPG]", ["png", "svg", "jpg"]),
    ]

    for title, fmts in groups:
        lines.append(f"  {title}")
        lines.append("  " + "-" * 46)
        shown: set[tuple[str, str]] = set()
        for src in fmts:
            for dst in fmts:
                if src == dst:
                    continue
                pair = tuple(sorted((src, dst)))
                if pair in shown:
                    continue
                if f"{src}_{dst}" in CONVERSION_MAP:
                    lines.append(
                        f"    {FORMAT_DESCRIPTIONS.get(src, src):18s} -> "
                        f"{FORMAT_DESCRIPTIONS.get(dst, dst)}"
                    )
                    shown.add(pair)
        lines.append("")

    lines += [
        "=" * 62,
        "用法: python convert.py <源格式> <目标格式> <输入文件> [选项]",
        "提示: .doc 请先在 Word/WPS 中另存为 .docx；.xls 需要 python-calamine",
        "=" * 62,
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="trans_everything - 通用文件格式转换工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
支持互转的格式组:
  PDF / DOCX / TXT
  XLSX / CSV / TSV
  PNG / SVG / JPG

示例:
  python convert.py pdf docx 报告.pdf
  python convert.py png jpg 图片.png -o ./output/ -q 90
  python convert.py xlsx csv 数据表.xlsx --sheet "Sheet1"
        """,
    )

    parser.add_argument("source_format", nargs="?", help="源格式 (pdf/docx/txt/xlsx/csv/tsv/png/svg/jpg)")
    parser.add_argument("target_format", nargs="?", help="目标格式 (同上)")
    parser.add_argument("input_file", nargs="?", help="输入文件路径")
    parser.add_argument("-o", "--output-dir", default="", help="输出目录（默认与输入文件同目录）")
    parser.add_argument("--list", action="store_true", help="列出所有支持的转换")
    parser.add_argument(
        "--sheet", default="",
        help="Excel 工作表名（转换 Excel 时可选，默认第一个 sheet）"
    )
    parser.add_argument(
        "-q", "--quality", type=int, default=95,
        help="JPEG 质量 1-100（默认 95）"
    )
    parser.add_argument(
        "-s", "--scale", type=float, default=1.0,
        help="SVG 输出缩放比例（默认 1.0）"
    )
    parser.add_argument(
        "--width", type=int, default=0,
        help="输出宽度（SVG→PNG 时可选）"
    )
    parser.add_argument(
        "--height", type=int, default=0,
        help="输出高度（SVG→PNG 时可选）"
    )
    parser.add_argument(
        "--font-size", type=int, default=11,
        help="生成 PDF 时的正文字号（默认 11）"
    )
    parser.add_argument(
        "--dpi", type=int, default=150,
        help="PDF→PNG 的渲染分辨率（默认 150，打印可用 300）"
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # --list 模式：不需要任何第三方依赖
    if args.list:
        print(list_conversions())
        return

    # 校验参数
    if not args.source_format or not args.target_format or not args.input_file:
        parser.print_help()
        print("\n[!] 错误: 请指定源格式、目标格式和输入文件")
        print("   提示: 使用 --list 查看所有支持的转换")
        sys.exit(1)

    src = normalize_format(args.source_format)
    dst = normalize_format(args.target_format)
    key = f"{src}_{dst}"

    module_path = CONVERSION_MAP.get(key)
    if module_path is None:
        print(f"[!] 不支持的转换: {args.source_format} -> {args.target_format}")
        print(f"   提示: 使用 --list 查看所有支持的转换")
        reverse_key = f"{dst}_{src}"
        if reverse_key in CONVERSION_MAP:
            print(f"   注意: 支持反向转换 {args.target_format} -> {args.source_format}")
        sys.exit(1)

    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        print(f"[!] 无法加载转换模块: {module_path}")
        sys.exit(1)

    # 收集额外参数
    extra_kwargs = {}

    # Excel 相关：sheet 参数
    if src in ("xlsx", "xls") and args.sheet:
        extra_kwargs["sheet_name"] = args.sheet

    # 图片相关参数
    if src == "svg" and dst in ("png", "jpg"):
        if args.scale != 1.0:
            extra_kwargs["scale"] = args.scale
        if args.width:
            extra_kwargs["width"] = args.width
        if args.height:
            extra_kwargs["height"] = args.height

    if dst == "jpg":
        extra_kwargs["quality"] = args.quality

    # 生成 PDF 时传递字号
    if dst == "pdf":
        extra_kwargs["font_size"] = args.font_size

    # PDF 逐页渲染成图片
    if src == "pdf" and dst == "png":
        extra_kwargs["dpi"] = args.dpi

    if args.output_dir:
        extra_kwargs["output_dir"] = args.output_dir

    print(f"[*] 正在转换: {args.input_file}")
    print(f"    {src.upper()} -> {dst.upper()}")

    try:
        result_path = mod.convert(args.input_file, **extra_kwargs)
        print(f"[+] 转换成功: {result_path}")
    except Exception as e:
        print(f"[-] 转换失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
