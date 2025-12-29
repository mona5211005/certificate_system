from PIL import Image
import base64
from io import BytesIO

# 定义尺寸预设（明确像素值）
STANDARD_SIZES = {
    "A4": (2480, 3508),  # A4高清像素
    "A5": (1754, 2480),  # A5高清像素
    "custom": (1200, 1600)  # 自定义尺寸
}


def rotate_image(img: Image.Image, angle: int) -> Image.Image:
    """
    旋转图片（保持图片完整，不裁剪）
    :param img: 原始图片对象
    :param angle: 旋转角度（0/90/180/270）
    :return: 旋转后的图片对象
    """
    if angle == 0:
        return img.copy()
    # expand=True 确保旋转后图片完整显示
    return img.rotate(angle, expand=True)


def resize_image(img: Image.Image, size_type: str) -> Image.Image:
    """
    调整图片尺寸（保持宽高比，不拉伸）
    :param img: 原始图片对象
    :param size_type: 尺寸类型（A4/A5/custom）
    :return: 调整后的图片对象
    """
    # 获取目标尺寸
    target_size = STANDARD_SIZES.get(size_type, STANDARD_SIZES["custom"])

    # 计算等比例缩放后的尺寸
    img.thumbnail(target_size, Image.Resampling.LANCZOS)
    return img


def pil_image_to_bytes(img: Image.Image) -> bytes:
    """
    将PIL图片转换为字节流（用于Streamlit显示）
    :param img: PIL图片对象
    :return: 字节流
    """
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def image_to_base64(img: Image.Image) -> str:
    """
    将PIL图片转换为Base64编码
    :param img: PIL图片对象
    :return: Base64编码字符串
    """
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode("utf-8")