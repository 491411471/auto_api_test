"""
本模块用于测试订单分配责任人接口，验证接口返回的各类订单状态数量是否正确。
测试策略：通过直接查询数据库获取分配的真实数据，与接口返回的统计数据进行对比断言。
"""
import allure
import pytest
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables

@allure.feature("商家端-订单模块")
@allure.story("订单分配责任人")
class TestStatusCount:
    """
    订单分配责任人
    """
    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("order_batch_assign_responsible_person_api.yaml")
        return cls._global_vars.copy()

    @pytest.mark.smoke
    @pytest.mark.parametrize(
        "case",
        get_test_data("order_batch_assign_responsible_person_api.yaml", "order_batch_assign_tests"),
        ids=lambda case: case['case_id']
    )
    def test_batch_assign_responsible_persiont(self, api_client, db, case):
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        # 动态设置标题，方便 Allure 展示
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)