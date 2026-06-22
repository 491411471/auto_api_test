# testcases/admin/api/order/test_set_order_to_shop.py
"""
运营端 - 订单列表：转订单接口测试
接口：GET /hzsx/ope/order/set_order_to_shop

用例流程：
  1. 前置SQL：从源店铺查询一条状态为10（可转单）的订单号
  2. 调用转单接口，将订单转入目标店铺
  3. 响应断言：验证接口返回 businessSuccess=true
  4. 后置SQL：验证订单已存在于目标店铺中
"""
import allure
import pytest

from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables


_DATA_FILE = "data/admin/api/order/set_order_to_shop.yaml"


@allure.epic("运营端")
@allure.feature("运营端-订单管理")
@allure.story("转订单")
class TestSetOrderToShop:
    """转订单 - 将订单从源店铺转入目标店铺"""

    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    @pytest.mark.parametrize(
        "case",
        get_test_data(_DATA_FILE, "set_order_to_shop_tests"),
        ids=[c["case_id"] for c in get_test_data(_DATA_FILE, "set_order_to_shop_tests")],
    )
    def test_set_order_to_shop(self, admin_api_client, db, case):
        # 1. 加载全局变量
        global_vars = self._load_global_vars()

        # 2. 合并用例级别变量（如果有）
        if "variables" in case and isinstance(case["variables"], dict):
            global_vars.update(case["variables"])

        # 3. 更新 Allure 标题
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")

        # 4. 执行测试（框架自动处理前置SQL、变量替换、API请求、断言、后置SQL验证）
        execute_test_case(case, admin_api_client, db, global_vars)
