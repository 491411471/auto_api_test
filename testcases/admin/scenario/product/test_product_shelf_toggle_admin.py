# testcases/admin/scenario/product/test_product_shelf_toggle.py
"""
运营端 - 商品上下架流程测试

用例1: 单个商品下架流程
  - 步骤1: 查询私域已上架商品（commonStatus=3），提取 productId
  - 步骤2: 下架商品（setProuctShowState, type=3）
  - 步骤3: 验证商品已下架（查询已上架列表不应包含该商品）

用例2: 单个商品上架流程
  - 步骤1: 查询私域已下架商品（commonStatus=3, type=2），提取 productId
  - 步骤2: 上架商品（setProuctShowState, type=1, GET）
  - 步骤3: 验证商品已上架（查询已下架列表不应包含该商品）
"""
import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case, replace_placeholders
from utils.data_loader import get_test_data, get_global_variables

_DATA_FILE = "data/admin/scenario/product/product_shelf_toggle_api.yaml"


# ==================== 用例1: 商品下架流程 ====================
@allure.epic("运营端")
@allure.feature("运营端-商品管理")
@allure.story("单个商品下架流程")
class TestProductOffShelf:
    """商品下架流程：查询已上架商品 → 下架"""

    _global_vars = None
    _product_id = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("product_shelf_toggle_api.yaml")
        return cls._global_vars.copy()

    @pytest.mark.order(1)
    @allure.title("OFF_001 - 查询私域已上架商品")
    def test_step1_query_listed_products(self, admin_api_client, db):
        """查询已上架商品列表，提取第一条记录的 productId 供下架使用"""
        cases = get_test_data(_DATA_FILE, "product_off_shelf_tests")
        case = cases[0]
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        # 使用 execute_test_case 执行查询，利用框架的断言验证
        execute_test_case(case, admin_api_client, db, global_vars)

        # 再发一次请求提取 productId（参数相同，结果一致）
        body = replace_placeholders(case["json"], global_vars)
        resp = admin_api_client.post(case["endpoint"], json=body)
        resp_json = resp.json()
        records = resp_json.get("data", {}).get("records", [])

        if not records:
            pytest.skip("已上架商品列表为空，无法获取 productId 进行下架测试")

        self.__class__._product_id = str(records[0]["productId"])
        allure.attach(
            f"product_id = {self._product_id}\n商品名称: {records[0].get('name', '')}",
            name="提取的商品ID",
            attachment_type=allure.attachment_type.TEXT,
        )
        logger.info(f"OFF_001 提取 productId={self._product_id}, 商品: {records[0].get('name', '')}")

    @pytest.mark.order(2)
    @allure.title("OFF_002 - 下架商品")
    def test_step2_off_shelf_product(self, admin_api_client, db):
        """使用步骤1提取的 productId 调用下架接口（type=3）"""
        cases = get_test_data(_DATA_FILE, "product_off_shelf_tests")
        case = cases[1]
        global_vars = self._load_global_vars()

        if not self._product_id:
            pytest.skip("步骤1未获取到 productId，跳过下架操作")

        global_vars["product_id"] = self._product_id
        allure.dynamic.title(f"{case['case_id']} | {case['title']} (productId={self._product_id})")
        execute_test_case(case, admin_api_client, db, global_vars)
        logger.info(f"[OFF_002] 下架商品成功 productId={self._product_id}")

    @pytest.mark.order(3)
    @allure.title("OFF_003 - 验证商品已下架")
    def test_step3_verify_off_shelf(self, admin_api_client, db):
        """用 productId 精确查询已上架列表，验证该商品已不在上架列表中"""
        cases = get_test_data(_DATA_FILE, "product_off_shelf_tests")
        case = cases[2]
        global_vars = self._load_global_vars()

        if not self._product_id:
            pytest.skip("步骤1未获取到 productId，跳过验证")

        global_vars["product_id"] = self._product_id
        allure.dynamic.title(f"{case['case_id']} | {case['title']} (productId={self._product_id})")

        # 执行框架断言（验证接口响应成功）
        execute_test_case(case, admin_api_client, db, global_vars)

        # 补充断言：验证该商品不在已上架列表中
        with allure.step(f"验证 productId={self._product_id} 不在已上架商品列表中"):
            body = replace_placeholders(case["json"], global_vars)
            resp = admin_api_client.post(case["endpoint"], json=body)
            resp_json = resp.json()
            records = resp_json.get("data", {}).get("records", [])
            product_ids = [str(r.get("productId", "")) for r in records]

            allure.attach(
                f"查询到的已上架商品 productId 列表: {product_ids}\n"
                f"目标 productId: {self._product_id}",
                name="验证数据",
                attachment_type=allure.attachment_type.TEXT,
            )

            assert self._product_id not in product_ids, (
                f"商品 {self._product_id} 仍出现在已上架列表中，下架未生效"
            )
            logger.info(f"[OFF_003] 验证通过: 商品 {self._product_id} 已不在已上架列表中")


