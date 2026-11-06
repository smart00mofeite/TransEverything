"""
SVG → JPG 转换（先渲染为 PNG 再做白底合成）

优先使用 resvg_py（wheel 自带依赖，打包友好），cairosvg 仅作兜底。
"""

import io

from core.utils import ensure_dependencies, get_output_path, validate_input_file


def convert(
    input_path: str,
    output_dir: str = "",
    scale: float = 1.0,
    width: int = 0,
    height: int = 0,
    quality: int = 95,
) -> str:
    """将 SVG 转换为 JPG

    Args:
        scale: 缩放比例
        width: 输出宽度（像素），0 表示自动
        height: 输出高度（像素），0 表示自动
        quality: JPEG 质量 (1-100)
    """
    ensure_dependencies("PIL")

    from PIL import Image

    src = validate_input_file(input_path, [".svg"])
    dst = get_output_path(src, "jpg", output_dir or None)

    scale = max(0.01, float(scale or 1.0))
    size_kwargs = {}
    if width > 0:
        size_kwargs["width"] = int(width)
    if height > 0:
        size_kwargs["height"] = int(height)
    if not size_kwargs and scale != 1.0:
        size_kwargs["zoom"] = scale

    png_bytes = _render_png(src, size_kwargs, scale, width, height)

    # PNG -> JPG（白色背景，去除透明通道）
    image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    background.paste(image, mask=image)
    background.convert("RGB").save(str(dst), "JPEG", quality=quality)
    return str(dst)


def _render_png(src, size_kwargs, scale, width, height) -> bytes:
    """渲染为 PNG 字节；resvg_py 优先，cairosvg 兜底"""
    try:
        import resvg_py
    except ImportError:
        resvg_py = None

    if resvg_py is not None:
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
