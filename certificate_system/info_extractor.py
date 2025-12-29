import json
from typing import Dict, List, Optional

# 定义必须提取的10个字段
REQUIRED_FIELDS = [
    "student_college",
    "competition_project",
    "student_id",
    "student_name",
    "award_category",
    "award_level",
    "competition_type",
    "organizer",
    "award_time",
    "tutor_name"
]


def parse_api_response(api_response: Dict) -> Dict:
    """
    解析API返回的字典，提取并清洗10个字段信息
    Args:
        api_response: glm4v_api.call_ocr_api 返回的原始字典
    Returns:
        包含状态 和数据 的字典
    """
    # 1. 检查API调用是否出错
    if "error" in api_response:
        return {
            "status": "failed",
            "error": api_response.get("error"),
            "data": None
        }
    # 2. 提取文本内容
    try:
        choices = api_response.get("choices", [])
        if not choices:
            return {"status": "failed", "error": "API返回内容为空", "data": None}
        content = choices[0].get("message", {}).get("content", "")
    except Exception as e:
        return {"status": "failed", "error": f"解析API结构失败: {e}", "data": None}
    # 3. 清洗内容 (去除Markdown代码块标记)
    content = content.replace("```json", "").replace("```", "").strip()
    # 4. 解析JSON
    json_data = None
    try:
        json_data = json.loads(content)
    except json.JSONDecodeError:
        # 如果直接解析失败，尝试截取第一个JSON对象
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        if start_idx != -1 and end_idx > start_idx:
            try:
                json_data = json.loads(content[start_idx:end_idx])
            except:
                return {"status": "failed", "error": "无法解析JSON内容", "raw_content": content}
    if not json_data:
        return {"status": "failed", "error": "未找到有效的JSON数据", "raw_content": content}
    # 5. 字段对齐与标准化
    extracted_data = {}
    missing_fields = []
    for field in REQUIRED_FIELDS:
        value = json_data.get(field)
        if value is None:
            missing_fields.append(field)
            extracted_data[field] = ""  # 缺失字段设为空字符串
        else:
            extracted_data[field] = str(value).strip()  # 确保是字符串且去除首尾空格
    # 6. 返回结果
    result = {
        "status": "success",
        "data": extracted_data
    }
    if missing_fields:
        result["warning"] = f"以下字段识别为空: {', '.join(missing_fields)}"
    return result


def save_result_to_log(image_name: str, result: Dict, log_file: str = "extraction_results.json"):
    """
    将提取结果追加保存到日志文件
    """
    log_entry = {
        "timestamp": __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "image_name": image_name,
        "status": result.get("status"),
        "error": result.get("error"),
        "data": result.get("data")
    }
    logs = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logs = []
    logs.append(log_entry)
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)