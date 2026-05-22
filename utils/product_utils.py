"""
商品测试相关的公共工具函数
用于生成测试数据、上传图片等
"""
import re
import uuid
from datetime import datetime, timedelta
import os
from typing import Any, Dict
import random
from pathlib import Path


def gen_product_name() -> str:
    """
    生成带自动化测试标识的商品名称
    
    Returns:
        str: 格式化的商品名称，如 "【自动化测试】新款-蓝牙耳机-黑"
    """
    prefix = "【自动化测试】"
    adj = random.choice(['新款', '便携', '无线', '智能', '高清'])
    product = random.choice(['蓝牙耳机', '机械键盘', '鼠标', '电脑充电器', '无线耳机', 'ThinkPad', 'ipad'])
    color = random.choice(['黑', '白', '灰', '蓝', '红', '黄', '绿', '紫', '粉'])
    return f"{prefix}{adj}-{product}-{color}"


def generate_uuid() -> str:
    """
    生成 UUID v4
    
    Returns:
        str: UUID 字符串
    """
    return str(uuid.uuid4())


def upload_test_image(api_client, image_path: str) -> str:
    """
    上传图片并返回 URL
    Args:
        api_client: API 客户端实例
        image_path: 图片文件路径（绝对路径或相对路径）
    Returns:
        str: 图片 URL
    Raises:
        RuntimeError: 图片上传失败时抛出异常
        FileNotFoundError: 图片文件不存在时抛出异常
    """
    # 获取当前文件所在目录的父目录的父目录（绝对路径）
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = Path(current_file_dir).parent  # 项目根目录

    # 处理传入的 image_path
    # 如果是以 / 开头的路径，视为相对于项目根目录的路径
    if image_path.startswith('/'):
        # 移除开头的 /，然后拼接项目根目录
        relative_path = image_path.lstrip('/')
        full_path = base_dir / relative_path
    elif Path(image_path).is_absolute():
        # 如果是真正的绝对路径（如 D:\...），直接使用
        full_path = Path(image_path)
    else:
        # 否则是相对路径，拼接项目根目录
        full_path = base_dir / image_path
    
    print("full_path:", full_path)
    print("base_dir:", base_dir)
    # 验证文件是否存在
    if not full_path.exists():
        raise FileNotFoundError(f"图片文件不存在: {full_path}")

    # 上传图片
    with open(full_path, 'rb') as f:
        resp = api_client.post("/hzsx/busShop/doUpLoadwebp", files={'file': f})

    data = resp.json()

    # 检查业务是否成功
    if data.get('businessSuccess'):
        image_url = data.get('data', '')
        if image_url:
            return image_url

    # 上传失败时，打印完整响应以便调试
    error_msg = data.get('errorMessage') or data.get('message') or data.get('error') or '未知错误'
    raise RuntimeError(f"图片上传失败: {error_msg}\n完整响应: {data}")


def generate_inventory_date_map(days: int = 14) -> Dict[str, int]:
    """
    生成库存日期映射（未来 N 天）
    
    Args:
        days: 天数，默认 14 天
        
    Returns:
        Dict[str, int]: 日期到库存数量的映射，如 {"2024-01-01": 100, ...}
    """
    today = datetime.now().date()
    return {(today + timedelta(days=i)).isoformat(): 100 for i in range(days)}


def replace_placeholders(obj: Any, variables: Dict[str, Any]) -> Any:
    """
    递归替换对象中所有字符串里的 ${key} 占位符
    
    Args:
        obj: 待替换的对象（可以是字符串、字典、列表或基本类型）
        variables: 变量字典，键为占位符名称，值为替换值
        
    Returns:
        Any: 替换后的对象
        
    Examples:
        >>> variables = {"name": "test", "id": 123}
        >>> replace_placeholders("${name}", variables)
        'test'
        >>> replace_placeholders({"key": "${id}"}, variables)
        {'key': 123}
    """
    if isinstance(obj, str):
        # 如果整个字符串就是一个占位符，直接返回对应的值（保持原始类型）
        for key, value in variables.items():
            placeholder = f"${{{key}}}"
            if obj == placeholder:
                return replace_placeholders(value, variables)
        
        # 否则进行字符串替换
        def replacer(match):
            key = match.group(1)
            return str(variables[key]) if key in variables else match.group(0)
        
        return re.sub(r'\$\{([^}]+)}', replacer, obj)
    
    elif isinstance(obj, dict):
        return {k: replace_placeholders(v, variables) for k, v in obj.items()}
    
    elif isinstance(obj, list):
        return [replace_placeholders(item, variables) for item in obj]
    
    else:
        return obj
