from passlib.context import CryptContext

# 新版passlib标准配置（下划线格式，无警告、无报错）
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],  # 下划线格式（新版要求）
    default="pbkdf2_sha256",    # 和schemes中的名称完全一致
    pbkdf2_sha256__default_rounds=29000  # 迭代次数（可选，默认600000）
)

# 生成密码"admin"的哈希值（格式：pbkdf2:sha256:29000$xxx$xxx）
hash_password = pwd_context.hash("admin")
print("✅ 密码admin对应的哈希值：")
print(hash_password)

# 验证哈希值是否正确（测试用）
is_correct = pwd_context.verify("admin", hash_password)
print(f"\n✅ 密码验证结果：{is_correct}")  # 输出True表示正确