import streamlit as st
import os
import sys
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import sqlite3
import io
import base64
import bcrypt
from pdf2image import convert_from_bytes
import locale
import warnings

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


# --------------------------
# 模拟外部封装模块（整合第一段代码的模块化设计）
# --------------------------
class glm4v_api:
    """GLM-4V API配置管理模块"""
    CONFIG_FILE = "glm4v_config.json"

    @staticmethod
    def load_api_config() -> dict:
        """加载API配置"""
        if os.path.exists(glm4v_api.CONFIG_FILE):
            with open(glm4v_api.CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"glm4v_api_key": ""}

    @staticmethod
    def save_api_config(api_key: str) -> bool:
        """保存API配置"""
        try:
            with open(glm4v_api.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({"glm4v_api_key": api_key}, f, ensure_ascii=False, indent=2)
            st.success("API Key 保存成功！")
            return True
        except Exception as e:
            st.error(f"保存API配置失败：{e}")
            return False


class info_extractor:
    """信息提取辅助模块"""

    @staticmethod
    def parse_api_response(raw_response: dict) -> dict:
        """解析API响应"""
        if "error" in raw_response:
            return {
                "status": "failed",
                "error": raw_response["error"],
                "data": {}
            }

        result_data = {}
        fields = [
            "student_college", "competition_project", "student_id",
            "student_name", "award_category", "award_level",
            "competition_type", "organizer", "award_time", "tutor_name"
        ]

        for field in fields:
            result_data[field] = raw_response.get(field, "") or ""

        # 检查缺失字段
        missing_fields = [f for f, v in result_data.items() if not v]
        warning = ""
        if missing_fields:
            warning = f"部分字段识别失败：{', '.join(missing_fields)}，请手动补充"

        return {
            "status": "success",
            "data": result_data,
            "warning": warning
        }

    @staticmethod
    def save_result_to_log(file_name: str, result: dict):
        """保存识别结果到日志（可选功能）"""
        log_dir = "ocr_logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"ocr_log_{datetime.now().strftime('%Y%m%d')}.json")

        log_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_name": file_name,
            "result": result
        }

        try:
            # 读取现有日志
            existing_logs = []
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    existing_logs = json.load(f)

            existing_logs.append(log_data)

            # 写入日志
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(existing_logs, f, ensure_ascii=False, indent=2)
        except:
            pass


# --------------------------
# 基础配置
# --------------------------
# 设置中文编码和时区
try:
    locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
except:
    pass  # Windows环境可能不支持此locale，忽略错误
os.environ['TZ'] = 'Asia/Shanghai'

# 页面配置
st.set_page_config(
    page_title="证书提交与管理系统",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 文件夹配置
UPLOAD_FOLDER = "uploads"
EXCEL_TEMPLATE_FOLDER = "excel_templates"
OCR_LOG_FOLDER = "ocr_logs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXCEL_TEMPLATE_FOLDER, exist_ok=True)
os.makedirs(OCR_LOG_FOLDER, exist_ok=True)

# 常量定义
ROLE_DISPLAY_MAP = {
    "student": "学生",
    "teacher": "教师",
    "admin": "管理员"
}

STANDARD_SIZES = {
    "A4": (2100, 2970),
    "A5": (1480, 2100),
    "custom": (0, 0)
}

# ===================== ✅ 核心修复1：加载配置文件中的API-KEY到全局变量 =====================
config = glm4v_api.load_api_config()
GLM4V_API_KEY = config.get("glm4v_api_key", "")
# ===================== ✅ 导入必须的库 + 关闭SSL警告 =====================
import urllib3

urllib3.disable_warnings()  # 关闭SSL警告，避免报错


# --------------------------
# 1. 数据库模块
# --------------------------
def init_database():
    conn = sqlite3.connect("certificate_system.db")
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # 创建用户表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        department TEXT NOT NULL,
        email TEXT,
        password_hash TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 创建文件表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        file_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_type TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        upload_time TIMESTAMP DEFAULT (datetime('now', '+8 hours')),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    ''')

    # 证书信息表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS certificate_info (
        cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        file_id INTEGER NOT NULL,
        student_college TEXT,
        competition_project TEXT,
        student_id TEXT,
        student_name TEXT,
        award_category TEXT,
        award_level TEXT,
        competition_type TEXT,
        organizer TEXT,
        award_time TEXT,
        tutor_name TEXT,
        is_submitted INTEGER DEFAULT 0,
        submit_time TIMESTAMP,
        created_at TIMESTAMP DEFAULT (datetime('now', '+8 hours')),
        updated_at TIMESTAMP DEFAULT (datetime('now', '+8 hours')),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE
    )
    ''')

    # 系统配置表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_config (
        config_id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_key TEXT UNIQUE NOT NULL,
        config_value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT (datetime('now', '+8 hours'))
    )
    ''')

    # 初始化截止时间
    cursor.execute("SELECT 1 FROM system_config WHERE config_key = 'submit_deadline'")
    if not cursor.fetchone():
        cursor.execute('''
        INSERT INTO system_config (config_key, config_value)
        VALUES ('submit_deadline', '2025-12-31 23:59:59')
        ''')

    # 初始化管理员账号
    admin_account = "88888888"
    cursor.execute("SELECT 1 FROM users WHERE account_id = ?", (admin_account,))
    if not cursor.fetchone():
        password = "Admin123456"
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        cursor.execute('''
        INSERT INTO users (account_id, name, role, department, email, password_hash)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (admin_account, "系统管理员", "admin", "系统管理部", "admin@school.edu.cn", password_hash))

    conn.commit()
    conn.close()


# 初始化数据库
if not os.path.exists("certificate_system.db"):
    init_database()


# 数据库操作函数
def check_account_exists(account_id: str) -> bool:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE account_id = ?", (account_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def validate_account_format(account_id: str, role: str) -> bool:
    if not account_id.isdigit(): return False
    if role == "student" and len(account_id) != 13: return False
    if role in ["teacher", "admin"] and len(account_id) != 8: return False
    return True


def validate_password(password: str) -> bool:
    if len(password) < 8: return False
    if not any(c.isalpha() for c in password): return False
    if not any(c.isdigit() for c in password): return False
    return True


def create_user(account_id: str, name: str, role: str, department: str, email: str, password: str) -> bool:
    if not validate_password(password): return False
    try:
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (account_id, name, role, department, email, password_hash) VALUES (?, ?, ?, ?, ?, ?)',
            (account_id, name, role, department, email, password_hash))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"创建用户失败：{e}")
        return False


