import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from typing import List, Dict, Optional
from form_handler import get_all_certificate_info, ROLE_DISPLAY_MAP, create_user, check_account_exists, \
    validate_account_format, validate_password

EXCEL_TEMPLATE_FOLDER = "excel_templates"
os.makedirs(EXCEL_TEMPLATE_FOLDER, exist_ok=True)


# --------------------------
# 1. 生成用户导入Excel模板
# --------------------------
def generate_excel_template():
    template_data = {
        "学（工）号": ["2025000000001", "88888889"],
        "姓名": ["张三", "李四"],
        "角色类型": ["student", "teacher"],
        "单位": ["计算机学院", "教务处"],
        "邮箱": ["zhangsan@school.edu.cn", "lisi@school.edu.cn"],
        "初始密码": ["123456Ab", "654321Ba"]
    }
    df = pd.DataFrame(template_data)
    template_path = os.path.join(EXCEL_TEMPLATE_FOLDER, "用户导入模板.xlsx")
    df.to_excel(template_path, index=False)
    return template_path


# --------------------------
# 2. 解析Excel用户数据
# --------------------------
def parse_excel_users(file) -> tuple[bool, any]:
    try:
        df = pd.read_excel(file, dtype={"学（工）号": str})
        required_cols = ["学（工）号", "姓名", "角色类型", "单位", "邮箱"]
        if not all(col in df.columns for col in required_cols):
            return False, f"Excel表头缺失，必需包含：{required_cols}"

        ROLE_CN_TO_EN = {"学生": "student", "教师": "teacher", "管理员": "admin"}
        users = []
        for idx, row in df.iterrows():
            account_id = str(row["学（工）号"]).strip()
            name = str(row["姓名"]).strip()
            role_cn = str(row["角色类型"]).strip()
            role = ROLE_CN_TO_EN.get(role_cn.lower(), role_cn.strip().lower())
            department = str(row["单位"]).strip()
            email = str(row["邮箱"]).strip()
            password = str(row.get("初始密码", "123456Ab")).strip()

            errors = []
            if not account_id or not name or not role or not department or not email: errors.append("必填字段为空")
            if role not in ["student", "teacher", "admin"]: errors.append(f"角色类型错误（{role}）")
            if not validate_account_format(account_id, role): errors.append(f"学工号格式错误")
            if check_account_exists(account_id): errors.append("学工号已存在")
            if not validate_password(password): errors.append("密码必须至少8位，包含字母+数字")

            users.append(
                {"row": idx + 2, "account_id": account_id, "name": name, "role": role, "department": department,
                 "email": email, "password": password, "errors": errors})
        return True, users
    except Exception as e:
        return False, f"Excel解析失败：{str(e)}"


# --------------------------
# 3. 批量导入用户
# --------------------------
def batch_import_users(users: List[dict]) -> Dict:
    success_count = 0
    failed_records = []
    total_count = len(users)
    for user in users:
        if user["errors"]:
            failed_records.append(f"第{user['row']}行：{'; '.join(user['errors'])}")
            continue
        if create_user(user["account_id"], user["name"], user["role"], user["department"], user["email"],
                       user["password"]):
            success_count += 1
        else:
            failed_records.append(f"第{user['row']}行：创建用户失败")
    return {"success": success_count, "failed": failed_records, "total": total_count}


# --------------------------
# 4. 证书数据导出（CSV + Excel）
# --------------------------
def export_certificate_data():
    certs = get_all_certificate_info()
    if not certs:
        st.info("暂无数据可导出！")
        return

    df_export = pd.DataFrame(certs)
    df_export["提交状态"] = df_export["is_submitted"].map({0: "草稿", 1: "已提交"})
    df_export["提交人角色"] = df_export["submitter_role"].map(ROLE_DISPLAY_MAP)

    export_cols = ["cert_id", "student_id", "student_name", "student_college",
                   "competition_project", "award_category", "award_level",
                   "competition_type", "organizer", "award_time", "tutor_name",
                   "submitter_name", "submitter_role", "submitter_dept",
                   "is_submitted", "submit_time", "file_name"]
    df_export = df_export[export_cols]

    timestamp = datetime.now().strftime("%Y%m%d")
    filename_csv = f"证书数据_{timestamp}.csv"
    filename_xlsx = f"证书数据_{timestamp}.xlsx"

    col1, col2 = st.columns(2)
    with col1:
        csv_data = df_export.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(label="📥 导出CSV格式", data=csv_data, file_name=filename_csv, mime="text/csv")
    with col2:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_export.to_excel(writer, sheet_name="证书数据", index=False)
        excel_data = output.getvalue()
        st.download_button(label="📥 导出Excel格式", data=excel_data, file_name=filename_xlsx,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# --------------------------
# 5. 格式化证书数据为前端展示用DataFrame
# --------------------------
def format_certificate_dataframe(certs: List[dict]) -> pd.DataFrame:
    df_certs = pd.DataFrame(certs)
    df_certs.rename(columns={
        "cert_id": "证书ID", "user_id": "用户ID", "file_id": "文件ID",
        "student_college": "学生学院", "competition_project": "竞赛项目",
        "student_id": "学生学号", "student_name": "学生姓名",
        "award_category": "获奖类别", "award_level": "获奖等级",
        "competition_type": "竞赛类型", "organizer": "主办单位",
        "award_time": "获奖时间", "tutor_name": "指导教师",
        "is_submitted": "提交状态", "submit_time": "提交时间",
        "submitter_name": "提交人", "submitter_role": "提交人角色",
        "submitter_dept": "提交人部门", "file_name": "文件名"
    }, inplace=True)
    df_certs["提交状态"] = df_certs["提交状态"].map({0: "草稿", 1: "已提交"})
    df_certs["提交人角色"] = df_certs["提交人角色"].map(ROLE_DISPLAY_MAP)
    return df_certs


# --------------------------
# 6. 格式化用户数据为前端展示用DataFrame
# --------------------------
def format_user_dataframe(users: List[dict]) -> pd.DataFrame:
    df_users = pd.DataFrame(users)
    df_users.rename(columns={
        "user_id": "用户ID", "account_id": "学/工号", "name": "姓名",
        "role": "角色", "department": "学院/部门", "email": "邮箱",
        "is_active": "账号状态", "created_at": "创建时间"
    }, inplace=True)
    df_users["账号状态"] = df_users["账号状态"].map({1: "启用", 0: "禁用"})
    df_users["角色"] = df_users["角色"].map(ROLE_DISPLAY_MAP)
    return df_users