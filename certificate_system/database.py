import sqlite3
import bcrypt  # 统一使用bcrypt加密，替换原hashlib
import hashlib  # 保留兼容，实际使用bcrypt

# --------------------------
# 核心数据库操作函数
# --------------------------
def init_database():
    """初始化数据库表结构（整合新增表，兼容原有逻辑）"""
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()

    # 1. 用户表（兼容原有结构 + 适配bcrypt）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'admin')),
        department TEXT NOT NULL,
        email TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT DEFAULT 'self_register'
    )
    ''')

    # 2. 文件表（保持原有结构）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        file_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_type TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    ''')

    # 3. 新增：证书信息表（存储识别/提交的证书数据）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS certificate_info (
        cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        file_id INTEGER NOT NULL,
        student_college TEXT,
        competition_project TEXT,
        student_id TEXT,
        student_name TEXT,
        award_category TEXT,  -- 国家级、省级
        award_level TEXT,     -- 一等奖、二等奖等
        competition_type TEXT,-- A类、B类
        organizer TEXT,
        award_time TEXT,
        tutor_name TEXT,
        is_submitted INTEGER DEFAULT 0,  -- 0-草稿，1-已提交
        submit_time TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (file_id) REFERENCES files(file_id)
    )
    ''')

    # 4. 新增：系统配置表（存储提交截止时间）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_config (
        config_id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_key TEXT UNIQUE NOT NULL,
        config_value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 5. 初始化截止时间（若不存在）
    cursor.execute("SELECT 1 FROM system_config WHERE config_key = 'submit_deadline'")
    if not cursor.fetchone():
        cursor.execute('''
        INSERT INTO system_config (config_key, config_value)
        VALUES ('submit_deadline', '2025-12-31 23:59:59')
        ''')

    # 6. 创建默认管理员账号（修复角色错误 + 使用bcrypt加密）
    admin_account = "88888888"
    cursor.execute("SELECT 1 FROM users WHERE account_id = ?", (admin_account,))
    if not cursor.fetchone():
        password = "Admin123456"
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        cursor.execute('''
        INSERT INTO users (account_id, name, role, department, email, password_hash, created_by)
        VALUES (?, '系统管理员', 'admin', '系统管理部', 'admin@school.edu.cn', ?, 'system')
        ''', (admin_account, password_hash))

    conn.commit()
    conn.close()


def hash_password(password):
    """密码加密（统一使用bcrypt）"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(input_pwd, stored_hash):
    """验证密码（适配bcrypt）"""
    try:
        return bcrypt.checkpw(input_pwd.encode('utf-8'), stored_hash.encode('utf-8'))
    except Exception:
        # 兼容旧hashlib加密的密码（兜底）
        return hashlib.sha256(input_pwd.encode('utf-8')).hexdigest() == stored_hash


def check_account_exists(account_id):
    """检查账号是否存在"""
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE account_id = ?", (account_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def validate_account_format(account_id, role):
    """验证学工号格式"""
    if not account_id.isdigit():
        return False
    if role == 'student' and len(account_id) != 13:
        return False
    if role in ['teacher', 'admin'] and len(account_id) != 8:
        return False
    return True


def create_user(account_id, name, role, department, email, password, created_by="self_register"):
    """创建用户"""
    try:
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        pwd_hash = hash_password(password)
        cursor.execute('''
        INSERT INTO users (account_id, name, role, department, email, password_hash, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (account_id, name, role, department, email, pwd_hash, created_by))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"创建用户失败：{e}")
        return False


def get_user_by_account(account_id):
    """根据账号获取用户信息"""
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute('''
    SELECT user_id, account_id, name, role, department, email, is_active, password_hash
    FROM users WHERE account_id = ?
    ''', (account_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return {
            "user_id": user[0],
            "account_id": user[1],
            "name": user[2],
            "role": user[3],
            "department": user[4],
            "email": user[5],
            "is_active": user[6],
            "password_hash": user[7]
        }
    return None


def get_all_users(role_filter=None):
    """获取所有用户"""
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    query = "SELECT account_id, name, role, department, email, is_active FROM users"
    params = []
    if role_filter:
        query += " WHERE role = ?"
        params.append(role_filter)
    cursor.execute(query, params)
    users = []
    for row in cursor.fetchall():
        users.append({
            "account_id": row[0],
            "name": row[1],
            "role": row[2],
            "department": row[3],
            "email": row[4],
            "is_active": row[5]
        })
    conn.close()
    return users


def update_user_status(account_id, is_active):
    """更新用户状态"""
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_active = ? WHERE account_id = ?", (is_active, account_id))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def save_file_metadata(user_id, file_name, file_path, file_type, file_size):
    """保存文件元信息"""
    try:
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO files (user_id, file_name, file_path, file_type, file_size)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, file_name, file_path, file_type, file_size))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存文件元信息失败：{e}")
        return False


