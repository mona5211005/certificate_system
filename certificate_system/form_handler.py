import streamlit as st
import os
import sys
import json
import requests
from datetime import datetime
from typing import Optional, Dict, List
from PIL import Image, ImageDraw, ImageFont
import sqlite3
import io
import base64
import bcrypt
from pdf2image import convert_from_bytes
import locale
import warnings
import urllib3

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --------------------------
# 模拟外部封装模块
# --------------------------
class glm4v_api:
    """GLM-4V API配置管理模块"""
    CONFIG_FILE = "glm4v_config.json"

    @staticmethod
    def load_api_config() -> dict:
        if os.path.exists(glm4v_api.CONFIG_FILE):
            with open(glm4v_api.CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"glm4v_api_key": ""}

    @staticmethod
    def save_api_config(api_key: str) -> bool:
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
        if "error" in raw_response:
            return {"status": "failed", "error": raw_response["error"], "data": {}}

        result_data = {}
        fields = ["student_college", "competition_project", "student_id",
                  "student_name", "award_category", "award_level",
                  "competition_type", "organizer", "award_time", "tutor_name"]

        for field in fields:
            result_data[field] = raw_response.get(field, "") or ""

        missing_fields = [f for f, v in result_data.items() if not v]
        warning = ""
        if missing_fields:
            warning = f"部分字段识别失败：{', '.join(missing_fields)}，请手动补充"

        return {"status": "success", "data": result_data, "warning": warning}

    @staticmethod
    def save_result_to_log(file_name: str, result: dict):
        log_dir = "ocr_logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"ocr_log_{datetime.now().strftime('%Y%m%d')}.json")
        log_data = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "file_name": file_name, "result": result}
        try:
            existing_logs = []
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    existing_logs = json.load(f)
            existing_logs.append(log_data)
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(existing_logs, f, ensure_ascii=False, indent=2)
        except:
            pass

# --------------------------
# 基础配置 & 常量定义
# --------------------------
try:
    locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
except:
    pass
os.environ['TZ'] = 'Asia/Shanghai'

UPLOAD_FOLDER = "uploads"
EXCEL_TEMPLATE_FOLDER = "excel_templates"
OCR_LOG_FOLDER = "ocr_logs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXCEL_TEMPLATE_FOLDER, exist_ok=True)
os.makedirs(OCR_LOG_FOLDER, exist_ok=True)

ROLE_DISPLAY_MAP = {"student": "学生", "teacher": "教师", "admin": "管理员"}
STANDARD_SIZES = {"A4": (2100, 2970), "A5": (1480, 2100), "custom": (0, 0)}

config = glm4v_api.load_api_config()
GLM4V_API_KEY = config.get("glm4v_api_key", "")
urllib3.disable_warnings()

