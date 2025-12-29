import sqlite3

# 连接数据库
conn = sqlite3.connect("certificate_system.db")
cursor = conn.cursor()

# 1. 先备份旧users表数据（如果有）
cursor.execute("ALTER TABLE users RENAME TO users_old")

# 2. 重新创建带account_id列的users表
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

# 3. 迁移旧数据（如果旧表有数据，根据实际列名调整）
# 先查看旧表结构
cursor.execute("PRAGMA table_info(users_old);")
old_columns = [col[1] for col in cursor.fetchall()]
print("旧表列名：", old_columns)

# 如果旧表有类似账号的列（比如id/student_id等），替换下面的迁移逻辑
try:
    # 示例：假设旧表用user_id作为账号，迁移到account_id
    cursor.execute('''
    INSERT INTO users (account_id, name, role, department, email, password_hash, is_active)
    SELECT CAST(user_id AS TEXT), name, role, department, email, password_hash, is_active 
    FROM users_old
    ''')
    print("旧数据迁移成功")
except Exception as e:
    print("数据迁移失败（无旧数据）：", e)

# 4. 删除旧表
cursor.execute("DROP TABLE IF EXISTS users_old")

# 5. 重新初始化管理员账号
admin_account = "88888888"
cursor.execute("SELECT 1 FROM users WHERE account_id = ?", (admin_account,))
if not cursor.fetchone():
    import bcrypt
    password = "Admin123456"
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    cursor.execute('''
    INSERT INTO users (account_id, name, role, department, email, password_hash)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        admin_account,
        "系统管理员",
        "admin",
        "系统管理部",
        "admin@school.edu.cn",
        password_hash
    ))

conn.commit()
conn.close()
print("表结构修复完成！")