import os
from typing import Tuple, Dict

# 允许的文件格式
ALLOWED_EXTENSIONS = {
    'pdf': 'pdf',
    'jpg': 'image',
    'jpeg': 'image',
    'png': 'image',
    'bmp': 'image'
}
# 文件大小限制：10MB（字节）
MAX_FILE_SIZE = 10 * 1024 * 1024


def get_file_extension(filename: str) -> str:
    """获取文件后缀（小写）"""
    return os.path.splitext(filename)[1].lower().lstrip('.')


def validate_file_format(filename: str, file_content: memoryview) -> Tuple[bool, str, str]:
    """
    验证文件格式（后缀+文件头，兼容memoryview）
    :param filename: 文件名
    :param file_content: 文件内容（memoryview类型）
    :return: (是否有效, 错误信息, 文件类型)
    """
    # 1. 验证后缀
    ext = get_file_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"文件格式不支持！仅允许：{', '.join(ALLOWED_EXTENSIONS.keys())}", ""

    # 2. 核心修复：将memoryview转换为bytes（关键）
    try:
        file_bytes = bytes(file_content)  # 转换为bytes类型
    except Exception as e:
        return False, f"转换文件内容失败：{str(e)}", ""

    # 3. 文件头特征（通用格式）
    FILE_SIGNATURES = {
        'pdf': b'%PDF-',
        'jpg': b'\xFF\xD8\xFF',
        'jpeg': b'\xFF\xD8\xFF',
        'png': b'\x89PNG\r\n\x1a\n',
        'bmp': b'BM'
    }

    # 4. 校验文件头（现在可以用startswith了）
    signature = FILE_SIGNATURES.get(ext)
    if not signature:
        return False, f"不支持的文件类型：{ext}", ""

    # 补充：处理文件内容过短的情况
    if len(file_bytes) < len(signature):
        return False, "文件内容过短，无法验证类型！", ""

    if not file_bytes.startswith(signature):
        return False, f"文件后缀为{ext}，但实际不是{ext}文件（文件头不匹配）！", ""

    return True, "", ALLOWED_EXTENSIONS[ext]


def validate_file_size(file_size: int) -> Tuple[bool, str]:
    """
    验证文件大小
    :param file_size: 文件大小（字节）
    :return: (是否有效, 错误信息)
    """
    if file_size > MAX_FILE_SIZE:
        return False, f"文件大小超过限制（最大10MB）！当前大小：{file_size / 1024 / 1024:.2f}MB"
    return True, ""


def validate_upload_file(file) -> Tuple[bool, str, str]:
    """
    统一验证文件（格式+大小）
    :param file: Streamlit上传的文件对象
    :return: (是否有效, 错误信息, 文件类型)
    """
    # 1. 空值判断
    if file is None:
        return False, "未选择上传文件！", ""

    # 2. 读取文件内容和大小（兼容memoryview）
    try:
        file_content = file.getbuffer()  # 返回memoryview
        file_size = len(file_content)  # memoryview可直接取长度
    except Exception as e:
        return False, f"读取文件内容失败：{str(e)}", ""

    # 3. 验证大小
    is_size_valid, size_err = validate_file_size(file_size)
    if not is_size_valid:
        return False, size_err, ""

    # 4. 验证格式（直接传入memoryview，内部转换为bytes）
    is_format_valid, format_err, file_type = validate_file_format(file.name, file_content)
    if not is_format_valid:
        return False, format_err, ""

    return True, "", file_type