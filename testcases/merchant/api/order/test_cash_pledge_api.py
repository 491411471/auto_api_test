import allure
import pytest
import random
import string
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables

# 预先加载所有用例数据（只加载一次）
# 使用项目根目录相对路径，精确匹配 data/merchant/api/order/ 目录结构
_DATA_FILE = "data/merchant/api/order/order_cash_pledge_api.yaml"
_ALL_CASES = get_test_data(_DATA_FILE, "cash_pledge_tests")
if not _ALL_CASES:
    raise RuntimeError(f"无法加载 YAML 数据，请检查文件路径 {_DATA_FILE}")

def get_case_by_id(case_id: str):
    for case in _ALL_CASES:
        if case['case_id'] == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")

@allure.feature("商家端-订单模块")
@allure.story("订单详情之订单押金")
class TestOrderOperatorApi:
    _global_vars = None
    # 用于跨用例共享的数据
    shared_order_id = None
    shared_remark = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    def test_cp_001(self, api_client, db):
        case = get_case_by_id("CP_001")
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_cp_002(self, api_client, db):
        case = get_case_by_id("CP_002")
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_cp_003(self, api_client, db):
        case = get_case_by_id("CP_003")
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_cp_004(self, api_client, db):
        case = get_case_by_id("CP_004")
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)