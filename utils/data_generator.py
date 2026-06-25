# utils/data_generator.py
import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Any, List, Optional, Union
from faker import Faker
fake = Faker("zh_CN")

# ---------- 二手商品专用词汇库 ----------
PRODUCT_CATEGORIES = ["手机"]
BRAND_MAP = {"手机": ["苹果", "华为", "小米", "三星", "OPPO", "vivo"]}
MODEL_SUFFIX = {"手机": ["Pro", "Max", "Ultra", "SE", "Plus", "青春版"]}
CONDITIONS = ["精品二手", "精品准新", "99新", "几乎全新", "轻微使用痕迹", "无划痕", "保修期内"]
FEATURES = ["功能完好", "原装无修", "电池健康度高", "屏幕完美", "配件齐全", "已贴膜", "带保护壳"]

def _generate_product_data():
    """生成一组关联的商品数据（品类、品牌、型号、成色、特征）"""
    category = random.choice(PRODUCT_CATEGORIES)
    brand = random.choice(BRAND_MAP[category])
    model = random.choice(MODEL_SUFFIX.get(category, ["标准版"]))
    condition = random.choice(CONDITIONS)
    return {
        "category": category,
        "brand": brand,
        "model": model,
        "condition": condition,
        "price": round(random.uniform(500, 15000), 2)  # 随机价格
    }

def generate_test_data(data_type: str, **kwargs):
    """
    生成自动化测试所需的随机数据
    支持类型:
      - cn_phone, cn_name, cn_email, cn_id_card, cn_address, cn_company, alipay_account
      - uid (返回32位十六进制UUID)
      - product_title (独立生成商品标题)
      - product_detail (独立生成商品详情)
      - product (返回完整商品信息，标题和详情强关联)
    """
    if data_type == "cn_phone":
        return fake.unique.phone_number() if kwargs.get("unique") else fake.phone_number()

    elif data_type == "cn_name":
        return fake.name()

    elif data_type == "cn_email":
        return fake.email()

    elif data_type == "cn_id_card":
        return fake.ssn()

    elif data_type == "cn_address":
        return fake.address()

    elif data_type == "cn_company":
        return fake.company()

    elif data_type == "alipay_account":
        return fake.phone_number() if fake.boolean(chance_of_getting_true=70) else fake.email()

    elif data_type == "uid":
        return uuid.uuid4().hex

    # ---------- 独立生成商品标题（有真实感，但与其他调用不强制关联） ----------
    elif data_type == "product_title":
        # 每次调用都随机生成一组数据，用于构建标题
        data = _generate_product_data()
        # 标题格式：成色 + 品牌 + 品类 + 型号 + 特征摘要
        title = f"{data['condition']}{data['brand']}{data['category']}{data['model']}"
        # 若传入 length，可控制标题字数（此处简单截断或扩展，但为保持自然，暂不处理）
        return title

    # ---------- 独立生成商品详情（有真实感，但与其他调用不强制关联） ----------
    elif data_type == "product_detail":
        data = _generate_product_data()
        # 构建详情段落，包含成色、功能、配件、建议等内容
        detail = (f"本商品为{data['condition']}，品牌{data['brand']}，型号{data['model']}。"
                  f"外观保护良好，功能一切正常，附带原装配件。"
                  f"适合自用或送礼，性价比高。")
        return detail

    # ---------- 强关联的完整商品信息 ----------
    elif data_type == "product":
        data = _generate_product_data()
        title = f"{data['condition']} {data['brand']} {data['category']} {data['model']} {random.choice(data['features'])}"
        detail = (f"本商品为{data['condition']}，品牌{data['brand']}，型号{data['model']}。"
                  f"外观保护良好，功能一切正常，附带原装配件。"
                  f"适合自用或送礼，性价比高。")
        # 同时可返回更多字段
        return {
            "title": title,
            "detail": detail,
            "category": data["category"],
            "brand": data["brand"],
            "condition": data["condition"],
            "price": data["price"]
        }

    else:
        raise ValueError(f"Unsupported data type: {data_type}")


def generate_random_value(
        value_type: str,
        min_val: Optional[Union[int, float]] = None,
        max_val: Optional[Union[int, float]] = None,
        choices: Optional[List[Any]] = None,
        length: Optional[int] = None,
        **kwargs
) -> Any:
    """
    生成随机测试数据
    支持类型: int, float, str, choice, bool, date, datetime, phone, email, uuid
    """
    min_val = min_val or 0
    max_val = max_val or 100
    length = length or 10

    if value_type == "int":
        return random.randint(int(min_val), int(max_val))

    elif value_type == "float":
        return round(random.uniform(float(min_val), float(max_val)), 2)

    elif value_type == "str":
        str_type = kwargs.get("str_type", "alphanumeric")
        include_symbols = kwargs.get("include_symbols", False)

        if str_type == "alpha":
            chars = string.ascii_letters
        elif str_type == "digits":
            chars = string.digits
        elif str_type == "alphanumeric":
            chars = string.ascii_letters + string.digits
        elif str_type == "chinese":
            chars = [chr(i) for i in range(0x4E00, 0x9FA5)]
        else:
            chars = string.printable

        if include_symbols:
            chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"
        return ''.join(random.choice(chars) for _ in range(length))

    elif value_type == "choice":
        if not choices:
            raise ValueError("choice 类型需要提供 choices 参数")
        return random.choice(choices)

    elif value_type == "bool":
        return random.choice([True, False])

    elif value_type == "date":
        fmt = kwargs.get("date_format", "%Y-%m-%d")
        start = datetime.now() - timedelta(days=365*5)
        end = datetime.now() + timedelta(days=365*5)
        delta = end - start
        random_date = start + timedelta(days=random.randrange(delta.days))
        return random_date.strftime(fmt)

    elif value_type == "datetime":
        fmt = kwargs.get("date_format", "%Y-%m-%d %H:%M:%S")
        start = datetime.now() - timedelta(days=365*5)
        end = datetime.now() + timedelta(days=365*5)
        delta_sec = int((end - start).total_seconds())
        random_sec = random.randrange(delta_sec)
        random_dt = start + timedelta(seconds=random_sec)
        return random_dt.strftime(fmt)

    elif value_type == "phone":
        prefix = random.choice(["13","14","15","16","17","18","19"])
        suffix = ''.join(random.choice(string.digits) for _ in range(9))
        return prefix + suffix

    elif value_type == "email":
        domains = ["gmail.com","yahoo.com","hotmail.com","company.com"]
        username = ''.join(random.choice(string.ascii_lowercase+string.digits) for _ in range(length))
        return f"{username}@{random.choice(domains)}"

    elif value_type == "uuid":
        return uuid.uuid4().hex  # 直接拿hex属性，无横杠

    elif value_type == "alipay":
        p =  random.choice(["3", "5", "7", "8", "9"]) + "1"  + "".join(random.choices(string.digits, k=12))
        return p

    else:
        raise ValueError(f"不支持的类型: {value_type}")


if __name__ == "__main__":

    print(generate_test_data("cn_address"))
