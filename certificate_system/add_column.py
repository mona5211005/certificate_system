import sqlite3

# 连接你的项目数据库
conn = sqlite3.connect("certificate_system.db")
cursor = conn.cursor()

# 核心SQL：给system_config表新增updated_at字段，允许为空，文本类型
cursor.execute('''
ALTER TABLE system_config 
ADD COLUMN updated_at TEXT
''')

conn.commit()  # 提交修改
conn.close()   # 关闭连接
print("字段 updated_at 创建成功！")