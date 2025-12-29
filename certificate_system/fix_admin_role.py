import sqlite3

# 连接数据库并修改角色
conn = sqlite3.connect("certificate_system.db")
cursor = conn.cursor()

try:
    # 将账号88888888的角色改为admin
    cursor.execute("""
        UPDATE users 
        SET role = 'admin' 
        WHERE account_id = '88888888'
    """)
    conn.commit()
    print("✅ 已将账号88888888的角色修改为管理员！")
except Exception as e:
    print(f"❌ 修改失败：{e}")
finally:
    conn.close()