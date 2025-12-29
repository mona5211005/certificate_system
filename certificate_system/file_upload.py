import os
import uuid
from datetime import datetime
from typing import Tuple, Dict
import streamlit as st
from file_validator import validate_upload_file
from database import save_file_metadata

# 上传文件存储目录（自动创建）
UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def generate_unique_filename(original_name: str) -> str:
    """
    生成唯一文件名（避免重复）
    :param original_name: 原始文件名
    :return: 唯一文件名
    """
    ext = os.path.splitext(original_name)[1]
    unique_id = uuid.uuid4().hex[:8]  # 8位唯一ID
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{timestamp}_{unique_id}{ext}"


def save_uploaded_file(file, user_id: int) -> Tuple[bool, str, Dict]:
    """
    保存上传的文件到本地，并记录元信息
    :param file: Streamlit上传的文件对象
    :param user_id: 上传用户ID
    :return: (是否成功, 错误信息, 文件元信息)
    """
    # 1. 验证文件
    is_valid, err_msg, file_type = validate_upload_file(file)
    if not is_valid:
        return False, err_msg, {}

    # 2. 生成唯一文件名和存储路径
    original_name = file.name
    unique_name = generate_unique_filename(original_name)
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    # 3. 保存文件到本地
    try:
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
        file_size = os.path.getsize(file_path)
    except Exception as e:
        return False, f"保存文件失败：{str(e)}", {}

    # 4. 记录文件元信息到数据库
    if not save_file_metadata(user_id, original_name, file_path, file_type, file_size):
        # 数据库记录失败，删除已保存的文件
        os.remove(file_path)
        return False, "保存文件元信息失败", {}

    # 5. 返回文件元信息
    file_meta = {
        "original_name": original_name,
        "saved_name": unique_name,
        "file_path": file_path,
        "file_type": file_type,
        "file_size": file_size,
        "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return True, "", file_meta


def render_file_upload_page(user_id: int, user_role: str):
    """
    渲染文件上传页面（适配学生/教师角色）
    :param user_id: 当前登录用户ID
    :param user_role: 用户角色（student/teacher）
    """
    st.title("证书文件上传")

    # 上传说明
    st.subheader("上传要求")
    st.markdown(f"""
    - 支持格式：PDF、JPG、PNG、JPEG、BMP
    - 大小限制：单个文件≤10MB
    - 角色说明：{"学生上传个人证书，教师上传指导学生证书" if user_role == "student" else "教师可上传指导学生的证书"}
    """)

    # 文件上传组件
    uploaded_file = st.file_uploader(
        "选择证书文件",
        type=["pdf", "jpg", "jpeg", "png", "bmp"],
        accept_multiple_files=False
    )

    if uploaded_file:
        # 显示文件基本信息
        st.subheader("文件信息")
        file_size = len(uploaded_file.getbuffer())
        st.write(f"文件名：{uploaded_file.name}")
        st.write(f"大小：{file_size / 1024:.2f} KB")

        # 上传按钮
        if st.button("确认上传"):
            with st.spinner("正在上传文件..."):
                is_success, err_msg, file_meta = save_uploaded_file(uploaded_file, user_id)
                if is_success:
                    st.success("文件上传成功！")
                    # 显示上传结果
                    st.subheader("上传结果")
                    st.write(f"原始文件名：{file_meta['original_name']}")
                    st.write(f"存储路径：{file_meta['file_path']}")
                    st.write(f"文件类型：{file_meta['file_type']}")
                    st.write(f"上传时间：{file_meta['upload_time']}")
                else:
                    st.error(f"上传失败：{err_msg}")

    # 显示用户已上传的文件
    st.subheader("已上传文件")
    from database import get_user_uploaded_files
    uploaded_files = get_user_uploaded_files(user_id)
    if uploaded_files:
        # 转换为DataFrame显示
        import pandas as pd
        df_files = pd.DataFrame(uploaded_files)
        df_files["file_size_MB"] = df_files["file_size"] / 1024 / 1024
        df_files = df_files[["file_id", "file_name", "file_type", "file_size_MB", "upload_time"]]
        df_files.rename(columns={
            "file_id": "文件ID",
            "file_name": "文件名",
            "file_type": "文件类型",
            "file_size_MB": "大小(MB)",
            "upload_time": "上传时间"
        }, inplace=True)
        st.dataframe(df_files)
    else:
        st.info("暂无已上传的文件")