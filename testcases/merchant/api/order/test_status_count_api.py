# testcases/api/order/test_status_count_api.py
"""
本模块用于测试订单状态统计接口，验证接口返回的各类订单状态数量是否正确。
测试策略：通过直接查询数据库获取各状态订单的真实数量，与接口返回的统计数据进行对比断言。
"""
import allure
import pytest
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables

@allure.feature("商家端-订单模块")
@allure.story("订单查询")
class TestStatusCount:
    """
    订单状态统计接口测试类
    """
    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("order_status_count_api.yaml")
        return cls._global_vars.copy()

    @pytest.mark.smoke
    @pytest.mark.parametrize("case", get_test_data("order_status_count_api.yaml", "order_status_tests"))
    def test_status_count(self, api_client, db, case):
        global_vars = self._load_global_vars()
        # 如果用例内部定义了 variables，合并（用例级优先级更高）
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        execute_test_case(case, api_client, db, global_vars)