-- 初始化数据库表结构
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT UNIQUE NOT NULL,  -- 学/工号（学生13位，教师8位）
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'teacher', 'admin')),
    department TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'self_register'  -- self_register/admin_import
);

CREATE TABLE IF NOT EXISTS system_config (
    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER,
    FOREIGN KEY (updated_by) REFERENCES users(user_id)
);
-- 新增文件表（files）
CREATE TABLE IF NOT EXISTS files (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,  -- pdf/image
    file_size INTEGER NOT NULL,  -- 字节
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 原有表结构保持不变...

-- 初始化管理员账号（默认密码：Admin123456，需首次登录修改）
INSERT OR IGNORE INTO users (account_id, name, role, department, email, password_hash, created_by)
VALUES (
    'admin00000000',
    '系统管理员',
    'admin',
    '教务处',
    'admin@school.edu.cn',
    '$2b$12$EixZaYb4xU58Gpq1R0yWbeb00LU5qUaK65e2r0h8H8H8H8H8H8H8H',  -- 密码：Admin123456
    'system'
);

-- 初始化默认截止时间配置
INSERT OR IGNORE INTO system_config (config_key, config_value, description)
VALUES ('submission_deadline', '2025-12-31 23:59:59', '证书提交截止时间');