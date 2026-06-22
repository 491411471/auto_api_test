# testcases/api/order/test_query_action_audit_list.py
"""
查询操作记录接口测试
接口：/hzsx/business/order/queryActionAuditListByOrderId
方法：GET

测试流程：
1. 通过YAML的sql配置动态获取租用中的订单ID（框架自动处理）
2. 调用接口查询操作记录
3. 验证接口返回数据（基础断言）
4. 查询数据库操作记录（使用YAML的verify_sql配置）
5. 验证接口与数据库数据一致性（业务断言）
"""
import allure
import json
import pytest
from common.test_helpers import execute_test_case, replace_placeholders
from utils.data_loader import get_test_data, get_global_variables
from utils.variable_utils import validate, get_value_by_path


# 预先加载用例数据
_ALL_CASES = get_test_data("query_action_audit_list.yaml", "query_action_audit_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 query_action_audit_list.yaml")

@allure.epic("商家端")
@allure.feature("商家端-订单操作记录")
@allure.story("查询操作记录")
class TestQueryActionAuditList:
    """查询操作记录接口测试"""
    _global_vars = None
    _DATA_FILE = "data/merchant/api/order/query_action_audit_list.yaml"

    @classmethod
    def _load_global_vars(cls):
        """加载全局变量"""
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(cls._DATA_FILE)
        return cls._global_vars.copy()

    @pytest.mark.parametrize("case_data", _ALL_CASES, ids=[c['case_id'] for c in _ALL_CASES])
    @allure.description("查询订单操作记录，验证接口返回数据与数据库一致性")
    def test_query_action_audit(self, merchant_api_client, db, case_data):
        global_vars = self._load_global_vars()
        # 如果用例内部定义了 variables，合并（用例级优先级更高）
        if 'variables' in case_data and isinstance(case_data['variables'], dict):
            global_vars.update(case_data['variables'])
        
        # 执行标准测试流程（SQL处理、请求、基础断言、post_sql）
        execute_test_case(case_data, merchant_api_client, db, global_vars)
        



