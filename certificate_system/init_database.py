import sqlite3
import bcrypt

def init_database():
    """初始化数据库（整合所有表结构 + 初始化默认数据）"""
    conn = sqlite3.connect("certificate_system.db")
    cursor = conn.cursor()

    # 1. 用户表（兼容原有结构 + 约束）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'admin')),
        department TEXT NOT NULL,
        email TEXT,
        password_hash TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 2. 文件表（保持原有结构 + 外键约束）
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
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE
    )
    ''')

    # 4. 新增：系统配置表（存储提交截止时间等配置）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_config (
        config_id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_key TEXT UNIQUE NOT NULL,
        config_value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 5. 初始化系统配置（提交截止时间）
    cursor.execute("SELECT 1 FROM system_config WHERE config_key = 'submit_deadline'")
    if not cursor.fetchone():
        cursor.execute('''
        INSERT INTO system_config (config_key, config_value)
        VALUES ('submit_deadline', '2025-12-31 23:59:59')
        ''')

    # 6. 初始化默认管理员账号
    admin_account = "88888888"  # 管理员8位工号
    cursor.execute("SELECT 1 FROM users WHERE account_id = ?", (admin_account,))
    if not cursor.fetchone():
        # 密码：Admin123456（bcrypt加密）
        password = "Admin123456"
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        cursor.execute('''
        INSERT INTO users (account_id, name, role, department, email, password_hash)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            admin_account,
            "系统管理员",
            "admin",  # 修复原错误的角色值（原是Admin123456）
            "系统管理部",
            "admin@school.edu.cn",
            password_hash
        ))

    # 提交所有修改
    conn.commit()
    conn.close()

# 单独执行该文件时初始化数据库
if __name__ == "__main__":
    init_database()
    print("数据库初始化完成！")