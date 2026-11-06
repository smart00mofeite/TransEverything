"""
JPG → PNG 转换

依赖: Pillow
"""

from core.utils import ensure_dependencies, get_output_path, validate_input_file

# PNG 不支持 CMYK，遇到必须转 RGB（否则 PIL 报 cannot write mode CMYK as PNG）
_PNG_MODES = {"1", "L", "LA", "RGB", "RGBA", "P"}


def convert(input_path: str, output_dir: str = "") -> str:
    """将 JPG 转换为 PNG（按 EXIF 方向摆正、CMYK 自动转 RGB）"""
    ensure_dependencies("PIL")

    from PIL import Image, ImageOps

    src = validate_input_file(input_path, [".jpg", ".jpeg"])
    dst = get_output_path(src, "png", output_dir or None)

    with Image.open(str(src)) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in _PNG_MODES:
            img = img.convert("RGB")
        img.save(str(dst), "PNG")
    return str(dst)
