# testcases/merchant/api/product/test_product_shelf_toggle.py
"""
商家端 - 商品上下架流程测试

用例1: 单个商品下架流程
  - 步骤1: 查询已上架商品（type=1），提取 productId
  - 步骤2: 下架商品（updateProductInfo, type=2）
  - 步骤3: 验证商品已下架（查询type=2列表应包含该商品）

用例2: 单个商品上架流程
  - 步骤1: 查询已下架商品（type=2），提取 productId
  - 步骤2: 上架商品（updateProductInfo, type=1）
  - 步骤3: 验证商品已上架（查询type=1列表应包含该商品）
"""
import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case, replace_placeholders
from utils.data_loader import get_test_data, get_global_variables

_DATA_FILE = "data/merchant/api/product/product_shelf_toggle_api.yaml"


# ==================== 用例1: 商品下架流程 ====================
@allure.epic("商家端")
@allure.feature("商家端-商品管理模块")
@allure.story("单个商品下架流程")
class TestProductOffShelf:
    """商品下架流程：查询已上架商品 → 下架 → 验证已下架"""

    _global_vars = None
    _product_id = None
    _id = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("product_shelf_toggle_api.yaml")
        return cls._global_vars.copy()

    @pytest.mark.order(1)
    @allure.title("MOFF_001 - 查询已上架商品")
    def test_step1_query_listed_products(self, merchant_api_client, db, admin_api_client):
        """查询已上架商品列表（type=1），提取第一条记录的 productId 供下架使用"""
        cases = get_test_data(_DATA_FILE, "product_off_shelf_tests")
        case = cases[0]
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        # 使用 execute_test_case 执行查询，利用框架的断言验证
        execute_test_case(case, merchant_api_client, db, global_vars)

        # 再发一次请求提取 productId（参数相同，结果一致）
        body = replace_placeholders(case["json"], global_vars)
        resp = merchant_api_client.post(case["endpoint"], json=body)
        resp_json = resp.json()
        records = resp_json.get("data", {}).get("records", [])

        if not records:
            pytest.skip("已上架商品列表为空，无法获取 productId 进行下架测试")

        self.__class__._product_id = str(records[0]["productId"])
        self.__class__._id = str(records[0]["id"])
        allure.attach(
            f"product_id = {self._product_id}\n商品名称: {records[0].get('name', '')}",
            name="提取的商品ID",
            attachment_type=allure.attachment_type.TEXT,
        )
        logger.info(f"MOFF_001 提取 productId={self._product_id}, 商品: {records[0].get('name', '')}")

    @pytest.mark.order(2)
    @allure.title("MOFF_002 - 下架商品")
    def test_step2_off_shelf_product(self, merchant_api_client, db):
        """使用步骤1提取的 productId 调用下架接口（type=2）"""
        cases = get_test_data(_DATA_FILE, "product_off_shelf_tests")
        case = cases[1]
        global_vars = self._load_global_vars()

        if not self._product_id:
            pytest.skip("步骤1未获取到 productId，跳过下架操作")

        global_vars["product_id"] = self._product_id
        allure.dynamic.title(f"{case['case_id']} | {case['title']} (productId={self._product_id})")
        execute_test_case(case, merchant_api_client, db, global_vars)
        logger.info(f"[MOFF_002] 下架商品成功 productId={self._product_id}")

    @pytest.mark.order(3)
    @allure.title("MOFF_003 - 验证商品已下架")
    def test_step3_verify_off_shelf(self, merchant_api_client, db):
        """查询type=2的已下架商品列表，验证该商品出现在下架列表中"""
        cases = get_test_data(_DATA_FILE, "product_off_shelf_tests")
        case = cases[2]
        global_vars = self._load_global_vars()

        if not self._product_id:
            pytest.skip("步骤1未获取到 productId，跳过验证")

        global_vars["product_id"] = self._product_id
        allure.dynamic.title(f"{case['case_id']} | {case['title']} (productId={self._product_id})")

        # 执行框架断言（验证接口响应成功）
        execute_test_case(case, merchant_api_client, db, global_vars)

        # 补充断言：验证该商品在已下架列表中
        with allure.step(f"验证 productId={self._product_id} 在已下架商品列表中"):
            body = replace_placeholders(case["json"], global_vars)
            resp = merchant_api_client.post(case["endpoint"], json=body)
            resp_json = resp.json()
            records = resp_json.get("data", {}).get("records", [])
            product_ids = [str(r.get("productId", "")) for r in records]

            allure.attach(
                f"查询到的已下架商品 productId 列表: {product_ids}\n"
                f"目标 productId: {self._product_id}",
                name="验证数据",
                attachment_type=allure.attachment_type.TEXT,
            )

            assert self._product_id in product_ids, (
                f"商品 {self._product_id} 未出现在已下架列表中，下架未生效"
            )
            logger.info(f"[MOFF_003] 验证通过: 商品 {self._product_id} 已在已下架列表中")

    @pytest.mark.order(4)
    @allure.title("MOFF_004 - 运营端审核通过下架商品 前置：验证商品已下架")
    def test_step4_audit_off_shelf(self, admin_api_client, db):
        cases = get_test_data(_DATA_FILE, "product_off_shelf_tests")
        case = cases[3]  # MOFF_004
        global_vars = self._load_global_vars()

        if not self._product_id:
            pytest.skip("步骤1未获取到 productId，跳过审核下架")

        global_vars["product_id"] = self._product_id
        global_vars["id"] = self._id
        allure.dynamic.title(f"{case['case_id']} | {case['title']} (productId={self._product_id})")
        execute_test_case(case, admin_api_client, db, global_vars)
        logger.info(f"[MOFF_004] 审核通过下架商品 productId={self._product_id}")


