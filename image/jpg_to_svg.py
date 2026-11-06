"""
JPG → SVG 转换

把 JPG 的原始字节以 base64 嵌入 SVG（不重新编码，避免二次 JPEG 压缩掉画质）。
注意：这是"位图装进 SVG 容器"，不是描边矢量化；需要真正矢量化请用 Potrace / Inkscape 追踪位图。

依赖: Pillow（仅用于读取尺寸）
"""

import base64

from core.utils import ensure_dependencies, get_output_path, validate_input_file


def convert(input_path: str, output_dir: str = "") -> str:
    """将 JPG/JPEG 转换为 SVG（原始字节 base64 嵌入）"""
    ensure_dependencies("PIL")

    from PIL import Image

    src = validate_input_file(input_path, [".jpg", ".jpeg"])
    dst = get_output_path(src, "svg", output_dir or None)

    with Image.open(str(src)) as img:
        width, height = img.size

    # 关键：直接嵌入源字节。旧实现用 img.save(buf, "JPEG") 重新压一遍，
    # 等于第二次有损压缩，JPG→SVG 会明显掉画质。
    data = src.read_bytes()
    b64_data = base64.b64encode(data).decode("ascii")

    svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <image width="{width}" height="{height}"
         xlink:href="data:image/jpeg;base64,{b64_data}"/>
</svg>
"""
    dst.write_text(svg_content, encoding="utf-8")
    return str(dst)
