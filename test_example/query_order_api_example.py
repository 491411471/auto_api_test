# testcases/api/order/test_query_order_api_example.py
"""
订单查询接口测试 - 使用 BaseAPITest 基类的示例

这个文件展示了如何使用新的测试基类简化测试代码
"""
from datetime import datetime, timedelta
import allure
import pytest
from testcases.base_test import BaseAPITest


@allure.feature("商家端-订单模块")
@allure.story("订单查询")
class TestOrderQueryExample(BaseAPITest):
    """
    订单查询测试类
    使用 BaseAPITest 基类后，测试代码大大简化：
    1. 不需要手动加载全局变量
    2. 不需要手动合并用例变量
    3. 变量管理更安全（使用 VariableManager）
    """
    
    # 指定测试数据文件
    yaml_file = "query_order_api.yaml"
    data_key = "order_query_tests"
    
    @pytest.mark.smoke
    @pytest.mark.parametrize(
        "case",
        BaseAPITest.load_test_cases("query_order_api.yaml", "order_query_tests"),
        ids=BaseAPITest.load_case_ids("query_order_api.yaml", "order_query_tests")
    )
    def test_order_query(self, api_client, db, case):
        """
        订单查询测试
        """
        # 1. 设置 Allure 标题
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        
        # 2. 添加动态日期变量（仅对需要日期的用例）
        if 'start_date' not in self.var_manager:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            self.add_dynamic_vars({
                "start_date": (today - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"),
                "end_date": today.strftime("%Y-%m-%d %H:%M:%S"),
                "start_date_iso": (today - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00.000Z"),
                "end_date_iso": datetime.now().replace(hour=16, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            })
        
        # 3. 执行测试用例（基类处理所有变量管理逻辑）
        self.run_case(case, api_client, db)


# ==================== 对比：原来的实现方式 ====================
# class TestOrderQueryOld:
#     _global_vars = None
#
#     @classmethod
#     def _load_global_vars(cls):
#         if cls._global_vars is None:
#             cls._global_vars = get_global_variables("query_order_api.yaml")
#         return cls._global_vars.copy()
#
#     @staticmethod
#     def _add_dynamic_date_vars(global_vars: dict) -> dict:
#         today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
#         start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
#         end_date = today.strftime("%Y-%m-%d %H:%M:%S")
#         start_date_iso = (today - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00.000Z")
#         end_date_iso = datetime.now().replace(hour=16, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.000Z")
#
#         global_vars.update({
#             "start_date": start_date,
#             "end_date": end_date,
#             "start_date_iso": start_date_iso,
#             "end_date_iso": end_date_iso,
#         })
#         return global_vars
#
#     @pytest.mark.smoke
#     @pytest.mark.parametrize(
#         "case",
#         get_test_data("query_order_api.yaml", "order_query_tests"),
#         ids=[case['case_id'] for case in get_test_data("query_order_api.yaml", "order_query_tests")]
#     )
#     def test_order_query(self, api_client, db, case):
#         # 1. 加载全局变量
#         global_vars = self._load_global_vars()
#
#         # 2. 合并用例级别变量（如果有）
#         if 'variables' in case and isinstance(case['variables'], dict):
#             global_vars.update(case['variables'])
#
#         # 3. 动态添加日期变量（关键步骤）
#         global_vars = self._add_dynamic_date_vars(global_vars)
#
#         # 4. 更新 allure 标题
#         allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
#
#         # 5. 执行测试（内部会调用 replace_variables 替换占位符）
#         execute_test_case(case, api_client, db, global_vars)