# ==================== 用例2: 商品上架流程 ====================
@allure.epic("商家端")
@allure.feature("商家端-商品管理模块")
@allure.story("单个商品上架流程")
class TestProductOnShelf:
    """商品上架流程：查询已下架商品 → 上架 → 验证已上架"""

    _global_vars = None
    _product_id = None
    _id = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("product_shelf_toggle_api.yaml")
        return cls._global_vars.copy()

    @pytest.mark.order(1)
    @allure.title("MON_001 - 查询已下架商品")
    def test_step1_query_unlisted_products(self, merchant_api_client, db, admin_api_client):
        """查询已下架商品列表（type=2），提取第一条记录的 productId 供上架使用"""
        cases = get_test_data(_DATA_FILE, "product_on_shelf_tests")
        case = cases[0]
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        execute_test_case(case, merchant_api_client, db, global_vars)

        resp = merchant_api_client.post(case["endpoint"], json=replace_placeholders(case["json"], global_vars))
        resp_json = resp.json()
        records = resp_json.get("data", {}).get("records", [])

        if not records:
            pytest.skip("已下架商品列表为空，无法获取 productId 进行上架测试")

        self.__class__._product_id = str(records[0]["productId"])
        self.__class__._id = str(records[0]["id"])
        allure.attach(
            f"product_id = {self._product_id}\n商品名称: {records[0].get('name', '')}",
            name="提取的商品ID",
            attachment_type=allure.attachment_type.TEXT,
        )
        logger.info(f"MON_001 提取 productId={self._product_id}, 商品: {records[0].get('name', '')}")

    @pytest.mark.order(2)
    @allure.title("MON_002 - 上架商品")
    def test_step2_on_shelf_product(self, merchant_api_client, db):
        """使用步骤1提取的 productId 调用上架接口（type=1）"""
        cases = get_test_data(_DATA_FILE, "product_on_shelf_tests")
        case = cases[1]
        global_vars = self._load_global_vars()

        if not self._product_id:
            pytest.skip("步骤1未获取到 productId，跳过上架操作")

        global_vars["product_id"] = self._product_id
        global_vars["id"] = self._id
        allure.dynamic.title(f"{case['case_id']} | {case['title']} (productId={self._product_id})")
        execute_test_case(case, merchant_api_client, db, global_vars)
        logger.info(f"[MON_002] 上架商品成功 productId={self._product_id}")

    @pytest.mark.order(3)
    @allure.title("MON_003 - 验证商品已上架")
    def test_step3_verify_on_shelf(self, merchant_api_client, db):
        """查询type=1的已上架商品列表，验证该商品出现在上架列表中"""
        cases = get_test_data(_DATA_FILE, "product_on_shelf_tests")
        case = cases[2]
        global_vars = self._load_global_vars()

        if not self._product_id:
            pytest.skip("步骤1未获取到 productId，跳过验证")

        global_vars["product_id"] = self._product_id
        allure.dynamic.title(f"{case['case_id']} | {case['title']} (productId={self._product_id})")

        # 执行框架断言（验证接口响应成功）
        execute_test_case(case, merchant_api_client, db, global_vars)

        # 补充断言：验证该商品在已上架列表中
        with allure.step(f"验证 productId={self._product_id} 在已上架商品列表中"):
            body = replace_placeholders(case["json"], global_vars)
            resp = merchant_api_client.post(case["endpoint"], json=body)
            resp_json = resp.json()
            records = resp_json.get("data", {}).get("records", [])
            product_ids = [str(r.get("productId", "")) for r in records]

            allure.attach(
                f"查询到的已上架商品 productId 列表: {product_ids}\n"
                f"目标 productId: {self._product_id}",
                name="验证数据",
                attachment_type=allure.attachment_type.TEXT,
            )

            assert self._product_id in product_ids, (
                f"商品 {self._product_id} 未出现在已上架列表中，上架未生效"
            )
            logger.info(f"[MON_003] 验证通过: 商品 {self._product_id} 已在已上架列表中")

    @pytest.mark.order(4)
    @allure.title("MON_004 - 运营端审核商品上架")
    def test_step4_audit_on_shelf(self, admin_api_client, db):
        """调用运营端 productAudit 接口，auditState=2 审核通过上架商品"""
        cases = get_test_data(_DATA_FILE, "product_on_shelf_tests")
        case = cases[3]  # MON_004
        global_vars = self._load_global_vars()

        if not self._product_id:
            pytest.skip("步骤1未获取到 productId，跳过审核上架")

        global_vars["product_id"] = self._product_id
        global_vars["id"] = self._id
        allure.dynamic.title(f"{case['case_id']} | {case['title']} (productId={self._product_id})")
        execute_test_case(case, admin_api_client, db, global_vars)
        logger.info(f"[MON_004] 审核通过上架商品 productId={self._product_id}")