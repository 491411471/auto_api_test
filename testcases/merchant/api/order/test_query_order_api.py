# testcases/api/order/test_query_order_api.py
import allure
import pytest
from datetime import datetime, timedelta
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables
@allure.epic("商家端")
@allure.feature("商家端-订单查询")
@allure.story("订单查询")
class TestOrderQuery:
    _global_vars = None
    _DATA_FILE = "data/merchant/api/order/query_order_api.yaml"
    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("query_order_api.yaml")
        return cls._global_vars.copy()

    @staticmethod
    def _add_dynamic_date_vars(global_vars: dict) -> dict:
        """动态计算起租日期范围并更新到全局变量中"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        end_date = today.strftime("%Y-%m-%d %H:%M:%S")
        start_date_iso = (today - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00.000Z")
        # 第二个元素为当天16:00:00（与原示例保持一致）
        end_date_iso = datetime.now().replace(hour=16, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        global_vars.update({
            "start_date": start_date,
            "end_date": end_date,
            "start_date_iso": start_date_iso,
            "end_date_iso": end_date_iso,
        })
        return global_vars

    @pytest.mark.smoke
    @pytest.mark.parametrize(
        "case",
        get_test_data("query_order_api.yaml", "order_query_tests"),
        ids=[case['case_id'] for case in get_test_data("query_order_api.yaml", "order_query_tests")]
    )
    def test_order_query(self, api_client, db, case):
        # 1. 加载全局变量
        global_vars = self._load_global_vars()

        # 2. 合并用例级别变量（如果有）
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])

        # 3. 动态添加日期变量（关键步骤）
        global_vars = self._add_dynamic_date_vars(global_vars)

        # 4. 更新 allure 标题
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")

        # 5. 执行测试（内部会调用 replace_variables 替换占位符）
        execute_test_case(case, api_client, db, global_vars)