# ==================== 用例2: 商品上架流程 ====================
@allure.epic("运营端")
@allure.feature("运营端-商品管理")
@allure.story("单个商品上架流程")
class TestProductOnShelf:
    """商品上架流程：查询已下架商品 → 上架"""

    _global_vars = None
    _product_id = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("product_shelf_toggle_api.yaml")
        return cls._global_vars.copy()

    @pytest.mark.order(11)
    @allure.title("ON_001 - 查询私域已下架商品")
    def test_step1_query_unlisted_products(self, admin_api_client, db):
        """查询已下架商品列表，提取第一条记录的 productId 供上架使用"""
        cases = get_test_data(_DATA_FILE, "product_on_shelf_tests")
        case = cases[0]
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        execute_test_case(case, admin_api_client, db, global_vars)

        resp = admin_api_client.post(case["endpoint"], json=replace_placeholders(case["json"], global_vars))
        resp_json = resp.json()
        records = resp_json.get("data", {}).get("records", [])

        if not records:
            pytest.skip("已下架商品列表为空，无法获取 productId 进行上架测试")

        self.__class__._product_id = str(records[0]["productId"])
        allure.attach(
            f"product_id = {self._product_id}\n商品名称: {records[0].get('name', '')}",
            name="提取的商品ID",
            attachment_type=allure.attachment_type.TEXT,
        )
        logger.info(f"ON_001 提取 productId={self._product_id}, 商品: {records[0].get('name', '')}")

    @pytest.mark.order(12)
    @allure.title("ON_002 - 上架商品")
    def test_step2_on_shelf_product(self, admin_api_client, db):
        """使用步骤1提取的 productId 调用上架接口（type=1, GET）"""
        cases = get_test_data(_DATA_FILE, "product_on_shelf_tests")
        case = cases[1]
        global_vars = self._load_global_vars()

        if not self._product_id:
            pytest.skip("步骤1未获取到 productId，跳过上架操作")

        global_vars["product_id"] = self._product_id
        allure.dynamic.title(f"{case['case_id']} | {case['title']} (productId={self._product_id})")
        execute_test_case(case, admin_api_client, db, global_vars)
        logger.info(f"[ON_002] 上架商品成功 productId={self._product_id}")

    @pytest.mark.order(13)
    @allure.title("ON_003 - 验证商品已上架")
    def test_step3_verify_on_shelf(self, admin_api_client, db):
        """用 productId 精确查询已下架列表，验证该商品已不在下架列表中"""
        cases = get_test_data(_DATA_FILE, "product_on_shelf_tests")
        case = cases[2]
        global_vars = self._load_global_vars()

        if not self._product_id:
            pytest.skip("步骤1未获取到 productId，跳过验证")

        global_vars["product_id"] = self._product_id
        allure.dynamic.title(f"{case['case_id']} | {case['title']} (productId={self._product_id})")

        # 执行框架断言（验证接口响应成功）
        execute_test_case(case, admin_api_client, db, global_vars)

        # 补充断言：验证该商品不在已下架列表中
        with allure.step(f"验证 productId={self._product_id} 不在已下架商品列表中"):
            body = replace_placeholders(case["json"], global_vars)
            resp = admin_api_client.post(case["endpoint"], json=body)
            resp_json = resp.json()
            records = resp_json.get("data", {}).get("records", [])
            product_ids = [str(r.get("productId", "")) for r in records]

            allure.attach(
                f"查询到的已下架商品 productId 列表: {product_ids}\n"
                f"目标 productId: {self._product_id}",
                name="验证数据",
                attachment_type=allure.attachment_type.TEXT,
            )

            assert self._product_id not in product_ids, (
                f"商品 {self._product_id} 仍出现在已下架列表中，上架未生效"
            )
            logger.info(f"[ON_003] 验证通过: 商品 {self._product_id} 已不在已下架列表中")
