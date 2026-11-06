"""
SVG → PNG 转换

优先使用 resvg_py（Rust 实现，wheel 自带全部依赖，打包到别人机器上不会缺 DLL）；
只有没装 resvg_py 时才回退到 cairosvg（后者依赖系统 cairo 库）。
"""

from core.utils import ensure_dependencies, get_output_path, validate_input_file


def convert(
    input_path: str,
    output_dir: str = "",
    scale: float = 1.0,
    width: int = 0,
    height: int = 0,
) -> str:
    """将 SVG 转换为 PNG

    Args:
        scale: 缩放比例（默认 1.0）
        width: 输出宽度（像素），0 表示自动
        height: 输出高度（像素），0 表示自动
    """
    src = validate_input_file(input_path, [".svg"])
    dst = get_output_path(src, "png", output_dir or None)

    scale = max(0.01, float(scale or 1.0))
    size_kwargs = {}
    if width > 0:
        size_kwargs["width"] = int(width)
    if height > 0:
        size_kwargs["height"] = int(height)
    if not size_kwargs and scale != 1.0:
        size_kwargs["zoom"] = scale

    png_bytes = _render_png(src, size_kwargs, scale, width, height)
    dst.write_bytes(png_bytes)
    return str(dst)


def _render_png(src, size_kwargs, scale, width, height) -> bytes:
    """渲染为 PNG 字节；resvg_py 优先，cairosvg 兜底"""
    try:
        import resvg_py
    except ImportError:
        resvg_py = None

    if resvg_py is not None:
        # 传路径而不是文本：SVG 声明非 UTF-8 编码时由 resvg 自行处理
        return resvg_py.svg_to_bytes(svg_path=str(src), **size_kwargs)

    ensure_dependencies("cairosvg")
    import cairosvg

    kwargs = {}
    if width > 0:
        kwargs["output_width"] = width
    if height > 0:
        kwargs["output_height"] = height
    if scale != 1.0:
        kwargs["scale"] = scale
    return cairosvg.svg2png(bytestring=src.read_bytes(), **kwargs)
