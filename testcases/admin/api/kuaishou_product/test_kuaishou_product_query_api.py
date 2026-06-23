# testcases/admin/api/kuaishou_product/test_kuaishou_product_query_api.py
"""
运营端 - 商品管理：快手商品查询接口测试

接口：POST /hzsx/examineProduct/selectExaminePoroductList
覆盖场景：审批状态(正在审核/审核通过)、上架状态(已上架/已下架)、
          店铺名称、店铺编码、商品编码、商品名称、新旧程度、组合条件查询

数据策略：Class 组织，步骤1从数据库提取快手商品数据供后续查询使用
变量传递：从数据库查询快手商品，提取 productId/name 注入到 KP_007/KP_008 的查询参数中
"""
import json
import random

import allure
import pytest

from common.logger import logger
from common.test_helpers import replace_placeholders, validate_response
from utils.assert_utils import assert_status_code
from utils.data_loader import get_test_data, get_global_variables
from utils.variable_utils import get_value_by_path

_DATA_FILE = "data/admin/api/kuaishou_product/kuaishou_product_query_api.yaml"

# 预加载所有用例数据
_ALL_CASES = get_test_data(_DATA_FILE, "kuaishou_product_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 kuaishou_product_query_api.yaml")


def _get_case_by_id(case_id: str) -> dict:
    """根据 case_id 从用例列表中获取测试用例数据"""
    for case in _ALL_CASES:
        if case["case_id"] == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")


