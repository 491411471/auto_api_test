from faker import Faker

fake = Faker('zh_CN')
def generate_chinese_name(existing_set=None):
    """生成较低重复率的名字"""
    if existing_set is None:
        return fake.name()
    while True:
        name = fake.name()
        if name not in existing_set:
            existing_set.add(name)
            return name



def gen_chinese_street():
    """随机生成中文街道地址"""
    return fake.street_address()
# 使用示例
print(gen_chinese_street())  # 输出：海淀区中关村大街1号
# 使用示例
if __name__ == '__main__':

    import math

    r=math.ceil(74 / 10)
    print(r)