# testcases/admin/api/merchant_management/test_shop_list_query_api.py
"""
运营端 - 商家管理 - 商家列表查询接口测试
接口：POST /hzsx/opeShop/toShopExamineListV2
覆盖场景：平台查询、店铺名称、店铺编码、续期状态、账户状态、注销状态、托管模式、清退状态、组合查询
"""
import allure
import pytest

from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables


_DATA_FILE = "data/admin/api/merchant_management/shop_list_query_api.yaml"


@allure.epic("运营端")
@allure.feature("商家管理")
@allure.story("商家列表查询")
class TestShopListQuery:
    """商家列表查询 - 14 个查询场景（参数化）"""

    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    @pytest.mark.parametrize(
        "case",
        get_test_data(_DATA_FILE, "shop_list_query_tests"),
        ids=[c["case_id"] for c in get_test_data(_DATA_FILE, "shop_list_query_tests")],
    )
    def test_shop_list_query(self, admin_api_client, db, case):
        # 1. 加载全局变量
        global_vars = self._load_global_vars()
        # 2. 合并用例级别变量（如果有）
        if "variables" in case and isinstance(case["variables"], dict):
            global_vars.update(case["variables"])
        # 3. 更新 Allure 标题
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        # 4. 执行测试（框架自动处理变量替换、API 请求、断言）
        execute_test_case(case, admin_api_client, db, global_vars)