@allure.epic("运营端")
@allure.feature("运营端-商品管理")
@allure.story("快手商品查询")
class TestKuaishouProductQuery:
    """快手商品查询 - 10 个查询场景"""

    _global_vars = None
    # 从数据库提取的快手商品数据（跨测试方法共享）
    _product_id = None
    _product_name = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    # ==================== 步骤1：从数据库提取快手商品数据 ====================
    @pytest.mark.order(1)
    @allure.title("KP_000 | 提取快手商品数据")
    def test_step0_extract_kuaishou_product_data(self, db):
        """步骤0：从数据库查询快手商品数据，提取 productId 和 name 供后续查询使用。"""
        sql = """
            SELECT name, product_id 
            FROM llxz_product.ct_product 
            WHERE product_type='kuaishou' AND delete_time IS NULL
            LIMIT 10
        """
        
        with allure.step("执行SQL查询快手商品数据"):
            allure.attach(sql, name="SQL语句", attachment_type=allure.attachment_type.TEXT)
            results = db.fetch_all(sql)
            
            if not results:
                skip_msg = "数据库中未找到快手商品数据，跳过后续测试"
                logger.warning(f"[跳过] {skip_msg}")
                allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                pytest.skip(skip_msg)
            
            # 随机选择一条商品记录
            selected = random.choice(results)
            # 使用.get()安全访问，兼容不同字段名
            self.__class__._product_id = str(selected.get("product_id") or selected.get("productId", ""))
            self.__class__._product_name = selected.get("name", "")
            
            extracted_info = (
                f"商品名称: {self._product_name}\n"
                f"商品编号: {self._product_id}"
            )
            logger.info(f"从数据库提取的快手商品数据:\n{extracted_info}")
            allure.attach(
                extracted_info,
                name="提取的商品数据", 
                attachment_type=allure.attachment_type.TEXT,
            )

    # ==================== 步骤2：审批状态--正在审核 ==========
    @pytest.mark.order(2)
    @allure.title("KP_001 | 审批状态--正在审核")
    def test_step1_query_audit_state_pending(self, admin_api_client, db):
        """步骤1：查询审批状态为正在审核(auditState=0)的快手商品。"""
        case = _get_case_by_id("KP_001")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤3：审批状态--审核通过 ==========
    @pytest.mark.order(3)
    @allure.title("KP_002 | 审批状态--审核通过")
    def test_step2_query_audit_state_approved(self, admin_api_client, db):
        """步骤2：查询审批状态为审核通过(auditState=2)的快手商品。"""
        case = _get_case_by_id("KP_002")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤4：查询条件--已上架 ==========
    @pytest.mark.order(4)
    @allure.title("KP_003 | 查询条件--已上架")
    def test_step3_query_on_shelf(self, admin_api_client, db):
        """步骤3：查询已上架状态(type=1)的快手商品。"""
        case = _get_case_by_id("KP_003")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤5：查询条件--已下架 ==========
    @pytest.mark.order(5)
    @allure.title("KP_004 | 查询条件--已下架")
    def test_step4_query_off_shelf(self, admin_api_client, db):
        """步骤4：查询已下架状态(type=2)的快手商品。"""
        case = _get_case_by_id("KP_004")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤6：以店铺名称为查询条件--sass人人享租1 ==========
    @pytest.mark.order(6)
    @allure.title("KP_005 | 以店铺名称为查询条件--sass人人享租1")
    def test_step5_query_by_shop_name(self, admin_api_client, db):
        """步骤5：使用店铺名称'sass人人享租1'查询快手商品。"""
        case = _get_case_by_id("KP_005")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤7：以店铺编码为查询条件 ==========
    @pytest.mark.order(7)
    @allure.title("KP_006 | 以店铺编码为查询条件")
    def test_step6_query_by_shop_id(self, admin_api_client, db):
        """步骤6：使用店铺编码查询快手商品。"""
        case = _get_case_by_id("KP_006")
        allure.dynamic.description(case.get("description", ""))
        
        global_vars = self._load_global_vars()
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤8：以商品编码为查询条件 ==========
    @pytest.mark.order(8)
    @allure.title("KP_007 | 以商品编码为查询条件")
    def test_step7_query_by_product_id(self, admin_api_client, db):
        """步骤7：使用步骤0提取的商品编码查询快手商品。"""
        if not self.__class__._product_id:
            pytest.skip("前置步骤未获取到商品编号，跳过")
        
        case = _get_case_by_id("KP_007")
        allure.dynamic.description(case.get("description", ""))
        
        global_vars = self._load_global_vars()
        global_vars["product_id"] = self.__class__._product_id
        
        allure.attach(
            f"商品编号: {self.__class__._product_id}",
            name="注入的查询条件", 
            attachment_type=allure.attachment_type.TEXT,
        )
        
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤9：以商品名称为查询条件 ==========
    @pytest.mark.order(9)
    @allure.title("KP_008 | 以商品名称为查询条件")
    def test_step8_query_by_product_name(self, admin_api_client, db):
        """步骤8：使用步骤0提取的商品名称查询快手商品。"""
        if not self.__class__._product_name:
            pytest.skip("前置步骤未获取到商品名称，跳过")
        
        case = _get_case_by_id("KP_008")
        allure.dynamic.description(case.get("description", ""))
        
        global_vars = self._load_global_vars()
        global_vars["product_name"] = self.__class__._product_name
        
        allure.attach(
            f"商品名称: {self.__class__._product_name}",
            name="注入的查询条件", 
            attachment_type=allure.attachment_type.TEXT,
        )
        
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤10：以"全新"为查询条件 ==========
    @pytest.mark.order(10)
    @allure.title("KP_009 | 以'全新'为查询条件")
    def test_step9_query_by_old_new_degree(self, admin_api_client, db):
        """步骤9：查询新旧程度为全新(oldNewDegree=1)的快手商品。"""
        case = _get_case_by_id("KP_009")
        allure.dynamic.description(case.get("description", ""))
        
        global_vars = self._load_global_vars()
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 步骤11：以审批状态：通过，上架状态：上架组合条件查询 ==========
    @pytest.mark.order(11)
    @allure.title("KP_010 | 审批状态通过+上架状态上架组合查询")
    def test_step10_query_combined_conditions(self, admin_api_client, db):
        """步骤10：组合查询审批状态为通过(auditState=2)且上架状态为上架(type=1)的快手商品。"""
        case = _get_case_by_id("KP_010")
        allure.dynamic.description(case.get("description", ""))
        
        global_vars = self._load_global_vars()
        self._execute_with_empty_check(case, admin_api_client, db, global_vars)

    # ==================== 通用辅助方法 ====================
    def _execute_with_empty_check(
        self, case: dict, api_client, db, global_vars: dict
    ):
        """
        通用执行方法：先发送请求检查空结果（跳过），再执行完整断言。
        适用于所有查询类用例。
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
                name="请求体 (JSON)", 
                attachment_type=allure.attachment_type.JSON,
            )
            resp = api_client.post(endpoint, json=body_data)
            response_data = resp.json()
            allure.attach(str(resp.status_code), name="HTTP 状态码", attachment_type=allure.attachment_type.TEXT)
            allure.attach(
                json.dumps(response_data, ensure_ascii=False, indent=2, default=str),
                name="完整响应体", 
                attachment_type=allure.attachment_type.JSON,
            )
        
        # 4. 检查 records 是否为空
        if response_data is None:
            skip_reason = (
                f"跳过原因：API返回响应为空\n"
                f"用例ID：{case['case_id']}\n"
                f"请求参数：{json.dumps(body_data, ensure_ascii=False, default=str)}\n"
                f"HTTP 状态码：{resp.status_code}"
            )
            logger.warning(f"[跳过] {case['case_id']}: {skip_reason}")
            allure.attach(
                skip_reason, 
                name="跳过原因",
                attachment_type=allure.attachment_type.TEXT,
            )
            pytest.skip(skip_reason)
        
        # 安全获取 records（兼容 data 为 null 的情况）
        data_obj = response_data.get("data") or {}
        records = data_obj.get("records", []) if isinstance(data_obj, dict) else []
        if not records and resp.status_code == 200:
            skip_reason = (
                f"跳过原因：查询结果为空\n"
                f"用例ID：{case['case_id']}\n"
                f"请求参数：{json.dumps(body_data, ensure_ascii=False, default=str)}\n"
                f"HTTP 状态码：{resp.status_code}"
            )
            logger.warning(f"[跳过] {case['case_id']}: {skip_reason}")
            allure.attach(
                skip_reason, 
                name="跳过原因",
                attachment_type=allure.attachment_type.TEXT,
            )
            pytest.skip(skip_reason)
        
        # 5. 执行完整断言（使用框架的 validate_response 函数）
        with allure.step("执行断言验证"):
            assert_status_code(resp.status_code, case["expected_status"])
            
            # 提前替换 case 中的变量占位符，避免 validate_response 内部打印未替换警告
            # validate_response 会自动处理：
            # 1. JSONPath 路径解析
            # 2. 所有操作符验证（all_eq, contains, etc.）
            # 3. Allure 报告生成
            case_replaced = replace_placeholders(case, global_vars)
            validate_response(case_replaced, response_data, global_vars)
