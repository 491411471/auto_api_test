# # 先执行 pip install faker
# import random
#
# def gen_prod():
#     return f"{random.choice(['新款','便携','无线','智能','高清'])}-{random.choice(['蓝牙耳机','机械键盘','速干T恤','保温杯','背包'])}-{random.choice(['黑','白','灰','蓝','红'])}"
#
# # 测试
# print(gen_prod())  # 输出示例：新款 机械键盘 (黑)
#
#
# import uuid
#
# def generate_uuid():
#     """生成随机 UUID (Version 4)"""
#     return str(uuid.uuid4())
#
# # 测试
# print(generate_uuid())
# 输出示例：'f47ac10b-58cc-4372-a567-0e02b2c3d479'

# import requests
# from pathlib import Path
#
# # 获取当前脚本所在目录，构建图片的绝对路径
# image_path = str(Path(__file__).parent / "data" / "scenario" / "images" / "test_image.png")
#
# def upload_path(p):
#     headers={"token": "jyiv98yq07k0wccgfnpjnmgc39t2umg4"}
#     r = requests.post("https://test.llxzu.com/hzsx/busShop/doUpLoadwebp", files={'file': open(p, 'rb')}, headers=headers)
#     return r.json().get('data', '') if r.json().get('businessSuccess') else ''
#
#
# image_url = upload_path(image_path)
# print(image_url)  # 输出: https://oss.llxzu.com/69bcd72d79f347f7bfcbcfa1ef3fc82a.jpeg

import json
import random
import uuid
import requests
from datetime import datetime, timedelta
from pathlib import Path
headers = {"token": "jyiv98yq07k0wccgfnpjnmgc39t2umg4"}
# ==================== 辅助函数 ====================
def gen_prod():
    """生成随机商品名称"""
    return f"{random.choice(['新款','便携','无线','智能','高清'])}-{random.choice(['蓝牙耳机','机械键盘','速干T恤','保温杯','背包'])}-{random.choice(['黑','白','灰','蓝','红'])}"

def generate_uuid():
    """生成随机 UUID (Version 4)"""
    return str(uuid.uuid4())