# --------------------------
# 1. 数据库初始化 + 所有数据库操作函数
# --------------------------
def init_database():
    conn = sqlite3.connect("certificate_system.db")
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
        role TEXT NOT NULL, department TEXT NOT NULL, email TEXT, password_hash TEXT NOT NULL,
        is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS files (
        file_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, file_name TEXT NOT NULL,
        file_path TEXT NOT NULL, file_type TEXT NOT NULL, file_size INTEGER NOT NULL,
        upload_time TIMESTAMP DEFAULT (datetime('now', '+8 hours')),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS certificate_info (
        cert_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, file_id INTEGER NOT NULL,
        student_college TEXT, competition_project TEXT, student_id TEXT, student_name TEXT,
        award_category TEXT, award_level TEXT, competition_type TEXT, organizer TEXT, award_time TEXT, tutor_name TEXT,
        is_submitted INTEGER DEFAULT 0, submit_time TIMESTAMP,
        created_at TIMESTAMP DEFAULT (datetime('now', '+8 hours')),
        updated_at TIMESTAMP DEFAULT (datetime('now', '+8 hours')),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS system_config (
        config_id INTEGER PRIMARY KEY AUTOINCREMENT, config_key TEXT UNIQUE NOT NULL,
        config_value TEXT NOT NULL, updated_at TIMESTAMP DEFAULT (datetime('now', '+8 hours')))''')

    cursor.execute("SELECT 1 FROM system_config WHERE config_key = 'submit_deadline'")
    if not cursor.fetchone():
        cursor.execute('INSERT INTO system_config (config_key, config_value) VALUES (?, ?)', ('submit_deadline', '2025-12-31 23:59:59'))

    admin_account = "88888888"
    cursor.execute("SELECT 1 FROM users WHERE account_id = ?", (admin_account,))
    if not cursor.fetchone():
        password = "Admin123456"
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        cursor.execute('INSERT INTO users (account_id, name, role, department, email, password_hash) VALUES (?, ?, ?, ?, ?, ?)',
                       (admin_account, "系统管理员", "admin", "系统管理部", "admin@school.edu.cn", password_hash))

    conn.commit()
    conn.close()

if not os.path.exists("certificate_system.db"):
    init_database()

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
        cursor.execute('INSERT INTO users (account_id, name, role, department, email, password_hash) VALUES (?, ?, ?, ?, ?, ?)',
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
    cursor.execute('SELECT user_id, account_id, name, role, department, email, is_active, password_hash FROM users WHERE account_id = ?', (account_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"user_id": result[0], "account_id": result[1], "name": result[2], "role": result[3], "department": result[4], "email": result[5], "is_active": result[6], "password_hash": result[7]}
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
        cursor.execute('SELECT user_id, account_id, name, role, department, email, is_active, created_at FROM users WHERE role = ?', (role,))
    else:
        cursor.execute('SELECT user_id, account_id, name, role, department, email, is_active, created_at FROM users')
    results = cursor.fetchall()
    conn.close()
    users = []
    for r in results:
        users.append({"user_id": r[0], "account_id": r[1], "name": r[2], "role": r[3], "department": r[4], "email": r[5], "is_active": r[6], "created_at": r[7]})
    return users

def save_file_metadata(user_id: int, file_name: str, file_path: str, file_type: str, file_size: int) -> bool:
    try:
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        cursor.execute('INSERT INTO files (user_id, file_name, file_path, file_type, file_size) VALUES (?, ?, ?, ?, ?)', (user_id, file_name, file_path, file_type, file_size))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存文件元信息失败：{e}")
        return False

def get_user_uploaded_files(user_id: int) -> List[dict]:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute('SELECT file_id, file_name, file_path, file_type, file_size, upload_time FROM files WHERE user_id = ? ORDER BY upload_time DESC', (user_id,))
    results = cursor.fetchall()
    conn.close()
    files = []
    for r in results:
        files.append({"file_id": r[0], "file_name": r[1], "file_path": r[2], "file_type": r[3], "file_size": r[4], "upload_time": r[5]})
    return files

def check_file_duplicate(user_id: int, file_name: str, file_size: int) -> bool:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM files WHERE user_id = ? AND file_name = ? AND file_size = ?', (user_id, file_name, file_size))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def delete_file_by_id(file_id: int) -> bool:
    try:
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM files WHERE file_id = ?", (file_id,))
        file_path = cursor.fetchone()
        if file_path:
            file_path = file_path[0]
            cursor.execute("DELETE FROM certificate_info WHERE file_id = ?", (file_id,))
            cursor.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
            conn.commit()
            conn.close()
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
    query = '''SELECT ci.*, u.name as submitter_name, u.role as submitter_role, u.department as submitter_dept, f.file_name, f.file_path
    FROM certificate_info ci LEFT JOIN users u ON ci.user_id = u.user_id LEFT JOIN files f ON ci.file_id = f.file_id WHERE 1=1'''
    params = []
    if filters:
        if filters.get("award_category"): query += " AND ci.award_category = ?"; params.append(filters["award_category"])
        if filters.get("award_level"): query += " AND ci.award_level = ?"; params.append(filters["award_level"])
        if filters.get("submitter_role"): query += " AND u.role = ?"; params.append(filters["submitter_role"])
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    cols = [desc[0] for desc in cursor.description]
    certs = []
    for r in results: certs.append(dict(zip(cols, r)))
    return certs

def update_deadline(new_deadline: str) -> bool:
    for key in list(st.session_state.keys()):
        if "deadline_error" in key: del st.session_state[key]
    try:
        datetime.strptime(new_deadline, "%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        cursor.execute('UPDATE system_config SET config_value = ?, updated_at = datetime(\'now\', \'+8 hours\') WHERE config_key = \'submit_deadline\'', (new_deadline,))
        conn.commit()
        conn.close()
        return True
    except ValueError:
        st.error("时间格式错误！请使用YYYY-MM-DD HH:MM:SS格式（如：2025-12-31 23:59:59）")
        return False

def get_submit_deadline() -> datetime:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'submit_deadline'")
    result = cursor.fetchone()
    conn.close()
    return datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S") if result else datetime(2025, 12, 31, 23, 59, 59)

def get_cert_info_by_file_id(file_id: int) -> Optional[dict]:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM certificate_info WHERE file_id = ? LIMIT 1', (file_id,))
    result = cursor.fetchone()
    conn.close()
    if result: cols = [desc[0] for desc in cursor.description]; return dict(zip(cols, result))
    return None

def batch_submit_draft(user_id: int) -> bool:
    try:
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        cursor.execute('UPDATE certificate_info SET is_submitted = 1, submit_time = datetime(\'now\', \'+8 hours\'), updated_at = datetime(\'now\', \'+8 hours\') WHERE user_id = ? AND is_submitted = 0', (user_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0
    except Exception as e:
        print(f"批量提交失败：{e}")
        return False

def get_user_cert_status(user_id: int) -> dict:
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM certificate_info WHERE user_id = ? AND is_submitted = 0', (user_id,))
    draft_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM certificate_info WHERE user_id = ? AND is_submitted = 1', (user_id,))
    submit_count = cursor.fetchone()[0]
    conn.close()
    return {"draft": draft_count, "submitted": submit_count}

# --------------------------
# 2. 文件处理与视觉识别模块
# --------------------------
def validate_upload_file(file) -> tuple[bool, str, str]:
    file_size = file.size
    if file_size > 10 * 1024 * 1024: return False, "文件大小超过10MB限制！", ""
    file_ext = os.path.splitext(file.name)[1].lower()
    allowed_types = [".pdf", ".jpg", ".jpeg", ".png", ".bmp"]
    if file_ext not in allowed_types: return False, f"不支持的文件类型！仅支持：{allowed_types}", ""
    file_type = "pdf" if file_ext == ".pdf" else "image"
    return True, "", file_type

def pdf_to_image(pdf_data: bytes) -> Image.Image:
    try:
        pages = convert_from_bytes(pdf_data, 300)
        return pages[0]
    except Exception as e:
        warnings.warn(f"PDF转换失败: {e}")
        default_img = Image.new('RGB', (2100, 2970), color='white')
        draw = ImageDraw.Draw(default_img)
        try: font = ImageFont.truetype("simhei.ttf", 60)
        except: font = ImageFont.load_default(size=60)
        text = "PDF预览失败：请安装poppler并配置环境变量\n或检查PDF文件是否损坏"
        text_bbox = draw.textbbox((0,0), text, font=font)
        x = (2100 - (text_bbox[2]-text_bbox[0]))/2
        y = (2970 - (text_bbox[3]-text_bbox[1]))/2
        draw.text((x, y), text, fill='red', font=font)
        return default_img

def rotate_image(img: Image.Image, angle: int) -> Image.Image:
    return img.rotate(angle, expand=True)

def resize_image(img: Image.Image, size_type: str) -> Image.Image:
    if size_type == "custom": return img
    target_width, target_height = STANDARD_SIZES[size_type]
    img_ratio = img.width / img.height
    target_ratio = target_width / target_height
    if img_ratio > target_ratio:
        new_width = target_width; new_height = int(new_width / img_ratio)
    else:
        new_height = target_height; new_width = int(new_height * img_ratio)
    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)

def generate_final_image(original_img: Image.Image, total_rotate_angle: int, size_type: str) -> Image.Image:
    rotated_img = rotate_image(original_img, total_rotate_angle % 360)
    resized_img = resize_image(rotated_img, size_type)
    return resized_img

def pil_image_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def image_to_base64(img_input):
    try:
        if isinstance(img_input, Image.Image):
            img_rgb = img_input.convert('RGB')
            buf = io.BytesIO()
            img_rgb.save(buf, format='JPEG', quality=70, subsampling=0)
            img_binary = buf.getvalue()
            if not img_binary or len(img_binary) < 100: return ""
            base64_str = base64.b64encode(img_binary).decode('utf-8')
            return f"data:image/jpeg;base64,{base64_str}"
        else: return ""
    except Exception as e:
        print(f"❌ 图片转码异常: {str(e)}")
        return ""

def call_ocr_api(img_source: Image.Image, is_url=False) -> dict:
    final_result = {"student_college": "", "competition_project": "", "student_id": "",
        "student_name": "", "award_category": "", "award_level": "",
        "competition_type": "", "organizer": "", "award_time": "", "tutor_name": ""}
    img_base64 = image_to_base64(img_source)
    if not img_base64 or len(img_base64) < 200:
        final_result["competition_type"] = "学科竞赛"; final_result["award_category"] = "省级"; return final_result

    api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {"Content-Type": "application/json;charset=utf-8", "Authorization": f"Bearer {GLM4V_API_KEY}"}
    prompt = """你是专业的赛事获奖证书信息提取专家，严格按要求执行，只返回标准JSON字符串，不要任何多余文字、换行、解释、备注、标点符号。
提取固定字段(英文key不可修改，识别不到则为空字符串)：student_college, competition_project, student_id, student_name, award_category, award_level, competition_type, organizer, award_time, tutor_name
提取规则：1.严格返回JSON格式，无其他内容；2.competition_type固定填写「学科竞赛」；3.award_category只能填写「国家级」或「省级」；4.如实识别，严禁编造任何信息；5.只输出JSON字符串。"""
    req_data = {"model": "glm-4v", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": img_base64}}]}], "temperature": 0.0, "top_p": 0.8, "max_tokens": 2048, "stream": False}
    body = json.dumps(req_data, ensure_ascii=False)

    try:
        res = requests.post(api_url, headers=headers, data=body.encode('utf-8'), timeout=80, allow_redirects=False, verify=False)
        if res.status_code == 200:
            res_json = res.json()
            content = res_json.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if content and "{" in content and "}" in content:
                start = content.find("{"); end = content.rfind("}") +1
                parse_data = json.loads(content[start:end], strict=False)
                for key in final_result.keys():
                    if key in parse_data and str(parse_data[key]).strip() not in ["无", "空", "-", "", "N/A", "暂无"]:
                        final_result[key] = str(parse_data[key]).strip()
    except Exception as e: print(f"❌ 识别接口调用异常: {str(e)}")

    if not final_result["competition_type"]: final_result["competition_type"] = "学科竞赛"
    if not final_result["award_category"]: final_result["award_category"] = "省级"
    return final_result

def save_uploaded_file(file, user_id: int) -> tuple[bool, str, dict]:
    try:
        is_valid, err_msg, file_type = validate_upload_file(file)
        if not is_valid: return False, err_msg, {}
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_ext = os.path.splitext(file.name)[1]
        filename = f"user_{user_id}_{timestamp}{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(file_path, "wb") as f: f.write(file.getbuffer())
        file_size = os.path.getsize(file_path)
        if save_file_metadata(user_id, file.name, file_path, file_type, file_size):
            file_meta = {"file_name": file.name, "file_path": file_path, "file_type": file_type, "file_size": file_size}
            return True, "", file_meta
        os.remove(file_path)
        return False, "数据库保存失败", {}
    except Exception as e: return False, str(e), {}

# --------------------------
# 3. 会话状态初始化
# --------------------------
def init_session_state():
    if "logged_in" not in st.session_state: st.session_state.logged_in = False
    if "user_info" not in st.session_state: st.session_state.user_info = {}
    if "active_tab" not in st.session_state: st.session_state.active_tab = "login"
    if "upload_original_img" not in st.session_state: st.session_state.upload_original_img = None
    if "upload_total_rotate" not in st.session_state: st.session_state.upload_total_rotate = 0
    if "upload_selected_size" not in st.session_state: st.session_state.upload_selected_size = "custom"
    if "preview_original_imgs" not in st.session_state: st.session_state.preview_original_imgs = {}
    if "preview_total_rotate" not in st.session_state: st.session_state.preview_total_rotate = {}
    if "preview_selected_size" not in st.session_state: st.session_state.preview_selected_size = {}
    if "ocr_processing" not in st.session_state: st.session_state.ocr_processing = False
    if "ocr_result" not in st.session_state:
        st.session_state.ocr_result = {"student_college": "", "competition_project": "", "student_id": "", "student_name": "", "award_category": "", "award_level": "", "competition_type": "", "organizer": "", "award_time": "", "tutor_name": ""}
    if "temp_uploaded_file" not in st.session_state: st.session_state.temp_uploaded_file = None
    if "temp_file_meta" not in st.session_state: st.session_state.temp_file_meta = {}
    if "import_report" not in st.session_state: st.session_state.import_report = {"success": 0, "failed": [], "total": 0}
    if "delete_confirm" not in st.session_state: st.session_state.delete_confirm = {}
    if "submitting_file_key" not in st.session_state: st.session_state.submitting_file_key = None

# --------------------------
# 4. 登录/注册表单页面
# --------------------------
def login_page():
    st.title("🔐 证书提交与管理系统 - 登录")
    col1, col2 = st.columns([1,1])
    with col1:
        account_id = st.text_input("学/工号", placeholder="学生13位数字 | 教师/管理员8位数字")
        password = st.text_input("密码", type="password", placeholder="至少8位，包含字母+数字")
        role = st.selectbox("角色", ["student", "teacher", "admin"], format_func=lambda x: ROLE_DISPLAY_MAP[x])
        login_btn = st.button("登录", type="primary", use_container_width=True)
        if login_btn:
            if not account_id or not password: st.error("学/工号和密码不能为空！"); return
            if not validate_account_format(account_id, role): st.error(f"{ROLE_DISPLAY_MAP[role]}学/工号格式错误！"); return
            user = get_user_by_account(account_id)
            if not user: st.error("学/工号不存在！"); return
            if not user["is_active"]: st.error("账号已被禁用，请联系管理员！"); return
            if not verify_password(password, user["password_hash"]): st.error("密码错误！"); return
            st.session_state.logged_in = True; st.session_state.user_info = user
            st.success(f"✅ 欢迎 {user['name']}（{ROLE_DISPLAY_MAP[user['role']]}）登录！"); st.rerun()
    with col2:
        st.info("📢 系统说明")
        st.markdown("""- 学生账号：13位数字学工号，密码自行注册设置
- 教师账号：8位数字工号，初始密码由管理员分配
- 管理员账号：88888888，初始密码：Admin123456
- 密码规则：至少8位，包含字母+数字！""")

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
            if not all([account_id, name, department, email, password, confirm_pwd]): st.error("所有字段不能为空！"); return
            if not validate_account_format(account_id, "student"): st.error("学生学工号必须是13位纯数字！"); return
            if password != confirm_pwd: st.error("两次密码不一致！"); return
            if not validate_password(password): st.error("密码必须至少8位，且包含字母+数字！"); return
            if check_account_exists(account_id): st.error("学工号已存在！"); return
            if create_user(account_id, name, "student", department, email, password): st.success("✅ 注册成功！请返回登录页面登录")
            else: st.error("❌ 注册失败，请联系管理员！")
    if st.button("🔙 返回登录", use_container_width=True):
        st.session_state.active_tab = "login"; st.rerun()

# --------------------------
# 5. 证书上传表单页面（学生/教师共用）
# --------------------------
def render_file_upload_page(user_id: int, user_role: str):
    global GLM4V_API_KEY
    st.title(f"📄 证书上传与智能识别 - {ROLE_DISPLAY_MAP[user_role]}")
    deadline = get_submit_deadline()
    now = datetime.now()
    if now > deadline and user_role != "admin":
        st.warning(f"⚠️ 提交已截止（截止时间：{deadline.strftime('%Y-%m-%d %H:%M:%S')}），无法新增/修改数据！")
        st.subheader("📋 已上传文件列表")
        uploaded_files = get_user_uploaded_files(user_id)
        if uploaded_files:
            for idx, file in enumerate(uploaded_files):
                col1, col2, col3, col4, col5, col6, col7 = st.columns([1,2,1,1,2,1,1])
                with col1: st.write(idx+1);
                with col2: st.write(file["file_name"]);
                with col3: st.write(file["file_type"])
                with col4: st.write(f"{file['file_size']/1024/1024:.2f} MB");
                with col5: st.write(file["upload_time"])
                with col6: cert_info = get_cert_info_by_file_id(file["file_id"]); st.write("✅ 已提交" if cert_info and cert_info["is_submitted"] ==1 else "📝 草稿")
                with col7:
                    if st.button("删除", key=f"delete_btn_deadline_{file['file_id']}", type="secondary"):
                        if delete_file_by_id(file["file_id"]): st.success(f"✅ 文件 {file['file_name']} 已删除！"); st.rerun()
                        else: st.error(f"❌ 删除失败！")
                if idx < len(uploaded_files)-1: st.divider()
        return

    cert_status = get_user_cert_status(user_id)
    col1, col2 = st.columns(2)
    with col1: st.success(f"📝 我的草稿数量：{cert_status['draft']}"); with_col2: st.info(f"✅ 我的已提交数量：{cert_status['submitted']}")
    st.divider()

    if cert_status['draft'] >0:
        if st.button("🚀 批量提交所有草稿", type="primary", use_container_width=True):
            with st.spinner("批量提交中..."):
                if batch_submit_draft(user_id): st.success(f"🎉 批量提交成功！共提交 {cert_status['draft']} 条草稿"); st.rerun()
                else: st.error("❌ 批量提交失败！")
        st.divider()

    st.subheader("📌 上传要求")
    st.markdown("- 支持格式：PDF、JPG、PNG、JPEG、BMP\n- 大小限制：单个文件≤10MB\n- PDF文件会自动提取首页转换为图片预览\n- 支持图片旋转、尺寸调整")

    config = glm4v_api.load_api_config()
    api_key = config.get("glm4v_api_key", "")
    if not api_key:
        with st.expander("🔑 GLM-4V API 配置", expanded=True):
            temp_key = st.text_input("输入API Key以启用识别功能", type="password", key="temp_api_key_input")
            if temp_key: api_key = temp_key; GLM4V_API_KEY = temp_key; st.success("API Key 已临时设置")

    st.subheader("🔸 步骤1：上传证书文件")
    uploaded_file = st.file_uploader("选择证书文件", type=["pdf", "jpg", "jpeg", "png", "bmp"], accept_multiple_files=False, key="cert_uploader")
    if uploaded_file:
        st.session_state.temp_uploaded_file = uploaded_file
        is_valid, err_msg, file_type = validate_upload_file(uploaded_file)
        if not is_valid: st.error(f"❌ {err_msg}"); st.session_state.temp_uploaded_file = None
        else:
            st.info(f"✅ 文件验证通过：{uploaded_file.name}")
            try:
                if st.session_state.upload_original_img is None:
                    if file_type == "pdf": original_img = pdf_to_image(uploaded_file.getvalue())
                    else: original_img = Image.open(uploaded_file)
                    st.session_state.upload_original_img = original_img; st.session_state.upload_total_rotate =0

                st.subheader("🔸 步骤2：图片预览与处理")
                st.write(f"当前累计旋转角度：{st.session_state.upload_total_rotate}°")
                rotate_step = st.selectbox("选择旋转角度", [90,180,270,0], key="rotate_step")
                if st.button("执行旋转", key="do_rotate"):
                    st.session_state.upload_total_rotate = 0 if rotate_step ==0 else st.session_state.upload_total_rotate + rotate_step

                target_size = st.selectbox("图片尺寸预设", list(STANDARD_SIZES.keys()), index=list(STANDARD_SIZES.keys()).index(st.session_state.upload_selected_size), format_func=lambda x: f"{x} ({STANDARD_SIZES[x][0]}x{STANDARD_SIZES[x][1]})", key="target_size")
                st.session_state.upload_selected_size = target_size
                final_img = generate_final_image(st.session_state.upload_original_img, st.session_state.upload_total_rotate, target_size)

                st.subheader("🖼️ 图片预览")
                st.write(f"原始尺寸：{st.session_state.upload_original_img.size} | 处理后尺寸：{final_img.size}")
                st.image(final_img, width=600)

                st.subheader("🔸 步骤3：智能识别证书信息")
                if not st.session_state.ocr_processing:
                    if st.button("🔍 使用GLM-4V提取信息", type="primary", disabled=not api_key):
                        if not api_key: st.error("请先配置API Key"); return
                        st.session_state.ocr_processing = True
                        with st.spinner("识别中..."):
                            raw_response = call_ocr_api(final_img, is_url=False)
                            parsed_obj = info_extractor.parse_api_response(raw_response)
                            info_extractor.save_result_to_log(uploaded_file.name, parsed_obj)
                            if parsed_obj['status'] == 'failed': st.error(f"❌ 识别失败: {parsed_obj['error']}")
                            else: st.success("✅ 识别成功！请核对信息"); st.session_state.ocr_result = parsed_obj['data']
                            if parsed_obj.get("warning"): st.warning(f"⚠️ {parsed_obj['warning']}")
                        st.session_state.ocr_processing = False

                st.subheader("🔸 步骤4：信息核对与提交")
                ocr_data = st.session_state.ocr_result
                user_info = st.session_state.user_info
                with st.form("cert_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        s_id = st.text_input("学生学号*", value=ocr_data.get("student_id") if user_role != "student" else user_info["account_id"], disabled=(user_role=="student"))
                        s_name = st.text_input("学生姓名*", value=ocr_data.get("student_name") if user_role != "student" else user_info["name"], disabled=(user_role=="student"))
                        tutor = st.text_input("指导教师*", value=ocr_data.get("tutor_name") if user_role == "student" else user_info["name"])
                        college = st.text_input("学生学院", value=ocr_data.get("student_college"))
                        project = st.text_input("竞赛项目", value=ocr_data.get("competition_project"))
                        category = st.selectbox("获奖类别", ["", "国家级", "省级"], index=["", "国家级", "省级"].index(ocr_data.get("award_category")) if ocr_data.get("award_category") in ["国家级", "省级"] else 0)
                    with col2:
                        level = st.selectbox("获奖等级", ["", "一等奖", "二等奖", "三等奖", "金奖", "银奖", "铜奖", "优秀奖"], index=["", "一等奖", "二等奖", "三等奖", "金奖", "银奖", "铜奖", "优秀奖"].index(ocr_data.get("award_level")) if ocr_data.get("award_level") in ["一等奖", "二等奖", "三等奖", "金奖", "银奖", "铜奖", "优秀奖"] else 0)
                        c_type = st.selectbox("竞赛类型", ["", "A类", "B类"], index=["", "A类", "B类"].index(ocr_data.get("competition_type")) if ocr_data.get("competition_type") in ["A类", "B类"] else 0)
                        organizer = st.text_input("主办单位", value=ocr_data.get("organizer"))
                        award_time = st.text_input("获奖时间 (YYYY-MM-DD)*", value=ocr_data.get("award_time"))

                    col_btn1, col_btn2 = st.columns(2)
                    save_draft_btn = col_btn1.form_submit_button("💾 保存为草稿", type="secondary")
                    submit_btn = col_btn2.form_submit_button("📤 正式提交（不可修改）", type="primary")

                    if save_draft_btn:
                        errors = []
                        if not s_id: errors.append("学生学号不能为空！")
                        if not s_name: errors.append("学生姓名不能为空！")
                        if not tutor: errors.append("指导教师不能为空！")
                        if not award_time: errors.append("获奖时间不能为空！")
                        if errors: [st.error(e) for e in errors]; return
                        with st.spinner("保存草稿中..."):
                            success, msg, meta = save_uploaded_file(uploaded_file, user_id)
                            if success:
                                conn = sqlite3.connect("certificate_system.db")
                                cursor = conn.cursor()
                                cursor.execute("SELECT file_id FROM files WHERE file_path = ?", (meta['file_path'],))
                                file_id = cursor.fetchone()[0]
                                cursor.execute('INSERT INTO certificate_info (user_id, file_id, student_college, competition_project, student_id, student_name, award_category, award_level, competition_type, organizer, award_time, tutor_name, is_submitted, submit_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)', (user_id, file_id, college, project, s_id, s_name, category, level, c_type, organizer, award_time, tutor))
                                conn.commit(); conn.close()
                                st.success(f"✅ 草稿保存成功！"); st.session_state.temp_uploaded_file = None; st.session_state.upload_original_img = None; st.rerun()
                            else: st.error(f"❌ {msg}")

                    if submit_btn:
                        errors = []
                        if not s_id or len(s_id)!=13: errors.append("学生学号必须为13位数字！")
                        if not s_name: errors.append("学生姓名不能为空！")
                        if not tutor: errors.append("指导教师不能为空！")
                        if not award_time: errors.append("获奖时间不能为空！")
                        try: datetime.strptime(award_time, "%Y-%m-%d")
                        except: errors.append("获奖时间格式错误，请使用YYYY-MM-DD！")
                        if errors: [st.error(e) for e in errors]; return
                        with st.spinner("提交中..."):
                            success, msg, meta = save_uploaded_file(uploaded_file, user_id)
                            if success:
                                conn = sqlite3.connect("certificate_system.db")
                                cursor = conn.cursor()
                                cursor.execute("SELECT file_id FROM files WHERE file_path = ?", (meta['file_path'],))
                                file_id = cursor.fetchone()[0]
                                cursor.execute('INSERT INTO certificate_info (user_id, file_id, student_college, competition_project, student_id, student_name, award_category, award_level, competition_type, organizer, award_time, tutor_name, is_submitted, submit_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime(\'now\', \'+8 hours\'))', (user_id, file_id, college, project, s_id, s_name, category, level, c_type, organizer, award_time, tutor))
                                conn.commit(); conn.close()
                                st.success(f"🎉 正式提交成功！"); st.session_state.temp_uploaded_file = None; st.session_state.upload_original_img = None; st.rerun()
                            else: st.error(f"❌ {msg}")
            except Exception as e: st.error(f"处理图片出错: {e}")
    else:
        st.session_state.temp_uploaded_file = None; st.session_state.upload_original_img = None; st.session_state.upload_total_rotate =0

    st.subheader("📋 已上传文件列表")
    uploaded_files = get_user_uploaded_files(user_id)
    if uploaded_files:
        for idx, file in enumerate(uploaded_files):
            col1, col2, col3, col4, col5, col6, col7 = st.columns([1,2,1,1,2,1,1])
            with col1: st.write(idx+1);with_col2: st.write(file["file_name"]);with_col3: st.write(file["file_type"])
            with col4: st.write(f"{file['file_size']/1024/1024:.2f} MB");
            with col5: st.write(file["upload_time"])
            with col6: cert_info = get_cert_info_by_file_id(file["file_id"]); st.write("✅ 已提交" if cert_info and cert_info["is_submitted"] ==1 else "📝 草稿")
            with col7:
                if st.button("删除", key=f"delete_btn_{file['file_id']}", type="secondary"):
                    if delete_file_by_id(file["file_id"]): st.success(f"✅ 文件 {file['file_name']} 已删除！"); st.rerun()
                    else: st.error(f"❌ 删除失败！")
            if idx < len(uploaded_files)-1: st.divider()
    else: st.info("📭 暂无已上传的文件，请先上传证书文件！")