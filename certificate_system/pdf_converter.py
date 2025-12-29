import os
import fitz  # PyMuPDF，需安装：pip install pymupdf
from PIL import Image
import io
from typing import Optional, Tuple


def pdf_to_image(pdf_bytes: bytes, dpi: int = 300) -> Optional[Image.Image]:
    """
    将PDF文件（首页）转换为PIL Image对象
    :param pdf_bytes: PDF文件二进制内容（bytes/memoryview）
    :param dpi: 图片分辨率（默认300DPI）
    :return: PIL Image对象（失败返回None）
    """
    try:
        # 转换为bytes（兼容memoryview）
        if isinstance(pdf_bytes, memoryview):
            pdf_bytes = bytes(pdf_bytes)

        # 打开PDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count == 0:
            print("PDF文件无页面")
            return None

        # 提取首页
        page = doc[0]
        # 设置分辨率
        mat = fitz.Matrix(dpi / 72, dpi / 72)  # 72是PDF默认DPI
        pix = page.get_pixmap(matrix=mat)

        # 转换为PIL Image
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        doc.close()
        return img

    except Exception as e:
        print(f"PDF转图片失败：{str(e)}")
        return None


def save_pdf_image(img: Image.Image, save_path: str, format: str = "PNG") -> bool:
    """
    保存PDF转换后的图片
    :param img: PIL Image对象
    :param save_path: 保存路径
    :param format: 保存格式（PNG/JPG）
    :return: 是否保存成功
    """
    try:
        # 创建目录
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        img.save(save_path, format=format, quality=95)
        return True
    except Exception as e:
        print(f"保存PDF图片失败：{str(e)}")
        return False


# 测试函数
if __name__ == "__main__":
    # 测试样本PDF
    test_pdf_path = "sample_certificates/test_certificate.pdf"
    if os.path.exists(test_pdf_path):
        with open(test_pdf_path, "rb") as f:
            pdf_data = f.read()
        img = pdf_to_image(pdf_data)
        if img:
            save_pdf_image(img, "sample_certificates/test_pdf_converted.png")
            print("PDF转图片测试成功！")
        else:
            print("PDF转图片测试失败！")
    else:
        print("测试PDF文件不存在！")