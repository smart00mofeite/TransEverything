"""
PDF → PNG（逐页渲染成图片）

扫描件 PDF 没有文本层，靠这一条给它一个可用出口：每页渲染成一张 PNG。
依赖: pypdfium2（自包含 PDFium，打包友好）
"""

from pathlib import Path

from core.utils import (
    ensure_dependencies,
    is_encrypted_pdf,
    validate_input_file,
    warn,
)

_MIN_DPI = 72
_MAX_DPI = 600


def convert(
    input_path: str,
    output_dir: str = "",
    dpi: int = 150,
    page_range: str = "",
) -> str:
    """
    将 PDF 的每一页渲染为 PNG，输出到「<源文件名>_页面」目录。

    Args:
        dpi: 渲染分辨率（72–600，默认 150；打印用途可用 300）
        page_range: 预留参数，形如 "1-3,5"；留空表示全部页
    Returns:
        输出目录路径
    """
    ensure_dependencies("pypdfium2")

    import pypdfium2 as pdfium

    src = validate_input_file(input_path, [".pdf"])
    dpi = max(_MIN_DPI, min(_MAX_DPI, int(dpi)))

    base = Path(output_dir) if output_dir else src.parent
    target = base / f"{src.stem}_页面"
    target.mkdir(parents=True, exist_ok=True)

    try:
        pdf = pdfium.PdfDocument(str(src))
    except Exception as e:  # noqa: BLE001
        if is_encrypted_pdf(src):
            raise ValueError(
                f"{src.name} 已加密（需要打开密码），请先去除密码后再转换。"
            ) from e
        raise ValueError(
            f"无法打开 PDF {src.name}：{e}。文件可能已损坏，或并非标准 PDF。"
        ) from e

    try:
        total = len(pdf)
        if total == 0:
            raise ValueError(f"{src.name} 没有可渲染的页面。")

        wanted = _parse_page_range(page_range, total)
        scale = dpi / 72.0
        written = 0
        for index in wanted:
            page = pdf[index - 1]
            try:
                image = page.render(scale=scale).to_pil()
                if image.mode not in ("RGB", "RGBA", "L"):
                    image = image.convert("RGB")
                image.save(str(target / f"{src.stem}_{index:03d}.png"), "PNG")
                written += 1
            finally:
                page.close()
    finally:
        pdf.close()

    if written < total and page_range:
        warn(f"按页码范围只渲染了 {written}/{total} 页")
    return str(target)


def _parse_page_range(spec: str, total: int) -> list[int]:
    """把 "1-3,5" 解析为页码列表；空串返回全部页"""
    if not spec or not spec.strip():
        return list(range(1, total + 1))

    pages: list[int] = []
    for chunk in spec.replace("，", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_s, _, end_s = chunk.partition("-")
            start = int(start_s) if start_s.strip() else 1
            end = int(end_s) if end_s.strip() else total
            pages.extend(range(max(1, start), min(total, end) + 1))
        else:
            pages.append(int(chunk))
    cleaned = sorted({p for p in pages if 1 <= p <= total})
    return cleaned or list(range(1, total + 1))
