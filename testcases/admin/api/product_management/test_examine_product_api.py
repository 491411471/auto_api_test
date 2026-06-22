# testcases/admin/api/product_management/test_examine_product_api.py
"""
运营端 - 商品管理：商品审核-商品查询接口测试

接口：POST /hzsx/examineProduct/selectExaminePoroductList
覆盖场景：空条件查询、商品名称、商品编码、店铺编码、店铺名称、
          创建时间范围、库存状态(7天内)、库存状态(已过期)、已上架、已下架

数据策略：Class 组织，步骤1提取商品数据供后续查询使用
变量传递：EP_001 从响应中随机选取一条商品记录，提取 name/productId/shopId/shopName
          注入到 EP_002~EP_005 的查询参数中
"""
import json
import random
from datetime import datetime, timedelta

import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case, replace_placeholders
from utils.assert_utils import assert_status_code
from utils.data_loader import get_test_data, get_global_variables
from utils.variable_utils import validate, get_value_by_path


_DATA_FILE = "data/admin/api/product_management/examine_product_api.yaml"

# 预加载所有用例数据
_ALL_CASES = get_test_data(_DATA_FILE, "examine_product_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 examine_product_api.yaml")


def _get_case_by_id(case_id: str) -> dict:
    """根据 case_id 从用例列表中获取测试用例数据"""
    for case in _ALL_CASES:
        if case["case_id"] == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")


