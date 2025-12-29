import streamlit as st
import sqlite3
import pandas as pd
from form_handler import glm4v_api, get_all_users, update_user_status, get_all_certificate_info, update_deadline, \
    ROLE_DISPLAY_MAP, GLM4V_API_KEY
from data_export import generate_excel_template, parse_excel_users, batch_import_users, export_certificate_data, \
    format_certificate_dataframe, format_user_dataframe


def admin_page():
    global GLM4V_API_KEY
    st.title("⚙️ 系统管理后台")

    # 1. API配置
    st.subheader("🔑 GLM-4V API 配置")
    config = glm4v_api.load_api_config()
    current_key = config.get("glm4v_api_key", "")
    col1, col2 = st.columns([3, 1])
    with col1:
        new_key = st.text_input("智谱AI API Key (格式: sk-xxx/xxx)", value=current_key, type="password")
    with col2:
        if st.button("保存配置"):
            glm4v_api.save_api_config(new_key)
            GLM4V_API_KEY = new_key
    st.info("💡 直接粘贴你的完整APIkey即可，无需拆分，格式为 sk-xxxx/xxxx")
    st.divider()

    # 2. 批量导入用户
    st.subheader("👥 批量导入用户")
    template_path = generate_excel_template()
    with open(template_path, "rb") as f:
        st.download_button(label="📥 下载导入模板", data=f, file_name="用户导入模板.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    uploaded_file = st.file_uploader("选择Excel文件", type=["xlsx"], accept_multiple_files=False)
    if uploaded_file:
        st.info("📝 导入说明：学工号格式-学生13位、教师/管理员8位；角色支持中文/英文；密码需含字母+数字")
        if st.button("🚀 开始导入", type="primary"):
            with st.spinner("解析并导入用户..."):
                parse_success, parse_result = parse_excel_users(uploaded_file)
                if not parse_success:
                    st.error(f"解析失败：{parse_result}")
                else:
                    import_report = batch_import_users(parse_result)
                    st.session_state.import_report = import_report
                    st.subheader("📊 导入结果报告")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("总条数", import_report["total"])
                    with col2:
                        st.metric("成功条数", import_report["success"])
                    with col3:
                        st.metric("失败条数", len(import_report["failed"]))
                    if import_report["failed"]:
                        with st.expander("查看失败详情", expanded=True):
                            [st.error(fail) for fail in import_report["failed"]]
                    else:
                        st.success("🎉 所有用户导入成功！")
    st.divider()

    # 3. 用户管理
    st.subheader("👤 用户管理")
    filter_role = st.selectbox("筛选角色", ["全部", "student", "teacher", "admin"],
                               format_func=lambda x: ROLE_DISPLAY_MAP.get(x, "全部"))
    users = get_all_users(None if filter_role == "全部" else filter_role)
    if users:
        df_users = format_user_dataframe(users)
        st.dataframe(df_users, hide_index=True, use_container_width=True)

        st.subheader("账号状态管理")
        selected_account = st.text_input("输入学/工号修改状态")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("启用账号"):
                if update_user_status(selected_account, True):
                    st.success(f"✅ 账号 {selected_account} 已启用！")
                else:
                    st.error(f"❌ 学工号不存在！")
        with col2:
            if st.button("禁用账号"):
                if update_user_status(selected_account, False):
                    st.success(f"✅ 账号 {selected_account} 已禁用！")
                else:
                    st.error(f"❌ 学工号不存在！")
    else:
        st.info("暂无用户数据！")
    st.divider()

    # 4. 证书数据管理
    st.subheader("📄 证书数据管理")
    col1, col2, col3 = st.columns(3)
    with col1:
        award_category = st.selectbox("获奖类别", ["", "国家级", "省级"], key="filter_category")
    with col2:
        award_level = st.selectbox("获奖等级", ["", "一等奖", "二等奖", "三等奖", "金奖", "银奖", "铜奖", "优秀奖"],
                                   key="filter_level")
    with col3:
        submitter_role = st.selectbox("提交者角色", ["", "student", "teacher"],
                                      format_func=lambda x: ROLE_DISPLAY_MAP.get(x, "全部"), key="filter_role")

    filters = {"award_category": award_category, "award_level": award_level,
               "submitter_role": submitter_role if submitter_role else None}
    certs = get_all_certificate_info(filters)
    if certs:
        df_certs = format_certificate_dataframe(certs)
        show_cols = ["证书ID", "学生学号", "学生姓名", "竞赛项目", "获奖类别", "获奖等级", "指导教师", "提交人",
                     "提交状态", "提交时间"]
        st.dataframe(df_certs[show_cols], hide_index=True, use_container_width=True)

        st.subheader("📊 数据统计")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总记录数", len(certs))
        with col2:
            st.metric("已提交数", len(df_certs[df_certs["提交状态"] == "已提交"]))
        with col3:
            st.metric("草稿数", len(df_certs[df_certs["提交状态"] == "草稿"]))
        with col4:
            st.metric("国家级奖项数", len(df_certs[df_certs["获奖类别"] == "国家级"]))
    else:
        st.info("暂无证书数据！")
    st.divider()

    # 5. 数据导出
    st.subheader("📤 数据导出")
    export_certificate_data()
    st.divider()

    # 6. 系统配置
    st.subheader("🔧 系统配置")
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'submit_deadline'")
    current_deadline = cursor.fetchone()[0]
    conn.close()

    new_deadline = st.text_input("提交截止时间", value=current_deadline, placeholder="格式：YYYY-MM-DD HH:MM:SS",
                                 key="new_deadline")
    if st.button("✅ 保存截止时间", type="primary"):
        if update_deadline(new_deadline):
            st.success(f"截止时间已更新为：{new_deadline}")
        else:
            st.error("时间格式错误！")