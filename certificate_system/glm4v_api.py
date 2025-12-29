import hmac
import base64
import hashlib
import time
import json
import requests
from typing import Dict, Optional

# 智谱AI GLM-4V API 地址
GLM4V_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def load_api_config(config_path: str = "api_config.json") -> Dict:
    """加载API配置文件"""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return {}


def generate_token(api_key: str, exp_seconds: int = 3600) -> str:
    """
    生成智谱AI所需的JWT Token
    不依赖第三方jwt库，手动实现HMAC-SHA256签名
    """
    try:
        id, secret = api_key.split(".")
    except ValueError:
        raise ValueError("API Key格式不正确，应为 id.secret")
    # Header
    header = {"alg": "HS256", "sign_type": "SIGN"}
    header_json = json.dumps(header, separators=(',', ':'))
    header_b64 = base64.urlsafe_b64encode(header_json.encode('utf-8')).decode('utf-8').rstrip('=')
    # Payload
    now = int(time.time())
    payload = {
        "api_key": id,
        "exp": now + exp_seconds,
        "timestamp": now
    }
    payload_json = json.dumps(payload, separators=(',', ':'))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode('utf-8')).decode('utf-8').rstrip('=')
    # Signature
    signing_content = f"{header_b64}.{payload_b64}"
    signature = hmac.new(secret.encode('utf-8'), signing_content.encode('utf-8'), hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def call_ocr_api(img_base64: str) -> Dict:
    """
    调用GLM-4V API进行图片识别
    返回原始的API响应字典
    """
    config = load_api_config()
    api_key = config.get("glm4v_api_key")
    if not api_key:
        return {"error": "未配置API密钥，请检查 api_config.json", "raw_response": None}
    try:
        token = generate_token(api_key)
        # 构造Prompt，要求模型返回特定JSON格式
        prompt_text = """
        请识别图片中的证书信息，并以纯JSON格式返回。不要包含任何Markdown标记或其他解释文字。
        JSON对象必须包含以下10个字段：
        1. student_college (学生所在学院)
        2. competition_project (竞赛项目)
        3. student_id (学号)
        4. student_name (学生姓名)
        5. award_category (获奖类别：如国家级、省级)
        6. award_level (获奖等级：如一等奖、金奖)
        7. competition_type (竞赛类型：如A类、B类)
        8. organizer (主办单位)
        9. award_time (获奖时间，格式YYYY-MM-DD)
        10. tutor_name (指导教师)
        如果图片中无法识别某个字段，请将该字段值设为null。
        """
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "glm-4v",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                    ]
                }
            ],
            "temperature": 0.1
        }
        response = requests.post(GLM4V_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"网络请求失败: {str(e)}", "raw_response": None}
    except Exception as e:
        return {"error": f"API调用异常: {str(e)}", "raw_response": None}