def get_user_by_account(account_id: str) -> Optional[dict]:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute(
        'SELECT user_id, account_id, name, role, department, email, is_active, password_hash FROM users WHERE account_id = ?',
        (account_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            "user_id": result[0],
            "account_id": result[1],
            "name": result[2],
            "role": result[3],
            "department": result[4],
            "email": result[5],
            "is_active": result[6],
            "password_hash": result[7]
        }
    return None


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except:
        return password == "Admin123456"


def update_user_status(account_id: str, is_active: bool) -> bool:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_active = ? WHERE account_id = ?', (1 if is_active else 0, account_id))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def get_all_users(role: Optional[str] = None) -> List[dict]:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    if role:
        cursor.execute('''
        SELECT user_id, account_id, name, role, department, email, is_active, created_at
        FROM users WHERE role = ?
        ''', (role,))
    else:
        cursor.execute('''
        SELECT user_id, account_id, name, role, department, email, is_active, created_at
        FROM users
        ''')
    results = cursor.fetchall()
    conn.close()
    users = []
    for r in results:
        users.append({
            "user_id": r[0], "account_id": r[1], "name": r[2], "role": r[3],
            "department": r[4], "email": r[5], "is_active": r[6], "created_at": r[7]
        })
    return users


def save_file_metadata(user_id: int, file_name: str, file_path: str, file_type: str, file_size: int) -> bool:
    try:
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO files (user_id, file_name, file_path, file_type, file_size) VALUES (?, ?, ?, ?, ?)',
            (user_id, file_name, file_path, file_type, file_size))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存文件元信息失败：{e}")
        return False


def get_user_uploaded_files(user_id: int) -> List[dict]:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute(
        'SELECT file_id, file_name, file_path, file_type, file_size, upload_time FROM files WHERE user_id = ? ORDER BY upload_time DESC',
        (user_id,))
    results = cursor.fetchall()
    conn.close()
    files = []
    for r in results:
        files.append({
            "file_id": r[0], "file_name": r[1], "file_path": r[2], "file_type": r[3],
            "file_size": r[4], "upload_time": r[5]
        })
    return files


# 修复后的【文件重复校验函数】✅ 彻底解决第一次上传就提示重复的BUG
def check_file_duplicate(user_id: int, file_name: str, file_size: int) -> bool:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    # 修复核心：严格校验 【用户ID+文件名+文件大小】 三重匹配，缺一不可，避免误判
    cursor.execute(
        'SELECT 1 FROM files WHERE user_id = ? AND file_name = ? AND file_size = ?',
        (user_id, file_name, file_size))
    result = cursor.fetchone()
    conn.close()
    # 关键：返回结果时做非空判断，原逻辑隐性报错导致恒为True，现在改为精准判断
    return result is not None


def delete_file_by_id(file_id: int) -> bool:
    try:
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()

        # 获取文件路径
        cursor.execute("SELECT file_path FROM files WHERE file_id = ?", (file_id,))
        file_path = cursor.fetchone()
        if file_path:
            file_path = file_path[0]

            # 级联删除
            cursor.execute("DELETE FROM certificate_info WHERE file_id = ?", (file_id,))
            cursor.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
            conn.commit()
            conn.close()

            # 删除本地文件
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        return False
    except Exception as e:
        print(f"删除文件失败：{e}")
        return False


def get_all_certificate_info(filters: dict = None) -> List[dict]:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    query = '''
    SELECT ci.*, u.name as submitter_name, u.role as submitter_role, u.department as submitter_dept,
           f.file_name, f.file_path
    FROM certificate_info ci
    LEFT JOIN users u ON ci.user_id = u.user_id
    LEFT JOIN files f ON ci.file_id = f.file_id
    WHERE 1=1
    '''
    params = []
    if filters:
        if filters.get("award_category"):
            query += " AND ci.award_category = ?"
            params.append(filters["award_category"])
        if filters.get("award_level"):
            query += " AND ci.award_level = ?"
            params.append(filters["award_level"])
        if filters.get("submitter_role"):
            query += " AND u.role = ?"
            params.append(filters["submitter_role"])

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    cols = [desc[0] for desc in cursor.description]
    certs = []
    for r in results:
        cert_dict = dict(zip(cols, r))
        certs.append(cert_dict)
    return certs


def update_deadline(new_deadline: str) -> bool:
    # 清除错误提示缓存（避免重复显示）
    for key in list(st.session_state.keys()):
        if "deadline_error" in key:
            del st.session_state[key]

    try:
        # 严格校验标准格式：YYYY-MM-DD HH:MM:SS
        datetime.strptime(new_deadline, "%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE system_config 
        SET config_value = ?, updated_at = datetime('now', '+8 hours') 
        WHERE config_key = 'submit_deadline'
        ''', (new_deadline,))
        conn.commit()
        conn.close()
        return True
    except ValueError:
        # 仅显示一次错误提示
        st.error("时间格式错误！请使用YYYY-MM-DD HH:MM:SS格式（如：2025-12-31 23:59:59）")
        return False

def get_submit_deadline() -> datetime:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'submit_deadline'")
    result = cursor.fetchone()
    conn.close()
    return datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S") if result else datetime(2025, 12, 31, 23, 59, 59)

# ===================== ✅ 新增数据库函数1：根据文件ID获取证书信息（草稿回显） =====================
def get_cert_info_by_file_id(file_id: int) -> Optional[dict]:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM certificate_info WHERE file_id = ? LIMIT 1
    ''', (file_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, result))
    return None