def get_user_uploaded_files(user_id):
    """获取用户上传的文件"""
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute('''
    SELECT file_id, file_name, file_path, file_type, file_size, upload_time
    FROM files WHERE user_id = ? ORDER BY upload_time DESC
    ''', (user_id,))
    files = []
    for row in cursor.fetchall():
        files.append({
            "file_id": row[0],
            "file_name": row[1],
            "file_path": row[2],
            "file_type": row[3],
            "file_size": row[4],
            "upload_time": row[5]
        })
    conn.close()
    return files


def delete_file_by_id(file_id):
    """根据ID删除文件（数据库+本地）"""
    import os
    try:
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        # 先获取文件路径
        cursor.execute("SELECT file_path FROM files WHERE file_id = ?", (file_id,))
        file_path = cursor.fetchone()[0]
        # 删除数据库记录（级联删除certificate_info）
        cursor.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
        conn.commit()
        conn.close()
        # 删除本地文件
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except Exception as e:
        print(f"删除文件失败：{e}")
        return False

# --------------------------
# 新增：证书信息操作函数
# --------------------------
def save_certificate_info(cert_data):
    """保存证书识别信息"""
    try:
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO certificate_info (
            user_id, file_id, student_college, competition_project, student_id,
            student_name, award_category, award_level, competition_type,
            organizer, award_time, tutor_name, is_submitted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            cert_data["user_id"], cert_data["file_id"], cert_data["student_college"],
            cert_data["competition_project"], cert_data["student_id"], cert_data["student_name"],
            cert_data["award_category"], cert_data["award_level"], cert_data["competition_type"],
            cert_data["organizer"], cert_data["award_time"], cert_data["tutor_name"],
            cert_data.get("is_submitted", 0)
        ))
        conn.commit()
        conn.close()
        return cursor.lastrowid
    except Exception as e:
        print(f"保存证书信息失败：{e}")
        return None


def get_certificate_by_file_id(file_id):
    """根据文件ID获取证书信息"""
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM certificate_info WHERE file_id = ?", (file_id,))
    cert = cursor.fetchone()
    conn.close()
    if cert:
        return {
            "cert_id": cert[0],
            "user_id": cert[1],
            "file_id": cert[2],
            "student_college": cert[3],
            "competition_project": cert[4],
            "student_id": cert[5],
            "student_name": cert[6],
            "award_category": cert[7],
            "award_level": cert[8],
            "competition_type": cert[9],
            "organizer": cert[10],
            "award_time": cert[11],
            "tutor_name": cert[12],
            "is_submitted": cert[13],
            "submit_time": cert[14],
            "created_at": cert[15],
            "updated_at": cert[16]
        }
    return None


def update_certificate_status(cert_id, is_submitted=True):
    """更新证书提交状态"""
    try:
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE certificate_info 
        SET is_submitted = ?, submit_time = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE cert_id = ?
        ''', (1 if is_submitted else 0, cert_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"更新证书状态失败：{e}")
        return False


def get_system_config(config_key):
    """获取系统配置"""
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()
    cursor.execute("SELECT config_value FROM system_config WHERE config_key = ?", (config_key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def update_system_config(config_key, config_value):
    """更新系统配置"""
    try:
        conn = sqlite3.connect("certificate_system.db")
        cursor = conn.cursor()
        # 先查是否存在，不存在则插入
        cursor.execute("SELECT 1 FROM system_config WHERE config_key = ?", (config_key,))
        if cursor.fetchone():
            cursor.execute('''
            UPDATE system_config 
            SET config_value = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE config_key = ?
            ''', (config_value, config_key))
        else:
            cursor.execute('''
            INSERT INTO system_config (config_key, config_value)
            VALUES (?, ?)
            ''', (config_key, config_value))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"更新系统配置失败：{e}")
        return False