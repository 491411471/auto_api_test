import allure
import pytest
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables
from utils.product_utils import gen_chinese_phone, gen_detailed_street_address, generate_chinese_name

_ALL_CASES = get_test_data("save_give_back_address_api.yaml", "save_give_back_address_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 save_give_back_address_api.yaml")
@allure.epic("商家端")
@allure.feature("商家端-商品管理模块")
@allure.story("归还地址")
class TestProductAuditQuery:
    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("save_give_back_address_api.yaml")
        return cls._global_vars.copy()

    def setup_method(self):
        """每个测试方法前执行，生成新的随机数据"""
        self._dynamic_vars = {
            "random_name": generate_chinese_name(),
            "random_street": gen_detailed_street_address(),
            "random_telephone": gen_chinese_phone()
        }

    def test_SBA_001_audit_state(self, merchant_api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "SBA_001"), None)
        if not case:
            pytest.fail("未找到用例 SBA_001")
        global_vars = self._load_global_vars()
        global_vars.update(self._dynamic_vars)  # 使用当前测试的动态变量
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)

    def test_SBA_002_audit_state(self, merchant_api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "SBA_002"), None)
        if not case:
            pytest.fail("未找到用例 SBA_002")
        global_vars = self._load_global_vars()
        global_vars.update(self._dynamic_vars)  # 使用当前测试的动态变量
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)

    def test_SBA_003_audit_state(self, merchant_api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "SBA_003"), None)
        if not case:
            pytest.fail("未找到用例 SBA_003")
        global_vars = self._load_global_vars()
        global_vars.update(self._dynamic_vars)  # 使用当前测试的动态变量
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)


    def test_SBA_004_audit_state(self, merchant_api_client, db):
        case = next((c for c in _ALL_CASES if c['case_id'] == "SBA_004"), None)
        if not case:
            pytest.fail("未找到用例 SBA_004")
        global_vars = self._load_global_vars()
        global_vars.update(self._dynamic_vars)  # 使用当前测试的动态变量
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)