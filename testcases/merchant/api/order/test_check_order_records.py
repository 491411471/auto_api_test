import allure
import pytest
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables

# 预先加载所有用例数据（只加载一次）
_DATA_FILE = "data/merchant/api/order/check_order_records_api.yaml"
_ALL_CASES = get_test_data(_DATA_FILE, "order_records_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 check_order_records_api.yaml")

@allure.feature("商家端-订单模块")
@allure.story("订单记录查询")
class TestOrderRecordsApi:
    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("check_order_records_api.yaml")
        return cls._global_vars.copy()

    def test_or_001(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "OR_001"), None) # 如果未找到，case 为 None
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_or_002(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "OR_002"), None) # 如果未找到，case 为 None
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_or_003(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "OR_003"), None) # 如果未找到，case 为 None
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_or_004(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "OR_004"), None) # 如果未找到，case 为 None
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_or_005(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "OR_005"), None) # 如果未找到，case 为 None
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    # def test_or_006(self, api_client, db):
    #     case = get_case_by_id("OR_006")
    #     global_vars = self._load_global_vars()
    #     if 'variables' in case and isinstance(case['variables'], dict):
    #         global_vars.update(case['variables'])
    #     allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
    #     execute_test_case(case, api_client, db, global_vars)