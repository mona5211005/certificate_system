import pandas as pd
import random
import string
from database import (
    check_account_exists,
    validate_account_format,
    create_user,
    get_user_by_account
)
from typing import Dict, List, Tuple


def generate_random_password(length: int = 8) -> str:
    """生成随机密码（字母+数字）"""
    letters = string.ascii_letters
    digits = string.digits
    all_chars = letters + digits
    return ''.join(random.choice(all_chars) for _ in range(length))


def validate_excel_file(file_path: str) -> Tuple[bool, List[str], pd.DataFrame]:
    """验证Excel文件格式"""
    errors = []
    try:
        df = pd.read_excel(file_path)
        # 检查必填列
        required_columns = ["学（工）号", "姓名", "角色类型", "单位", "邮箱"]
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            errors.append(f"缺失必填列：{', '.join(missing_cols)}")
            return False, errors, df

        # 检查数据非空
        df = df.dropna(subset=required_columns)
        if len(df) == 0:
            errors.append("Excel文件中无有效数据（必填列存在空值）")
            return False, errors, df

        return True, errors, df
    except Exception as e:
        errors.append(f"读取Excel文件失败：{str(e)}")
        return False, errors, pd.DataFrame()


def import_users_from_excel(file_path: str, update_existing: bool = False) -> Dict[str, any]:
    """
    从Excel批量导入用户
    :param file_path: Excel文件路径
    :param update_existing: 是否更新已存在的用户（False则跳过）
    :return: 导入报告
    """
    # 1. 验证文件
    is_valid, errors, df = validate_excel_file(file_path)
    if not is_valid:
        return {
            "success": False,
            "message": "文件验证失败",
            "errors": errors,
            "stats": {"total": 0, "success": 0, "failed": 0, "duplicate": 0},
            "details": []
        }

    # 2. 处理每条记录
    total = len(df)
    success_count = 0
    failed_count = 0
    duplicate_count = 0
    details = []

    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel行号（从2开始）
        account_id = str(row["学（工）号"]).strip()
        name = str(row["姓名"]).strip()
        role = row["角色类型"].strip().lower()
        department = str(row["单位"]).strip()
        email = str(row["邮箱"]).strip()
        password = row.get("初始密码", generate_random_password())

        # 角色映射（统一为英文）
        role_map = {"学生": "student", "教师": "teacher", "管理员": "admin"}
        if role not in role_map:
            errors.append(f"第{row_num}行：角色类型无效（仅支持学生/教师/管理员）")
            failed_count += 1
            details.append({
                "row": row_num,
                "account_id": account_id,
                "name": name,
                "status": "失败",
                "reason": "角色类型无效"
            })
            continue
        role = role_map[role]

        # 验证学工号格式
        if not validate_account_format(account_id, role):
            errors.append(f"第{row_num}行：{role}学/工号格式错误（学生13位，教师/管理员8位）")
            failed_count += 1
            details.append({
                "row": row_num,
                "account_id": account_id,
                "name": name,
                "status": "失败",
                "reason": f"{role}学/工号格式错误"
            })
            continue

        # 检查是否已存在
        if check_account_exists(account_id):
            if update_existing:
                # 暂不实现更新逻辑，仅跳过
                details.append({
                    "row": row_num,
                    "account_id": account_id,
                    "name": name,
                    "status": "跳过",
                    "reason": "用户已存在（未开启更新）"
                })
            else:
                duplicate_count += 1
                details.append({
                    "row": row_num,
                    "account_id": account_id,
                    "name": name,
                    "status": "重复",
                    "reason": "用户已存在"
                })
            continue

        # 创建用户
        if create_user(
                account_id=account_id,
                name=name,
                role=role,
                department=department,
                email=email,
                password=password,
                created_by="admin_import"
        ):
            success_count += 1
            details.append({
                "row": row_num,
                "account_id": account_id,
                "name": name,
                "status": "成功",
                "reason": "",
                "password": password  # 返回生成的密码
            })
        else:
            failed_count += 1
            details.append({
                "row": row_num,
                "account_id": account_id,
                "name": name,
                "status": "失败",
                "reason": "创建用户失败（数据库错误）"
            })

    # 3. 生成报告
    return {
        "success": True,
        "message": "导入完成",
        "errors": errors,
        "stats": {
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "duplicate": duplicate_count
        },
        "details": details
    }


# 测试函数
if __name__ == "__main__":
    # 测试导入
    report = import_users_from_excel("sample_users.xlsx")
    print("导入报告：")
    print(f"总记录数：{report['stats']['total']}")
    print(f"成功：{report['stats']['success']}")
    print(f"失败：{report['stats']['failed']}")
    print(f"重复：{report['stats']['duplicate']}")
    print("详细信息：")
    for detail in report["details"]:
        print(detail)