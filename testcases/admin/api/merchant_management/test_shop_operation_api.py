# testcases/admin/api/merchant_management/test_shop_operation_api.py
"""
运营端 - 商家管理 - 商家列表操作接口测试
接口：
  - POST /hzsx/opeShop/aloneUpdateShopTelAboutInfo（修改通讯信息）
  - GET  /hzsx/user/updateShopMainTel（修改店铺手机号）
  - POST /hzsx/busShop/updateShopStepOne（修改基础信息）
  - POST /hzsx/busShop/updateShopStepTwoZfb（修改结算账户）
  - POST /hzsx/busShop/auditShopStep（提交审核）
覆盖场景：修改客服电话、联系邮箱、支付宝账号、店铺手机号、基础信息、结算账户、提交审核
"""
import random

import allure
import pytest

from common.test_helpers import execute_test_case
from utils.data_generator import generate_random_value
from utils.data_loader import get_test_data, get_global_variables


_DATA_FILE = "data/admin/api/merchant_management/shop_operation_api.yaml"

# 用例 1-3 的 content_str 生成类型映射
_CONTENT_GEN_MAP = {
    "SOP_001": "phone",      # 客服电话 → 随机手机号
    "SOP_002": "email",      # 联系邮箱 → 随机邮箱
    "SOP_003": "alipay",     # 支付宝账号 → 随机支付宝号
}


@allure.epic("运营端")
@allure.feature("商家管理")
@allure.story("商家列表操作")
class TestShopOperation:
    """商家列表操作 - 修改通讯信息 + 修改店铺信息 + 提交审核"""

    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    # ==================== 用例 1-3：修改通讯信息（参数化） ====================
    _tel_cases = get_test_data(_DATA_FILE, "update_tel_info_tests")

    @pytest.mark.parametrize(
        "case",
        _tel_cases,
        ids=[c["case_id"] for c in _tel_cases],
    )
    def test_update_tel_info(self, admin_api_client, db, case):
        """修改通讯信息：客服电话 / 联系邮箱 / 支付宝账号"""
        global_vars = self._load_global_vars()
        # 根据 case_id 动态生成 content_str
        gen_type = _CONTENT_GEN_MAP[case["case_id"]]
        global_vars["content_str"] = generate_random_value(gen_type)
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== 用例 4：修改店铺手机号 ====================
    def test_update_shop_main_tel(self, admin_api_client, db):
        """修改店铺信息--手机号"""
        all_cases = get_test_data(_DATA_FILE, "shop_update_tests")
        case = next(c for c in all_cases if c["case_id"] == "SOP_004")
        global_vars = self._load_global_vars()
        global_vars["new_mobile"] = generate_random_value("phone")
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== 用例 5：修改店铺基础信息 ====================
    def test_update_shop_step_one(self, admin_api_client, db):
        """修改店铺信息--基础信息"""
        all_cases = get_test_data(_DATA_FILE, "shop_update_tests")
        case = next(c for c in all_cases if c["case_id"] == "SOP_005")
        global_vars = self._load_global_vars()
        global_vars["description"] = generate_random_value("uuid")
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== 用例 6：修改结算账户 ====================
    def test_update_shop_step_two_zfb(self, admin_api_client, db):
        """修改店铺信息--结算账户修改"""
        all_cases = get_test_data(_DATA_FILE, "shop_update_tests")
        case = next(c for c in all_cases if c["case_id"] == "SOP_006")
        global_vars = self._load_global_vars()
        global_vars["zfb_name"] = generate_random_value("str")
        global_vars["zfb_code"] = generate_random_value("alipay")
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== 用例 7：提交店铺修改审核 ====================
    def test_audit_shop_step(self, admin_api_client, db):
        """提交店铺修改信息"""
        all_cases = get_test_data(_DATA_FILE, "shop_update_tests")
        case = next(c for c in all_cases if c["case_id"] == "SOP_007")
        global_vars = self._load_global_vars()
        # isLocked 在 0 和 1 之间切换
        global_vars["is_locked"] = random.choice([0, 1])
        # channelId 在 "011","008","012" 之间切换
        global_vars["channel_id"] = random.choice(["011", "008", "012"])
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)
