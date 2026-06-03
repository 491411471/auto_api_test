import allure
import pytest
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables

_ALL_CASES = get_test_data("product_audit_query_api.yaml", "product_audit_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 product_audit_query_api.yaml")

@allure.epic("商家端")
@allure.feature("商家端-商品管理模块")
@allure.story("商品审核查询与详情")
class TestProductAuditQuery:
    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("product_audit_query_api.yaml")
        return cls._global_vars.copy()

    def test_pa_001_audit_state(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "PA_001"), None)
        if not case:
            pytest.fail("未找到用例 PA_001")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_pa_002_audit_state_and_product_status(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "PA_002"), None)
        if not case:
            pytest.fail("未找到用例 PA_002")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_pa_003_product_id(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "PA_003"), None)
        if not case:
            pytest.fail("未找到用例 PA_003")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_pa_004_product_name(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "PA_004"), None)
        if not case:
            pytest.fail("未找到用例 PA_004")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_pa_005_empty_condition(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "PA_005"), None)
        if not case:
            pytest.fail("未找到用例 PA_005")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_pa_006_on_shelf(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "PA_006"), None)
        if not case:
            pytest.fail("未找到用例 PA_006")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_pa_007_off_shelf(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "PA_007"), None)
        if not case:
            pytest.fail("未找到用例 PA_007")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_pa_008_audit_log_detail(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "PA_008"), None)
        if not case:
            pytest.fail("未找到用例 PA_008")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_pu_001_audit_log_detail(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "PU_001"), None)
        if not case:
            pytest.fail("未找到用例 PU_001")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_pu_002_audit_log_detail(self, api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "PU_002"), None)
        if not case:
            pytest.fail("未找到用例 PU_002")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)