@allure.epic("运营端")
@allure.feature("运营端-商品管理")
@allure.story("商品审核-商品查询")
class TestExamineProductQuery:
    """商品审核-商品查询 - 10 个查询场景"""

    _global_vars = None
    # 步骤1提取的商品数据（跨测试方法共享）
    _product_name = None
    _product_id = None
    _shop_id = None
    _shop_name = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    @staticmethod
    def _add_dynamic_date_vars(global_vars: dict) -> dict:
        """动态计算创建时间范围并注入变量（用于 EP_006 创建时间查询场景）：
        create_date_start = 8 天前（ISO 格式）
        create_date_end   = 1 天前（ISO 格式）
        create_time_start = 7 天前（YYYY-MM-DD HH:MM:SS）
        create_time_end   = 当天 23:59:59
        """
        now = datetime.now()
        # createDate（ISO 格式，与前端传参一致）
        global_vars["create_date_start"] = (now + timedelta(days=-8)).strftime("%Y-%m-%dT16:00:00.000Z")
        global_vars["create_date_end"] = (now + timedelta(days=-1)).strftime("%Y-%m-%dT16:00:00.000Z")
        # creatTime（YYYY-MM-DD HH:MM:SS 格式）
        global_vars["create_time_start"] = (now + timedelta(days=-7)).strftime("%Y-%m-%d 00:00:00")
        global_vars["create_time_end"] = now.strftime("%Y-%m-%d 23:59:59")
        return global_vars

    # ==================== 步骤1：空条件查询待审核商品 ====================
    @pytest.mark.order(1)
    @allure.title("EP_001 | 空条件查询待审核商品")
    def test_step1_query_pending_products(self, admin_api_client, db):
        """步骤1：空条件查询待审核商品列表，随机选取一条记录提取商品数据供后续查询。"""
        case = _get_case_by_id("EP_001")
        allure.dynamic.description(case.get("description", ""))

        # 1. 加载并合并变量
        global_vars = self._load_global_vars()
        if "variables" in case and isinstance(case["variables"], dict):
            global_vars.update(case["variables"])

        # 2. 变量替换
        case_replaced = replace_placeholders(case, global_vars)

        # 3. 发送查询请求
        endpoint = case_replaced.get("endpoint", "")
        body_data = case_replaced.get("json", {})
        with allure.step("发送查询请求（空条件查询待审核商品）"):
            allure.attach(
                json.dumps(body_data, ensure_ascii=False, indent=2, default=str),
                name="请求体 (JSON)", attachment_type=allure.attachment_type.JSON,
            )
            resp = admin_api_client.post(endpoint, json=body_data)
            response_data = resp.json()
            allure.attach(
                json.dumps(response_data, ensure_ascii=False, indent=2, default=str),
                name="完整响应体", attachment_type=allure.attachment_type.JSON,
            )

        # 4. 基础断言
        with allure.step("执行基础断言"):
            assert_status_code(resp.status_code, case["expected_status"])
            for check in case["validate_data"]:
                path = check["path"].lstrip("$").lstrip(".")
                actual = get_value_by_path(response_data, path)
                validate(actual, check["operator"], check.get("value"), path)

        # 5. 检查 records 是否为空，无数据则跳过
        records = response_data.get("data", {}).get("records", [])
        if not records:
            skip_msg = "未查询到待审核商品，跳过后续测试"
            logger.warning(f"[跳过] {skip_msg}")
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        # 6. 随机选取一条商品记录，提取关键字段
        selected = random.choice(records)
        self.__class__._product_name = selected["name"]
        self.__class__._product_id = selected["productId"]
        self.__class__._shop_id = selected["shopId"]
        self.__class__._shop_name = selected["shopName"]

        extracted_info = (
            f"商品名称: {self._product_name}\n"
            f"商品编号: {self._product_id}\n"
            f"店铺名称: {self._shop_name}\n"
            f"店铺编号: {self._shop_id}"
        )
        print("extracted_info", extracted_info)
        logger.info(f"随机选取的商品数据:\n{extracted_info}")
        allure.attach(
            extracted_info,
            name="提取的商品数据", attachment_type=allure.attachment_type.TEXT,
        )

    # ==================== 步骤2：以商品名称为查询条件 ====================
    @pytest.mark.order(2)
    @allure.title("EP_002 | 以商品名称为查询条件")
    def test_step2_query_by_product_name(self, admin_api_client, db):
        """步骤2：使用步骤1提取的商品名称查询，验证返回记录的商品名称均一致。"""
        if not self.__class__._product_name:
            pytest.skip("前置查询未获取到商品名称，跳过")

        case = _get_case_by_id("EP_002")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        global_vars["product_name"] = self.__class__._product_name

        allure.attach(
            f"商品名称: {self.__class__._product_name}",
            name="注入的查询条件", attachment_type=allure.attachment_type.TEXT,
        )

        # 空结果跳过：手动发送请求检查
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤3：以商品编码为查询条件 ====================
    @pytest.mark.order(3)
    @allure.title("EP_003 | 以商品编码为查询条件")
    def test_step3_query_by_product_id(self, admin_api_client, db):
        """步骤3：使用步骤1提取的商品编码查询，验证返回记录的商品编码均一致。"""
        if not self.__class__._product_id:
            pytest.skip("前置查询未获取到商品编号，跳过")

        case = _get_case_by_id("EP_003")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        global_vars["product_id"] = self.__class__._product_id

        allure.attach(
            f"商品编号: {self.__class__._product_id}",
            name="注入的查询条件", attachment_type=allure.attachment_type.TEXT,
        )

        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤4：以店铺编码为查询条件 ====================
    @pytest.mark.order(4)
    @allure.title("EP_004 | 以店铺编码为查询条件")
    def test_step4_query_by_shop_id(self, admin_api_client, db):
        """步骤4：使用步骤1提取的店铺编码查询，验证返回记录的店铺编码均一致。"""
        if not self.__class__._shop_id:
            pytest.skip("前置查询未获取到店铺编号，跳过")

        case = _get_case_by_id("EP_004")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        global_vars["shop_id"] = self.__class__._shop_id

        allure.attach(
            f"店铺编号: {self.__class__._shop_id}",
            name="注入的查询条件", attachment_type=allure.attachment_type.TEXT,
        )

        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤5：以店铺名称为查询条件 ====================
    @pytest.mark.order(5)
    @allure.title("EP_005 | 以店铺名称为查询条件")
    def test_step5_query_by_shop_name(self, admin_api_client, db):
        """步骤5：使用步骤1提取的店铺名称查询，验证返回记录的店铺名称均一致。"""
        if not self.__class__._shop_name:
            pytest.skip("前置查询未获取到店铺名称，跳过")

        case = _get_case_by_id("EP_005")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        global_vars["shop_name"] = self.__class__._shop_name

        allure.attach(
            f"店铺名称: {self.__class__._shop_name}",
            name="注入的查询条件", attachment_type=allure.attachment_type.TEXT,
        )

        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤6：以创建时间为查询条件 ====================
    @pytest.mark.order(6)
    @allure.title("EP_006 | 以创建时间为查询条件")
    def test_step6_query_by_create_time(self, admin_api_client, db):
        """步骤6：使用创建时间范围查询，验证返回的商品创建时间均在查询范围内。"""
        case = _get_case_by_id("EP_006")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        global_vars = self._add_dynamic_date_vars(global_vars)

        allure.attach(
            json.dumps(
                {k: global_vars[k] for k in
                 ["create_date_start", "create_date_end", "create_time_start", "create_time_end"]},
                ensure_ascii=False, indent=2,
            ),
            name="注入的时间范围变量", attachment_type=allure.attachment_type.JSON,
        )

        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤7：以库存状态(7天内)为查询条件 ====================
    @pytest.mark.order(7)
    @allure.title("EP_007 | 以库存状态(7天内)为查询条件")
    def test_step7_query_by_inventory_will_expire(self, admin_api_client, db):
        """步骤7：查询库存将在7天内过期的商品，验证返回商品的库存剩余天数均小于7。"""
        case = _get_case_by_id("EP_007")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤8：以库存状态(已过期)为查询条件 ====================
    @pytest.mark.order(8)
    @allure.title("EP_008 | 以库存状态(已过期)为查询条件")
    def test_step8_query_by_inventory_expired(self, admin_api_client, db):
        """步骤8：查询库存已过期的商品，验证返回商品的库存剩余天数均小于0。"""
        case = _get_case_by_id("EP_008")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤9：以已上架状态为查询条件 ====================
    @pytest.mark.order(9)
    @allure.title("EP_009 | 以已上架状态为查询条件")
    def test_step9_query_by_on_shelf(self, admin_api_client, db):
        """步骤9：查询已上架商品，验证返回商品的上架状态均为已上架。"""
        case = _get_case_by_id("EP_009")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤10：以已下架为查询条件 ====================
    @pytest.mark.order(10)
    @allure.title("EP_010 | 以已下架为查询条件")
    def test_step10_query_by_off_shelf(self, admin_api_client, db):
        """步骤10：查询已下架商品，验证返回商品的上架状态均为已下架。"""
        case = _get_case_by_id("EP_010")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 通用辅助方法 ====================
    def _execute_with_empty_check(
        self, case: dict, api_client, db, global_vars: dict
    ):
        """
        通用执行方法：先发送请求检查空结果（跳过），再执行完整断言。
        适用于步骤2-10的查询类用例。
        """
        # 1. 合并变量
        if "variables" in case and isinstance(case["variables"], dict):
            global_vars.update(case["variables"])

        # 2. 变量替换
        case_replaced = replace_placeholders(case, global_vars)

        # 3. 发送请求检查空结果
        endpoint = case_replaced.get("endpoint", "")
        body_data = case_replaced.get("json", {})
        with allure.step("发送查询请求"):
            allure.attach(
                json.dumps(body_data, ensure_ascii=False, indent=2, default=str),
                name="请求体 (JSON)", attachment_type=allure.attachment_type.JSON,
            )
            resp = api_client.post(endpoint, json=body_data)
            response_data = resp.json()
            allure.attach(str(resp.status_code), name="HTTP 状态码", attachment_type=allure.attachment_type.TEXT)
            allure.attach(
                json.dumps(response_data, ensure_ascii=False, indent=2, default=str),
                name="完整响应体", attachment_type=allure.attachment_type.JSON,
            )

        # 4. 检查 records 是否为空
        records = response_data.get("data", {}).get("records", [])
        if not records and resp.status_code == 200:
            skip_reason = (
                f"跳过原因：查询结果为空\n"
                f"用例ID：{case['case_id']}\n"
                f"请求参数：{json.dumps(body_data, ensure_ascii=False, default=str)}\n"
                f"HTTP 状态码：{resp.status_code}"
            )
            logger.warning(f"[跳过] {case['case_id']}: {skip_reason}")
            allure.attach(
                skip_reason, name="跳过原因",
                attachment_type=allure.attachment_type.TEXT,
            )
            pytest.skip(skip_reason)

        # 5. 执行完整断言
        with allure.step("执行断言验证"):
            assert_status_code(resp.status_code, case["expected_status"])
            from common.test_helpers import validate_response
            validate_response(case, response_data, global_vars)
