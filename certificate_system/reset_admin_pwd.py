import sqlite3
from passlib.context import CryptContext

# 1. 配置密码加密（和系统验证逻辑完全一致）
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    default="pbkdf2_sha256",
    pbkdf2_sha256__default_rounds=600000
)
# 生成密码admin的正确哈希值
admin_hash = pwd_context.hash("admin")

# 2. 连接数据库并重置密码
conn = sqlite3.connect("certificate_system.db")
cursor = conn.cursor()

try:
    # 先检查管理员账号是否存在，不存在则创建
    cursor.execute("SELECT 1 FROM users WHERE account_id = '88888888'")
    if cursor.fetchone() is None:
        # 创建管理员账号
        cursor.execute("""
            INSERT INTO users (
                account_id, name, role, department, email, 
                password_hash, is_active, created_at, created_by
            ) VALUES (
                '88888888', '系统管理员', 'admin', '教务处', 
                'admin@school.edu.cn', ?, 1, datetime('now'), 'system'
            )
        """, (admin_hash,))
    else:
        # 重置现有管理员密码
        cursor.execute("""
            UPDATE users 
            SET password_hash = ? 
            WHERE account_id = '88888888'
        """, (admin_hash,))

    conn.commit()
    print("✅ 管理员密码重置成功！")
    print("账号：88888888")
    print("密码：admin")
except Exception as e:
    print(f"❌ 重置失败：{e}")
    conn.rollback()
finally:
    conn.close()