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
      - uid
      - product_title, product_detail, product
      - logistics_no (物流单号字符串)
      - logistics (完整物流信息字典)
    """
    # ===== 原有逻辑保持不变 =====
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

    elif data_type == "product_title":
        data = _generate_product_data()
        return f"{data['condition']}{data['brand']}{data['category']}{data['model']}"

    elif data_type == "product_detail":
        data = _generate_product_data()
        return f"本商品为{data['condition']}，品牌{data['brand']}，型号{data['model']}。外观保护良好，功能一切正常，附带原装配件。"

    elif data_type == "product":
        data = _generate_product_data()
        return {
            "title": f"{data['condition']} {data['brand']} {data['category']} {data['model']}",
            "detail": f"本商品为{data['condition']}，品牌{data['brand']}，型号{data['model']}。外观保护良好，功能一切正常。",
            "category": data["category"],
            "brand": data["brand"],
            "condition": data["condition"],
            "price": data["price"]
        }

    # ========== 新增：极简物流号生成 ==========
    elif data_type in ("logistics_no", "logistics"):
        # 快递公司规则：前缀 + 数字长度
        rules = {
            "sf":  ("SF", 12),   # 顺丰
            "zto": ("ZTO", 12),  # 中通
            "sto": ("STO", 12),  # 申通
            "yto": ("YTO", 12),  # 圆通
            "yd":  ("YD", 13),   # 韵达
            "ems": ("EMS", 13),  # EMS
        }
        # 指定公司或随机选一个
        code = kwargs.get("company", random.choice(list(rules.keys())))
        prefix, length = rules[code]

        # 生成数字部分（顺丰最后一位当随机数即可，测试环境无需严格校验）
        number = "".join(random.choices("0123456789", k=length))
        tracking_no = f"{prefix}{number}"

        # 仅单号
        if data_type == "logistics_no":
            return tracking_no

        # 完整信息
        name_map = {"sf":"顺丰速运","zto":"中通快递","sto":"申通快递","yto":"圆通速递","yd":"韵达快递","ems":"EMS"}
        return {
            "company": name_map[code],
            "company_code": code,
            "tracking_no": tracking_no
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

    print(generate_test_data("logistics_no", company="sf"))
