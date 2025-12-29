import streamlit as st
from form_handler import init_session_state, login_page, register_page, render_file_upload_page
from admin_panel import admin_page

# 页面全局配置（必须放在最顶部）
st.set_page_config(page_title="证书提交与管理系统", layout="wide", initial_sidebar_state="collapsed")


# --------------------------
# 系统主函数 - 唯一入口
# --------------------------
def main():
    # 初始化会话状态
    init_session_state()

    # 未登录：显示登录/注册页
    if not st.session_state.logged_in:
        tab1, tab2 = st.tabs(["登录", "学生注册"])
        with tab1:
            login_page()
        with tab2:
            register_page()
    # 已登录：根据角色分发页面
    else:
        # 右上角退出按钮
        col1, col2 = st.columns([9, 1])
        with col2:
            if st.button("退出登录"):
                st.session_state.logged_in = False
                st.session_state.user_info = {}
                st.session_state.upload_original_img = None
                st.session_state.ocr_processing = False
                st.rerun()

        # 角色路由
        user_role = st.session_state.user_info["role"]
        user_id = st.session_state.user_info["user_id"]
        if user_role == "admin":
            admin_page()
        else:
            render_file_upload_page(user_id, user_role)


# 启动系统
if __name__ == "__main__":
    main()