import allure
import pytest
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables

_ALL_CASES = get_test_data("order_pay_detail_api.yaml", "order_pay_detail_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 order_pay_detail_api.yaml")

@allure.feature("商家端-订单模块")
@allure.story("订单支付详情部分字段验证")
class TestOrderPayDetailApi:
    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("order_pay_detail_api.yaml")
        return cls._global_vars.copy()

    def test_pd_001_total_rent(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "PD_001"), None)
        if not case:
            pytest.fail("未找到用例 PD_001")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_pd_002_paid_rent(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "PD_002"), None)
        if not case:
            pytest.fail("未找到用例 PD_002")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_pd_003_unpaid_rent(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "PD_003"), None)
        if not case:
            pytest.fail("未找到用例 PD_003")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    # def test_pd_004_real_pay_equals_has_pay(self, api_client, db):
    #     case = next((c for c in _ALL_CASES if c['case_id'] == "PD_004"), None)
    #     if not case:
    #         pytest.fail("未找到用例 PD_004")
    #     global_vars = self._load_global_vars()
    #     if 'variables' in case and isinstance(case['variables'], dict):
    #         global_vars.update(case['variables'])
    #     allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
    #     execute_test_case(case, api_client, db, global_vars)