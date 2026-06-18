# utils/data_generator.py
import random
import string
from datetime import datetime, timedelta
from typing import Any, List, Optional, Union
from faker import Faker
fake = Faker("zh_CN")


def generate_test_data(data_type: str, **kwargs):
    """
    生成自动化测试所需的随机数据
    """
    if data_type == "cn_phone":
        # unique=True 确保本轮测试中号码不重复（慎用，耗性能）
        return fake.unique.phone_number() if kwargs.get("unique") else fake.phone_number()

    elif data_type == "cn_name":
        return fake.name()

    elif data_type == "cn_email":
        # 生成拼音邮箱，更符合中国用户习惯
        return fake.email()

    elif data_type == "cn_id_card":
        return fake.ssn()

    elif data_type == "cn_address":
        return fake.address()

    elif data_type == "cn_company":
        return fake.company()

    elif data_type == "alipay_account":
        # 70%概率生成手机号，30%概率生成邮箱
        return fake.phone_number() if fake.boolean(chance_of_getting_true=70) else fake.email()

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
        import uuid
        return str(uuid.uuid4())

    elif value_type == "alipay":
        p =  random.choice(["3", "5", "7", "8", "9"]) + "1"  + "".join(random.choices(string.digits, k=12))
        return p

    else:
        raise ValueError(f"不支持的类型: {value_type}")


if __name__ == "__main__":

    print(generate_random_value("str"))