def upload_path(p):
    """上传图片并返回 URL"""
    try:
        # 验证文件是否存在
        if not Path(p).exists():
            return ''

        with open(p, 'rb') as f:
            response = requests.post(
                "https://test.llxzu.com/hzsx/busShop/doUpLoadwebp",
                files={'file': f},
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            return data.get('data', '') if data.get('businessSuccess') else ''
    except (requests.RequestException, ValueError, KeyError):
        return ''

# ==================== 转换函数 ====================
def transform_product_json(original_json_str: str) -> dict:
    """
    对商品 JSON 进行动态字段替换，返回转换后的字典对象。
    """
    data = original_json_str

    # 1. 替换 name 和 title
    new_name = gen_prod()
    data['name'] = new_name
    if 'title' in data:
        data['title'] = new_name

    # 2. 递归替换所有 uuid 字段
    def replace_uuid(obj):
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                if k == 'uuid':
                    obj[k] = generate_uuid()
                else:
                    replace_uuid(v)
        elif isinstance(obj, list):
            for item in obj:
                replace_uuid(item)
    replace_uuid(data)

    # 3. 处理 productSkusInventoryList 日期替换
    # 生成未来 14 天的日期列表（格式 YYYY-MM-DD）
    today = datetime.now().date()
    date_range = [(today + timedelta(days=i)).isoformat() for i in range(14)]

    inventory_list = data.get('productSkusInventoryList', [])
    if inventory_list:
        # 获取原始库存值（取第一个条目的第一个值，若无则默认 100）
        sample_map = inventory_list[0].get('dateDayInventoryMap', {})
        sample_value = next(iter(sample_map.values())) if sample_map else 100
    else:
        sample_value = 100

    new_inventory_list = []
    for item in inventory_list:
        new_map = {date: sample_value for date in date_range}
        new_item = {
            "productSpecName1": item.get("productSpecName1", ""),
            "productSpecName2": item.get("productSpecName2", ""),
            "productSpecName3": item.get("productSpecName3", ""),
            "dateDayInventoryMap": new_map
        }
        new_inventory_list.append(new_item)
    data['productSkusInventoryList'] = new_inventory_list

    # 同步更新 calendar 字段（如果存在）
    if 'calendar' in data and isinstance(data['calendar'], list):
        # 注意：calendar 结构可能与 productSkusInventoryList 不同，但通常保持一致
        data['calendar'] = new_inventory_list

    # 4. 替换 images 列表中的 src 和 url
    image_path = Path(__file__).parent / "data" / "scenario" / "images" / "test_image.png"
    uploaded_url = upload_path(str(image_path))
    if uploaded_url:
        images = data.get('images', [])
        for img in images:
            img['src'] = uploaded_url
            img['url'] = uploaded_url
        # 如果存在顶级 src 且为 null，也替换
        if 'src' in data and data['src'] is None:
            data['src'] = uploaded_url

    # 可选：清除 productId（新建商品不应携带旧 ID）
    if 'productId' in data:
        data['productId'] = ""
    if 'id' in data:
        data['id'] = 0   # 或删除该字段

    return data

# ==================== 调用接口 ====================
def create_product(api_base_url: str, product_data: dict, token: str = None):
    """
    发送 POST 请求创建商品
    api_base_url: 接口基础地址（例如 https://test.llxzu.com）
    product_data: 转换后的商品数据字典
    token: 可选，如果接口需要 token，传入后添加到头部
    """
    url = f"{api_base_url.rstrip('/')}/hzsx/product/busInsertProduct"

    response = requests.post(url, json=product_data, headers=headers)
    print(f"HTTP 状态码: {response.status_code}")
    print("响应内容:", json.dumps(response.json(), ensure_ascii=False, indent=2))
    return response.json()

# 使用示例
if __name__ == '__main__':

    d={'records': [{'id': 1880, 'createTime': '2024-08-05 08:23:10', 'updateTime': '2026-05-11 10:28:42', 'deleteTime': None, 'name': '会员服务', 'content': '<p>测试</p><div class="media-wrap image-wrap"><img class="media-wrap image-wrap" src="https://oss.llxzu.com/89cb07b7a1134a6abe6e44abaa0dbc7b.jpg"/></div><p></p><div class="media-wrap image-wrap"><img class="media-wrap image-wrap" src="https://oss.llxzu.com/afaff9bc600f45a2b9bb2008b13ea9ff.png"/></div><p></p><div class="media-wrap image-wrap"><img class="media-wrap image-wrap" src="https://oss.llxzu.com/d3c13105e1d645bcb6c32c87786d095c.jpg"/></div><p>阿三顶顶顶顶顶顶顶顶顶顶顶顶</p>', 'price': 20.0, 'priceSwitch': 1, 'settlementProportion': 0.01, 'channelGroupCode': '001', 'productId': '1724158348103,1742449848998,1746502593642,1761293435541,1776397753719,1778222526454', 'beizhu': None, 'productIds': ['1724158348103', '1742449848998', '1746502593642', '1761293435541', '1776397753719', '1778222526454'], 'skuPriceSwitch': 1, 'skuPrices': None, 'shopId': '71008738021cd3393bacbac182bd6a86af0b5c87', 'isDefaultType': None, 'isShow': 1, 'productType': '00', 'premiumFee': None}, {'id': 1994, 'createTime': '2026-03-03 10:21:13', 'updateTime': '2026-03-13 13:56:50', 'deleteTime': None, 'name': '溢价费', 'content': '<p>溢价费</p>', 'price': 200.0, 'priceSwitch': 1, 'settlementProportion': 0.8, 'channelGroupCode': '001', 'productId': 'PremiumFee', 'beizhu': None, 'productIds': ['PremiumFee'], 'skuPriceSwitch': 0, 'skuPrices': None, 'shopId': '', 'isDefaultType': 1, 'isShow': 1, 'productType': '00', 'premiumFee': 'PremiumFee'}], 'total': 2, 'size': 1000, 'current': 1, 'orders': [], 'optimizeCountSql': True, 'hitCount': False, 'searchCount': True, 'pages': 1}
    print(len(d))