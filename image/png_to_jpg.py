"""
PNG → JPG 转换

依赖: Pillow
"""

from core.utils import ensure_dependencies, validate_input_file, get_output_path


def convert(input_path: str, output_dir: str = "", quality: int = 95) -> str:
    """将 PNG 转换为 JPG（白色背景填充透明度）"""
    ensure_dependencies("PIL")

    from PIL import Image

    src = validate_input_file(input_path, [".png"])
    dst = get_output_path(src, "jpg", output_dir or None)

    img = Image.open(str(src)).convert("RGBA")
    # 创建白色背景，合成图像以处理透明区域
    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
    background.paste(img, mask=img)
    result = background.convert("RGB")
    result.save(str(dst), "JPEG", quality=quality)
    return str(dst)
