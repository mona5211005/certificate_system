import streamlit as st
import os
from PIL import Image
import io
from pdf_converter import pdf_to_image
from image_processor import process_image, pil_image_to_bytes, STANDARD_SIZES
from file_validator import validate_upload_file

# 页面配置
st.set_page_config(page_title="证书预览与提交系统", layout="wide")


def render_certificate_preview(user_id: int):
    """
    渲染证书预览和提交界面
    :param user_id: 当前登录用户ID
    """
    st.title("📄 证书预览与材料提交")

    # 1. 文件上传区域
    st.subheader("步骤1：上传证书文件")
    uploaded_file = st.file_uploader(
        "支持PDF/图片格式（PDF自动提取首页）",
        type=["pdf", "jpg", "jpeg", "png", "bmp"],
        key="certificate_uploader"
    )

    if uploaded_file:
        # 2. 文件验证
        is_valid, err_msg, file_type = validate_upload_file(uploaded_file)
        if not is_valid:
            st.error(f"文件验证失败：{err_msg}")
            return

        # 3. 文件转换（PDF→图片，图片直接读取）
        st.subheader("步骤2：文件转换与预览设置")
        col1, col2 = st.columns(2)

        with col1:
            # 旋转角度选择
            rotate_angle = st.selectbox(
                "图片旋转角度",
                [0, 90, 180, 270],
                key="rotate_angle"
            )
            # 尺寸选择
            target_size = st.selectbox(
                "图片尺寸预设",
                list(STANDARD_SIZES.keys()),
                key="target_size"
            )

        # 处理文件
        try:
            if file_type == "pdf":
                # PDF转图片
                img = pdf_to_image(uploaded_file.getbuffer())
                if not img:
                    st.error("PDF转图片失败！")
                    return
            else:
                # 直接读取图片
                img = Image.open(uploaded_file)

            # 图片处理（旋转+尺寸）
            processed_img, base64_str = process_image(img, rotate_angle, target_size)

            # 4. 预览区域
            with col2:
                st.info("✅ 文件处理完成，预览如下：")
                # 转换为二进制用于Streamlit预览
                img_bytes = pil_image_to_bytes(processed_img)
                st.image(
                    img_bytes,
                    caption=f"预览图（尺寸：{processed_img.size[0]}x{processed_img.size[1]}）",
                    use_column_width=False,
                    width=400
                )

            # 5. Base64编码展示（API调用用）
            with st.expander("🔍 查看Base64编码（用于API调用）", expanded=False):
                st.code(base64_str[:200] + "..." if len(base64_str) > 200 else base64_str)

            # 6. 提交按钮
            st.subheader("步骤3：提交材料")
            if st.button("📤 确认提交材料", type="primary", key="submit_btn"):
                # 这里可扩展：保存Base64/图片到数据库、记录提交状态等
                st.success(f"""
                    ✅ 材料提交成功！
                    - 用户ID：{user_id}
                    - 文件类型：{file_type}
                    - 图片尺寸：{processed_img.size[0]}x{processed_img.size[1]}
                    - Base64编码长度：{len(base64_str)}
                """)

                # 可选：保存处理后的图片到本地
                save_path = f"sample_certificates/submitted_{user_id}_{uploaded_file.name}.png"
                processed_img.save(save_path)
                st.info(f"处理后的图片已保存至：{save_path}")

        except Exception as e:
            st.error(f"文件处理失败：{str(e)}")
            return


# 模拟登录（实际需集成到原有auth_system）
def main():
    # 模拟用户ID（实际从登录态获取）
    user_id = 1001
    render_certificate_preview(user_id)


if __name__ == "__main__":
    # 创建样本目录
    os.makedirs("sample_certificates", exist_ok=True)
    main()