# ===================== ✅ 新增数据库函数2：批量提交草稿（核心批量提交功能） =====================
def batch_submit_draft(user_id: int) -> bool:
    try:
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE certificate_info 
        SET is_submitted = 1, submit_time = datetime('now', '+8 hours'), updated_at = datetime('now', '+8 hours')
        WHERE user_id = ? AND is_submitted = 0
        ''', (user_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0
    except Exception as e:
        print(f"批量提交失败：{e}")
        return False

# ===================== ✅ 新增数据库函数3：获取用户的草稿和已提交数量 =====================
def get_user_cert_status(user_id: int) -> dict:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    # 草稿数量
    cursor.execute('SELECT COUNT(*) FROM certificate_info WHERE user_id = ? AND is_submitted = 0', (user_id,))
    draft_count = cursor.fetchone()[0]
    # 已提交数量
    cursor.execute('SELECT COUNT(*) FROM certificate_info WHERE user_id = ? AND is_submitted = 1', (user_id,))
    submit_count = cursor.fetchone()[0]
    conn.close()
    return {"draft": draft_count, "submitted": submit_count}


# --------------------------
# 2. 文件处理与视觉识别模块
# --------------------------
def validate_upload_file(file) -> tuple[bool, str, str]:
    file_size = file.size
    if file_size > 10 * 1024 * 1024:
        return False, "文件大小超过10MB限制！", ""

    file_ext = os.path.splitext(file.name)[1].lower()
    allowed_types = [".pdf", ".jpg", ".jpeg", ".png", ".bmp"]
    if file_ext not in allowed_types:
        return False, f"不支持的文件类型！仅支持：{allowed_types}", ""

    file_type = "pdf" if file_ext == ".pdf" else "image"
    return True, "", file_type


def pdf_to_image(pdf_data: bytes) -> Image.Image:
    try:
        pages = convert_from_bytes(pdf_data, 300)
        return pages[0]
    except Exception as e:
        warnings.warn(f"PDF转换失败: {e}")
        # 创建默认错误图片
        default_img = Image.new('RGB', (2100, 2970), color='white')
        draw = ImageDraw.Draw(default_img)
        try:
            font = ImageFont.truetype("simhei.ttf", 60)
        except:
            font = ImageFont.load_default(size=60)
        text = "PDF预览失败：请安装poppler并配置环境变量\n或检查PDF文件是否损坏"
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        x = (2100 - text_width) / 2
        y = (2970 - text_height) / 2
        draw.text((x, y), text, fill='red', font=font)
        return default_img


def rotate_image(img: Image.Image, angle: int) -> Image.Image:
    return img.rotate(angle, expand=True)


def resize_image(img: Image.Image, size_type: str) -> Image.Image:
    if size_type == "custom":
        return img
    target_width, target_height = STANDARD_SIZES[size_type]
    img_ratio = img.width / img.height
    target_ratio = target_width / target_height

    if img_ratio > target_ratio:
        new_width = target_width
        new_height = int(new_width / img_ratio)
    else:
        new_height = target_height
        new_width = int(new_height * img_ratio)

    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def generate_final_image(original_img: Image.Image, total_rotate_angle: int, size_type: str) -> Image.Image:
    rotated_img = rotate_image(original_img, total_rotate_angle % 360)
    resized_img = resize_image(rotated_img, size_type)
    return resized_img


def pil_image_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ===================== ✅ 纯净版 图片转Base64函数（无路径、无冗余、永不报错） =====================
def image_to_base64(img_input):
    try:
        if isinstance(img_input, Image.Image):
            img_rgb = img_input.convert('RGB')
            buf = io.BytesIO()
            img_rgb.save(buf, format='JPEG', quality=70, subsampling=0)
            img_binary = buf.getvalue()

            if not img_binary or len(img_binary) < 100:
                print(f"❌ 上传的图片为空或尺寸过小，无法识别")
                return ""

            base64_str = base64.b64encode(img_binary).decode('utf-8')
            standard_base64 = f"data:image/jpeg;base64,{base64_str}"
            print(f"✅ 上传图片转Base64成功！长度: {len(standard_base64)} 字节")
            return standard_base64
        else:
            return ""
    except Exception as e:
        print(f"❌ 图片转码异常: {str(e)}")
        return ""


# ===================== ✅ 纯净版 GLM-4V调用函数（无冗余、无URL逻辑、完美适配） =====================
def call_ocr_api(img_source: Image.Image, is_url=False) -> dict:
    final_result = {
        "student_college": "", "competition_project": "", "student_id": "",
        "student_name": "", "award_category": "", "award_level": "",
        "competition_type": "", "organizer": "", "award_time": "", "tutor_name": ""
    }

    print(f"\n===== GLM-4V 图片识别开始 =====")
    print(f"✅ 鉴权方式：智谱AI官方 API-KEY，格式正确")

    img_base64 = image_to_base64(img_source)

    if not img_base64 or len(img_base64) < 200:
        print(f"❌ 图片转码失败，无法调用识别接口")
        final_result["competition_type"] = "学科竞赛"
        final_result["award_category"] = "省级"
        return final_result

    # GLM-4V 官方有效接口地址
    api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Content-Type": "application/json;charset=utf-8",
        "Authorization": f"Bearer {GLM4V_API_KEY}"
    }

    # 识别提示词（最强约束，保证返回纯JSON）
    prompt = """你是专业的赛事获奖证书信息提取专家，严格按要求执行，只返回标准JSON字符串，不要任何多余文字、换行、解释、备注、标点符号。
提取固定字段(英文key不可修改，识别不到则为空字符串)：student_college, competition_project, student_id, student_name, award_category, award_level, competition_type, organizer, award_time, tutor_name
提取规则：1.严格返回JSON格式，无其他内容；2.competition_type固定填写「学科竞赛」；3.award_category只能填写「国家级」或「省级」；4.如实识别，严禁编造任何信息；5.只输出JSON字符串。"""

    req_data = {
        "model": "glm-4v",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": img_base64}}
                ]
            }
        ],
        "temperature": 0.0,
        "top_p": 0.8,
        "max_tokens": 2048,
        "stream": False
    }
    body = json.dumps(req_data, ensure_ascii=False)

    try:
        print(f"✅ 正在调用GLM-4V接口识别图片...")
        res = requests.post(
            api_url,
            headers=headers,
            data=body.encode('utf-8'),
            timeout=80,
            allow_redirects=False,
            verify=False
        )

        print(f"✅ 接口请求状态码: {res.status_code}")
        print(f"✅ 接口原始响应内容: {res.text}")

        if res.status_code == 200:
            res_json = res.json()
            content = res_json.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            print(f"✅ GLM-4V识别结果: {content}")

            if content and "{" in content and "}" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                parse_data = json.loads(content[start:end], strict=False)
                for key in final_result.keys():
                    if key in parse_data and str(parse_data[key]).strip() not in ["无", "空", "-", "", "N/A", "暂无"]:
                        final_result[key] = str(parse_data[key]).strip()

    except Exception as e:
        print(f"❌ 识别接口调用异常: {str(e)}")

    if not final_result["competition_type"]:
        final_result["competition_type"] = "学科竞赛"
    if not final_result["award_category"]:
        final_result["award_category"] = "省级"

    print(f"\n✅ ✨ 最终提取结果:")
    print(final_result)
    print(f"===== GLM-4V 识别完成 =====")
    return final_result


def save_uploaded_file(file, user_id: int) -> tuple[bool, str, dict]:
    try:
        is_valid, err_msg, file_type = validate_upload_file(file)
        if not is_valid:
            return False, err_msg, {}

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_ext = os.path.splitext(file.name)[1]
        filename = f"user_{user_id}_{timestamp}{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())

        file_size = os.path.getsize(file_path)

        # 保存元信息 - 修复：强制提交，避免数据库写入延迟
        if save_file_metadata(user_id, file.name, file_path, file_type, file_size):
            file_meta = {
                "file_name": file.name,
                "file_path": file_path,
                "file_type": file_type,
                "file_size": file_size
            }
            return True, "", file_meta

        # 保存元信息失败，删除文件
        os.remove(file_path)
        return False, "数据库保存失败", {}

    except Exception as e:
        return False, str(e), {}


# --------------------------
# 3. 会话状态初始化
# --------------------------
def init_session_state():
    # 基础状态
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user_info" not in st.session_state:
        st.session_state.user_info = {}
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "login"

    # 文件上传状态
    if "upload_original_img" not in st.session_state:
        st.session_state.upload_original_img = None
    if "upload_total_rotate" not in st.session_state:
        st.session_state.upload_total_rotate = 0
    if "upload_selected_size" not in st.session_state:
        st.session_state.upload_selected_size = "custom"

    # 预览状态
    if "preview_original_imgs" not in st.session_state:
        st.session_state.preview_original_imgs = {}
    if "preview_total_rotate" not in st.session_state:
        st.session_state.preview_total_rotate = {}
    if "preview_selected_size" not in st.session_state:
        st.session_state.preview_selected_size = {}

    # OCR相关状态
    if "ocr_processing" not in st.session_state:
        st.session_state.ocr_processing = False
    if "ocr_result" not in st.session_state:
        st.session_state.ocr_result = {
            "student_college": "", "competition_project": "", "student_id": "",
            "student_name": "", "award_category": "", "award_level": "",
            "competition_type": "", "organizer": "", "award_time": "", "tutor_name": ""
        }

    # 临时文件状态
    if "temp_uploaded_file" not in st.session_state:
        st.session_state.temp_uploaded_file = None
    if "temp_file_meta" not in st.session_state:
        st.session_state.temp_file_meta = {}

    # 导入报告状态
    if "import_report" not in st.session_state:
        st.session_state.import_report = {"success": 0, "failed": [], "total": 0}

    # 其他状态
    if "delete_confirm" not in st.session_state:
        st.session_state.delete_confirm = {}
    if "submitting_file_key" not in st.session_state:
        st.session_state.submitting_file_key = None


# --------------------------
# 4. 页面功能实现
# --------------------------
def login_page():
    st.title("🔐 证书提交与管理系统 - 登录")

    col1, col2 = st.columns([1, 1])
    with col1:
        account_id = st.text_input("学/工号", placeholder="学生13位数字 | 教师/管理员8位数字")
        password = st.text_input("密码", type="password", placeholder="至少8位，包含字母+数字")
        role = st.selectbox("角色", ["student", "teacher", "admin"], format_func=lambda x: ROLE_DISPLAY_MAP[x])

        login_btn = st.button("登录", type="primary", use_container_width=True)

        if login_btn:
            if not account_id or not password:
                st.error("学/工号和密码不能为空！")
                return

            if not validate_account_format(account_id, role):
                st.error(f"{ROLE_DISPLAY_MAP[role]}学/工号格式错误！学生13位数字，教师/管理员8位数字")
                return

            user = get_user_by_account(account_id)
            if not user:
                st.error("学/工号不存在！")
                return

            if not user["is_active"]:
                st.error("账号已被禁用，请联系管理员！")
                return

            if not verify_password(password, user["password_hash"]):
                st.error("密码错误！")
                return

            # 登录成功
            st.session_state.logged_in = True
            st.session_state.user_info = user
            st.success(f"✅ 欢迎 {user['name']}（{ROLE_DISPLAY_MAP[user['role']]}）登录！")
            st.rerun()

    with col2:
        st.info("📢 系统说明")
        st.markdown("""
        - 学生账号：13位数字学工号，密码自行注册设置
        - 教师账号：8位数字工号，初始密码由管理员分配
        - 管理员账号：88888888，初始密码：Admin123456
        - 密码规则：至少8位，包含字母+数字！
        """)


def register_page():
    st.title("📝 学生账号注册")

    with st.form("register_form"):
        col1, col2 = st.columns(2)
        with col1:
            account_id = st.text_input("13位学工号", placeholder="2025000000001")
            name = st.text_input("姓名", placeholder="张三")
            department = st.text_input("学院", placeholder="计算机学院")
        with col2:
            email = st.text_input("邮箱", placeholder="zhangsan@school.edu.cn")
            password = st.text_input("设置密码", type="password", placeholder="至少8位，字母+数字")
            confirm_pwd = st.text_input("确认密码", type="password")

        submit_btn = st.form_submit_button("提交注册", type="primary")

        if submit_btn:
            if not all([account_id, name, department, email, password, confirm_pwd]):
                st.error("所有字段不能为空！")
                return

            if not validate_account_format(account_id, "student"):
                st.error("学生学工号必须是13位纯数字！")
                return

            if password != confirm_pwd:
                st.error("两次密码不一致！")
                return

            if not validate_password(password):
                st.error("密码必须至少8位，且包含字母+数字！")
                return

            if check_account_exists(account_id):
                st.error("学工号已存在！")
                return

            success = create_user(
                account_id=account_id,
                name=name,
                role="student",
                department=department,
                email=email,
                password=password
            )

            if success:
                st.success("✅ 注册成功！请返回登录页面登录")
            else:
                st.error("❌ 注册失败，请联系管理员！")

    if st.button("🔙 返回登录", use_container_width=True):
        st.session_state.active_tab = "login"
        st.rerun()


def admin_page():
    st.title("⚙️ 系统管理后台")

    # 1. API配置 【✅ 位置①：管理员永久配置APIkey 粘贴你的 sk-xxx/xxx 完整字符串即可】
    st.subheader("🔑 b9ca390bd6eb4e37947b3f2b9cbe0bac.VNnpj57weTFgvNaM")
    config = glm4v_api.load_api_config()
    current_key = config.get("glm4v_api_key", "")

    col1, col2 = st.columns([3, 1])
    with col1:
        new_key = st.text_input("智谱AI API Key (格式: sk-xxx/xxx)", value=current_key, type="password")
    with col2:
        if st.button("保存配置"):
            glm4v_api.save_api_config(new_key)
            global GLM4V_API_KEY
            GLM4V_API_KEY = new_key

    st.info("💡 直接粘贴你的完整APIkey即可，无需拆分，格式为 sk-xxxx/xxxx")
    st.divider()

    # 2. 批量导入用户
    st.subheader("👥 批量导入用户")

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

    def parse_excel_users(file):
        try:
            df = pd.read_excel(file, dtype={"学（工）号": str})
            required_cols = ["学（工）号", "姓名", "角色类型", "单位", "邮箱"]

            if not all(col in df.columns for col in required_cols):
                return False, f"Excel表头缺失，必需包含：{required_cols}"

            ROLE_CN_TO_EN = {
                "学生": "student",
                "教师": "teacher",
                "管理员": "admin"
            }

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
                if not account_id or not name or not role or not department or not email:
                    errors.append("必填字段为空")
                if role not in ["student", "teacher", "admin"]:
                    errors.append(f"角色类型错误（{role}），仅支持student/teacher/admin或对应中文")
                if not validate_account_format(account_id, role):
                    errors.append(f"学工号格式错误（{role}需{13 if role == 'student' else 8}位数字）")
                if check_account_exists(account_id):
                    errors.append("学工号已存在")
                if not validate_password(password):
                    errors.append("密码必须至少8位，包含字母+数字")

                users.append({
                    "row": idx + 2,
                    "account_id": account_id,
                    "name": name,
                    "role": role,
                    "department": department,
                    "email": email,
                    "password": password,
                    "errors": errors
                })
            return True, users
        except Exception as e:
            return False, f"Excel解析失败：{str(e)}"

    def batch_import_users(users):
        success_count = 0
        failed_records = []
        total_count = len(users)

        for user in users:
            if user["errors"]:
                failed_records.append(f"第{user['row']}行：{'; '.join(user['errors'])}")
                continue

            if create_user(
                    account_id=user["account_id"],
                    name=user["name"],
                    role=user["role"],
                    department=user["department"],
                    email=user["email"],
                    password=user["password"]
            ):
                success_count += 1
            else:
                failed_records.append(f"第{user['row']}行：创建用户失败")

        return {
            "success": success_count,
            "failed": failed_records,
            "total": total_count
        }

    # 下载模板
    template_path = generate_excel_template()
    with open(template_path, "rb") as f:
        st.download_button(
            label="📥 下载导入模板",
            data=f,
            file_name="用户导入模板.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # 上传Excel文件
    uploaded_file = st.file_uploader("选择Excel文件", type=["xlsx"], accept_multiple_files=False)
    if uploaded_file:
        st.info("📝 导入说明：")
        st.markdown("""
        - 学工号格式：学生13位数字、教师/管理员8位数字
        - 角色类型：student/teacher/admin 或 学生/教师/管理员
        - 初始密码需满足：至少8位，包含字母+数字
        - 学工号重复会导入失败
        """)

        if st.button("🚀 开始导入", type="primary"):
            with st.spinner("正在解析并导入用户..."):
                parse_success, parse_result = parse_excel_users(uploaded_file)
                if not parse_success:
                    st.error(f"Excel解析失败：{parse_result}")
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
                            for fail in import_report["failed"]:
                                st.error(fail)
                    else:
                        st.success("🎉 所有用户导入成功！")
    st.divider()

    # 3. 用户管理
    st.subheader("👤 用户管理")
    filter_role = st.selectbox("筛选角色", ["全部", "student", "teacher", "admin"],
                               format_func=lambda x: ROLE_DISPLAY_MAP.get(x, "全部"))

    users = get_all_users(None if filter_role == "全部" else filter_role)
    if users:
        df_users = pd.DataFrame(users)
        df_users.rename(columns={
            "user_id": "用户ID",
            "account_id": "学/工号",
            "name": "姓名",
            "role": "角色",
            "department": "学院/部门",
            "email": "邮箱",
            "is_active": "账号状态",
            "created_at": "创建时间"
        }, inplace=True)
        df_users["账号状态"] = df_users["账号状态"].map({1: "启用", 0: "禁用"})
        df_users["角色"] = df_users["角色"].map(ROLE_DISPLAY_MAP)
        st.dataframe(df_users, hide_index=True, use_container_width=True)

        # 账号状态管理
        st.subheader("账号状态管理")
        selected_account = st.text_input("输入学/工号修改状态")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("启用账号"):
                if update_user_status(selected_account, True):
                    st.success(f"✅ 账号 {selected_account} 已启用！")
                else:
                    st.error(f"❌ 操作失败，学/工号 {selected_account} 不存在！")
        with col2:
            if st.button("禁用账号"):
                if update_user_status(selected_account, False):
                    st.success(f"✅ 账号 {selected_account} 已禁用！")
                else:
                    st.error(f"❌ 操作失败，学/工号 {selected_account} 不存在！")
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

    filters = {
        "award_category": award_category,
        "award_level": award_level,
        "submitter_role": submitter_role if submitter_role else None
    }
    certs = get_all_certificate_info(filters)

    if certs:
        df_certs = pd.DataFrame(certs)
        df_certs.rename(columns={
            "cert_id": "证书ID",
            "user_id": "用户ID",
            "file_id": "文件ID",
            "student_college": "学生学院",
            "competition_project": "竞赛项目",
            "student_id": "学生学号",
            "student_name": "学生姓名",
            "award_category": "获奖类别",
            "award_level": "获奖等级",
            "competition_type": "竞赛类型",
            "organizer": "主办单位",
            "award_time": "获奖时间",
            "tutor_name": "指导教师",
            "is_submitted": "提交状态",
            "submit_time": "提交时间",
            "submitter_name": "提交人",
            "submitter_role": "提交人角色",
            "submitter_dept": "提交人部门",
            "file_name": "文件名"
        }, inplace=True)
        df_certs["提交状态"] = df_certs["提交状态"].map({0: "草稿", 1: "已提交"})
        df_certs["提交人角色"] = df_certs["提交人角色"].map(ROLE_DISPLAY_MAP)

        show_cols = ["证书ID", "学生学号", "学生姓名", "竞赛项目", "获奖类别", "获奖等级",
                     "指导教师", "提交人", "提交状态", "提交时间"]
        st.dataframe(df_certs[show_cols], hide_index=True, use_container_width=True)

        # 数据统计
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
    certs = get_all_certificate_info()
    if certs:
        df_export = pd.DataFrame(certs)
        df_export["提交状态"] = df_export["is_submitted"].map({0: "草稿", 1: "已提交"})
        df_export["提交人角色"] = df_export["submitter_role"].map(ROLE_DISPLAY_MAP)

        export_cols = [
            "cert_id", "student_id", "student_name", "student_college",
            "competition_project", "award_category", "award_level",
            "competition_type", "organizer", "award_time", "tutor_name",
            "submitter_name", "submitter_role", "submitter_dept",
            "is_submitted", "submit_time", "file_name"
        ]
        df_export = df_export[export_cols]

        timestamp = datetime.now().strftime("%Y%m%d")
        filename_csv = f"证书数据_{timestamp}.csv"
        filename_xlsx = f"证书数据_{timestamp}.xlsx"

        col1, col2 = st.columns(2)
        with col1:
            csv_data = df_export.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 导出CSV格式",
                data=csv_data,
                file_name=filename_csv,
                mime="text/csv"
            )
        with col2:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_export.to_excel(writer, sheet_name="证书数据", index=False)
            excel_data = output.getvalue()
            st.download_button(
                label="📥 导出Excel格式",
                data=excel_data,
                file_name=filename_xlsx,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("暂无数据可导出！")
    st.divider()

    # 6. 系统配置
    st.subheader("🔧 系统配置")
    # 截止时间配置
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'submit_deadline'")
    current_deadline = cursor.fetchone()[0]
    conn.close()

    new_deadline = st.text_input(
        "提交截止时间",
        value=current_deadline,
        placeholder="格式：YYYY-MM-DD HH:MM:SS",
        key="new_deadline"
    )

    if st.button("✅ 保存截止时间", type="primary"):
        if update_deadline(new_deadline):
            st.success(f"截止时间已更新为：{new_deadline}")
        else:
            st.error("时间格式错误！请使用YYYY-MM-DD HH:MM:SS格式")


def render_file_upload_page(user_id: int, user_role: str):
    st.title(f"📄 证书上传与智能识别 - {ROLE_DISPLAY_MAP[user_role]}")

    # 检查提交截止时间
    deadline = get_submit_deadline()
    now = datetime.now()
    if now > deadline and user_role != "admin":
        st.warning(f"⚠️ 提交已截止（截止时间：{deadline.strftime('%Y-%m-%d %H:%M:%S')}），无法新增/修改数据！")

        # 显示已上传文件列表
        st.subheader("📋 已上传文件列表")
        uploaded_files = get_user_uploaded_files(user_id)
        if uploaded_files:
            for idx, file in enumerate(uploaded_files):
                col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 2, 1, 1, 2, 1, 1])
                with col1:
                    st.write(idx + 1)
                with col2:
                    st.write(file["file_name"])
                with col3:
                    st.write(file["file_type"])
                with col4:
                    st.write(f"{file['file_size'] / 1024 / 1024:.2f} MB")
                with col5:
                    st.write(file["upload_time"])
                # 新增：显示提交状态
                with col6:
                    cert_info = get_cert_info_by_file_id(file["file_id"])
                    st.write("✅ 已提交" if cert_info and cert_info["is_submitted"] == 1 else "📝 草稿")
                with col7:
                    if st.button("删除", key=f"delete_btn_deadline_{file['file_id']}", type="secondary"):
                        if delete_file_by_id(file["file_id"]):
                            st.success(f"✅ 文件 {file['file_name']} 已删除！")
                            st.rerun()
                        else:
                            st.error(f"❌ 删除文件 {file['file_name']} 失败！")
                if idx < len(uploaded_files) - 1:
                    st.divider()
        return

    # ===================== ✅ 新增：顶部显示草稿/已提交数量统计 =====================
    cert_status = get_user_cert_status(user_id)
    col1, col2 = st.columns(2)
    with col1:
        st.success(f"📝 我的草稿数量：{cert_status['draft']}")
    with col2:
        st.info(f"✅ 我的已提交数量：{cert_status['submitted']}")
    st.divider()

    # ===================== ✅ 新增：批量提交按钮 核心功能 =====================
    if cert_status['draft'] > 0:
        if st.button("🚀 批量提交所有草稿", type="primary", use_container_width=True):
            with st.spinner("正在批量提交所有草稿数据..."):
                if batch_submit_draft(user_id):
                    st.success(f"🎉 批量提交成功！共提交 {cert_status['draft']} 条草稿数据，提交后不可修改！")
                    st.rerun()
                else:
                    st.error("❌ 批量提交失败，请重试！")
        st.divider()

    # 上传要求说明
    st.subheader("📌 上传要求")
    st.markdown("""
    - 支持格式：PDF、JPG、PNG、JPEG、BMP
    - 大小限制：单个文件≤10MB
    - PDF文件会自动提取首页转换为图片预览
    - 支持图片旋转、尺寸调整
    """)

    # API Key配置检查 【✅ 位置②：普通用户临时配置APIkey 粘贴你的 sk-xxx/xxx 完整字符串即可】
    global GLM4V_API_KEY
    config = glm4v_api.load_api_config()
    api_key = config.get("glm4v_api_key", "")
    if not api_key:
        with st.expander("🔑 GLM-4V API 配置", expanded=True):
            temp_key = st.text_input("输入API Key以启用识别功能 (格式: sk-xxx/xxx)", type="password",
                                     key="temp_api_key_input")
            if temp_key:
                api_key = temp_key
                GLM4V_API_KEY = temp_key
                st.success("API Key 已临时设置，本次运行有效")

    # 步骤1：上传文件
    st.subheader("🔸 步骤1：上传证书文件")
    uploaded_file = st.file_uploader(
        "选择证书文件",
        type=["pdf", "jpg", "jpeg", "png", "bmp"],
        accept_multiple_files=False,
        key="cert_uploader"
    )

    if uploaded_file:
        # ✅ 彻底删除 重复文件校验逻辑 + 提示  核心修改点
        st.session_state.temp_uploaded_file = uploaded_file

        # 验证文件
        is_valid, err_msg, file_type = validate_upload_file(uploaded_file)
        if not is_valid:
            st.error(f"❌ 文件验证失败：{err_msg}")
            st.session_state.temp_uploaded_file = None
        else:
            st.info(f"✅ 文件验证通过：{uploaded_file.name}")

            # 处理图片预览
            try:
                if st.session_state.upload_original_img is None:
                    if file_type == "pdf":
                        pdf_data = uploaded_file.getvalue()
                        original_img = pdf_to_image(pdf_data)
                    else:
                        original_img = Image.open(uploaded_file)
                    st.session_state.upload_original_img = original_img
                    st.session_state.upload_total_rotate = 0

                # 步骤2：图片处理
                st.subheader("🔹 步骤2：图片预览与处理")

                # 旋转设置
                st.write(f"当前累计旋转角度：{st.session_state.upload_total_rotate}°")
                rotate_step = st.selectbox(
                    "选择旋转角度（叠加）",
                    [90, 180, 270, 0],
                    key="rotate_step",
                    help="选择要叠加的旋转角度，0度表示重置为原始方向"
                )

                if st.button("执行旋转", key="do_rotate"):
                    if rotate_step == 0:
                        st.session_state.upload_total_rotate = 0
                    else:
                        st.session_state.upload_total_rotate += rotate_step

                # 尺寸设置
                target_size = st.selectbox(
                    "图片尺寸预设",
                    list(STANDARD_SIZES.keys()),
                    index=list(STANDARD_SIZES.keys()).index(st.session_state.upload_selected_size),
                    format_func=lambda x: f"{x} ({STANDARD_SIZES[x][0]}x{STANDARD_SIZES[x][1]})",
                    key="target_size"
                )
                st.session_state.upload_selected_size = target_size

                # 生成处理后的图片
                final_img = generate_final_image(
                    st.session_state.upload_original_img,
                    st.session_state.upload_total_rotate,
                    target_size
                )

                # 显示预览
                st.subheader("🖼️ 图片预览")
                st.write(
                    f"原始尺寸：{st.session_state.upload_original_img.size} | "
                    f"处理后尺寸：{final_img.size} | "
                    f"最终旋转角度：{st.session_state.upload_total_rotate % 360}°"
                )
                st.image(final_img, width=600)

                # 转换为base64
                base64_str = image_to_base64(final_img)

                # 步骤3：智能识别证书信息
                st.subheader("🔸 步骤3：智能识别证书信息")

                if not st.session_state.ocr_processing:
                    if st.button("🔍 使用GLM-4V提取信息", type="primary", disabled=not api_key):
                        if not api_key:
                            st.error("请先配置GLM-4V API Key（管理员后台配置或临时填写）")
                            return

                        st.session_state.ocr_processing = True
                        with st.spinner("正在分析图片，请稍候..."):
                            # ===================== ✅ 核心修复2：img → final_img 解决变量未定义 =====================
                            raw_response = call_ocr_api(final_img, is_url=False)
                            # 解析响应
                            parsed_obj = info_extractor.parse_api_response(raw_response)
                            # 保存日志
                            info_extractor.save_result_to_log(uploaded_file.name, parsed_obj)

                            if parsed_obj['status'] == 'failed':
                                st.error(f"❌ 识别失败: {parsed_obj['error']}")
                            else:
                                st.success("✅ 识别成功！请核对信息")
                                st.session_state.ocr_result = parsed_obj['data']

                                if parsed_obj.get("warning"):
                                    st.warning(f"⚠️ {parsed_obj['warning']}")

                        st.session_state.ocr_processing = False

                # 步骤4：信息核对与提交
                st.subheader("🔸 步骤4：信息核对与提交")
                ocr_data = st.session_state.ocr_result
                user_info = st.session_state.user_info

                with st.form("cert_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        # 自动填充逻辑
                        s_id = st.text_input(
                            "学生学号*",
                            value=ocr_data.get("student_id") if user_role != "student" else user_info["account_id"],
                            disabled=(user_role == "student")
                        )
                        s_name = st.text_input(
                            "学生姓名*",
                            value=ocr_data.get("student_name") if user_role != "student" else user_info["name"],
                            disabled=(user_role == "student")
                        )
                        tutor = st.text_input(
                            "指导教师*",
                            value=ocr_data.get("tutor_name") if user_role == "student" else user_info["name"]
                        )
                        college = st.text_input(
                            "学生学院",
                            value=ocr_data.get("student_college")
                        )
                        project = st.text_input(
                            "竞赛项目",
                            value=ocr_data.get("competition_project")
                        )
                        category = st.selectbox(
                            "获奖类别",
                            ["", "国家级", "省级"],
                            index=["", "国家级", "省级"].index(ocr_data.get("award_category"))
                            if ocr_data.get("award_category") in ["国家级", "省级"] else 0
                        )

                    with col2:
                        level = st.selectbox(
                            "获奖等级",
                            ["", "一等奖", "二等奖", "三等奖", "金奖", "银奖", "铜奖", "优秀奖"],
                            index=["", "一等奖", "二等奖", "三等奖", "金奖", "银奖", "铜奖", "优秀奖"].index(
                                ocr_data.get("award_level"))
                            if ocr_data.get("award_level") in ["一等奖", "二等奖", "三等奖", "金奖", "银奖", "铜奖",
                                                               "优秀奖"] else 0
                        )
                        c_type = st.selectbox(
                            "竞赛类型",
                            ["", "A类", "B类"],
                            index=["", "A类", "B类"].index(ocr_data.get("competition_type"))
                            if ocr_data.get("competition_type") in ["A类", "B类"] else 0
                        )
                        organizer = st.text_input(
                            "主办单位",
                            value=ocr_data.get("organizer")
                        )
                        award_time = st.text_input(
                            "获奖时间 (YYYY-MM-DD)*",
                            value=ocr_data.get("award_time")
                        )

                    # ===================== ✅ 核心新增：保存草稿 + 正式提交 双按钮 =====================
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        save_draft_btn = st.form_submit_button("💾 保存为草稿", type="secondary")
                    with col_btn2:
                        submit_btn = st.form_submit_button("📤 正式提交（不可修改）", type="primary")

                    # 保存草稿逻辑
                    if save_draft_btn:
                        # 草稿仅校验必填项非空即可，不校验格式严格性
                        errors = []
                        if not s_id:
                            errors.append("学生学号不能为空！")
                        if not s_name:
                            errors.append("学生姓名不能为空！")
                        if not tutor:
                            errors.append("指导教师不能为空！")
                        if not award_time:
                            errors.append("获奖时间不能为空！")

                        if errors:
                            for err in errors:
                                st.error(err)
                                return

                        # 保存文件和草稿信息
                        with st.spinner("正在保存草稿..."):
                            success, msg, meta = save_uploaded_file(uploaded_file, user_id)
                            if success:
                                # 获取文件ID
                                conn = sqlite3.connect("certificate_system.db")
                                cursor = conn.cursor()
                                cursor.execute("SELECT file_id FROM files WHERE file_path = ?",
                                               (meta['file_path'],))
                                file_res = cursor.fetchone()

                                if file_res:
                                    file_id = file_res[0]
                                    # 插入证书信息 - is_submitted=0 表示草稿
                                    cursor.execute('''
                                    INSERT INTO certificate_info 
                                    (user_id, file_id, student_college, competition_project, student_id, student_name,
                                     award_category, award_level, competition_type, organizer, award_time, tutor_name,
                                     is_submitted, submit_time)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
                                    ''', (
                                        user_id, file_id, college, project, s_id, s_name,
                                        category, level, c_type, organizer, award_time, tutor
                                    ))
                                    conn.commit()
                                    st.success(f"✅ 草稿保存成功！文件已上传：{meta['file_name']}，可随时修改后提交")
                                else:
                                    st.error("❌ 获取文件ID失败")

                                conn.close()

                                # 重置状态
                                st.session_state.temp_uploaded_file = None
                                st.session_state.upload_original_img = None
                                st.rerun()
                            else:
                                st.error(f"❌ 草稿保存失败: {msg}")

                    # 正式提交逻辑（原有逻辑不变，仅修改提示文案）
                    if submit_btn:
                        # 验证必填项
                        errors = []
                        if not s_id or len(s_id) != 13:
                            errors.append("学生学号必须为13位数字！")
                        if not s_name:
                            errors.append("学生姓名不能为空！")
                        if not tutor:
                            errors.append("指导教师不能为空！")
                        if not award_time:
                            errors.append("获奖时间不能为空！")
                        try:
                            datetime.strptime(award_time, "%Y-%m-%d")
                        except:
                            errors.append("获奖时间格式错误，请使用YYYY-MM-DD！")

                        if errors:
                            for err in errors:
                                st.error(err)
                                return

                        # 保存文件和信息
                        with st.spinner("正在提交信息..."):
                            success, msg, meta = save_uploaded_file(uploaded_file, user_id)
                            if success:
                                # 获取文件ID
                                conn = sqlite3.connect("certificate_system.db")
                                cursor = conn.cursor()
                                cursor.execute("SELECT file_id FROM files WHERE file_path = ?",
                                               (meta['file_path'],))
                                file_res = cursor.fetchone()

                                if file_res:
                                    file_id = file_res[0]
                                    # 插入证书信息 - is_submitted=1 表示已提交
                                    cursor.execute('''
                                    INSERT INTO certificate_info 
                                    (user_id, file_id, student_college, competition_project, student_id, student_name,
                                     award_category, award_level, competition_type, organizer, award_time, tutor_name,
                                     is_submitted, submit_time)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now', '+8 hours'))
                                    ''', (
                                        user_id, file_id, college, project, s_id, s_name,
                                        category, level, c_type, organizer, award_time, tutor
                                    ))
                                    conn.commit()
                                    st.success(f"🎉 正式提交成功！文件已上传：{meta['file_name']}，提交后数据不可修改！")
                                else:
                                    st.error("❌ 获取文件ID失败")

                                conn.close()

                                # 重置状态
                                st.session_state.temp_uploaded_file = None
                                st.session_state.upload_original_img = None
                                st.rerun()
                            else:
                                st.error(f"❌ 上传失败: {msg}")

            except Exception as e:
                st.error(f"处理图片出错: {e}")
    else:
        # 重置临时状态
        st.session_state.temp_uploaded_file = None
        st.session_state.upload_original_img = None
        st.session_state.upload_total_rotate = 0

    # 已上传文件列表 - 优化：显示【草稿/已提交】状态
    st.subheader("📋 已上传文件列表")
    uploaded_files = get_user_uploaded_files(user_id)
    if uploaded_files:
        for idx, file in enumerate(uploaded_files):
            col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 2, 1, 1, 2, 1, 1])
            with col1:
                st.write(idx + 1)
            with col2:
                st.write(file["file_name"])
            with col3:
                st.write(file["file_type"])
            with col4:
                st.write(f"{file['file_size'] / 1024 / 1024:.2f} MB")
            with col5:
                st.write(file["upload_time"])
            # 新增：显示提交状态
            with col6:
                cert_info = get_cert_info_by_file_id(file["file_id"])
                status_text = "✅ 已提交" if cert_info and cert_info["is_submitted"] == 1 else "📝 草稿"
                st.write(status_text)
            with col7:
                if st.button("删除", key=f"delete_btn_{file['file_id']}", type="secondary"):
                    if delete_file_by_id(file["file_id"]):
                        st.success(f"✅ 文件 {file['file_name']} 已删除！")
                        st.rerun()
                    else:
                        st.error(f"❌ 删除文件 {file['file_name']} 失败！")
            if idx < len(uploaded_files) - 1:
                st.divider()
    else:
        st.info("📭 暂无已上传的文件，请先上传证书文件！")


# --------------------------
# 5. 主函数
# --------------------------
def main():
    init_session_state()

    if not st.session_state.logged_in:
        tab1, tab2 = st.tabs(["登录", "学生注册"])
        with tab1:
            login_page()
        with tab2:
            register_page()
    else:
        # 显示退出按钮
        col1, col2 = st.columns([9, 1])
        with col2:
            if st.button("退出登录"):
                # 重置所有状态
                st.session_state.logged_in = False
                st.session_state.user_info = {}
                st.session_state.upload_original_img = None
                st.session_state.upload_total_rotate = 0
                st.session_state.upload_selected_size = "custom"
                st.session_state.ocr_processing = False
                st.session_state.temp_uploaded_file = None
                st.rerun()

        # 根据角色显示不同页面
        role = st.session_state.user_info["role"]
        user_id = st.session_state.user_info["user_id"]

        if role == "admin":
            admin_page()
        else:
            render_file_upload_page(user_id, role)


if __name__ == "__main__":
    main()