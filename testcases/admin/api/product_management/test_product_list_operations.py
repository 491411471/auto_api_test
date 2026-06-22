# testcases/admin/api/product_management/test_product_list_operations.py
"""
运营端 - 商品管理：商品列表操作流程测试

完整的商品列表管理流程，包含7个步骤：
  步骤1: 空条件获取商品列表（提取3条商品编码和名称）
  步骤2: 批量设置库存（使用步骤1的2条商品编码）
  步骤3: 批量分类（使用步骤1的2条商品编码，SQL校验submit_type）
  步骤4: 查询已上架商品（提取3条商品编码和名称）
  步骤5: 批量下架（使用步骤4的2条商品编码，SQL校验type=2）
  步骤6: 查询已下架商品（提取3条商品编码和名称）
  步骤7: 批量上架（使用步骤6的2条商品编码，SQL校验type=1）
"""
import json
import random
import time
from datetime import datetime, timedelta

import allure
import pytest

from common.logger import logger
from common.test_helpers import (
    execute_test_case,
    execute_sql,
    replace_placeholders,
    validate_response,
)
from utils.assert_utils import assert_status_code
from utils.data_loader import get_test_data, get_global_variables
from utils.variable_utils import validate, get_value_by_path

_DATA_FILE = "data/admin/api/product_management/product_list_operations.yaml"


@allure.epic("运营端")
@allure.feature("运营端-商品管理")
@allure.story("商品列表操作流程")
class TestProductListOperations:
    """商品列表操作流程 - 7 个步骤串联"""

    # ==================== 跨步骤共享变量 ====================
    _global_vars = None
    # 步骤1提取的商品数据（3条）
    _step1_products = []  # [{"productId": "...", "name": "..."}, ...]
    # 步骤4提取的已上架商品数据（3条）
    _step4_products = []
    # 步骤6提取的已下架商品数据（3条）
    _step6_products = []

    @classmethod
    def _load_global_vars(cls):
        """加载 YAML 全局变量（懒加载 + 缓存）"""
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    # ==================== 辅助方法 ====================
    @staticmethod
    def _send_query_and_extract(api_client, case: dict, global_vars: dict, extract_count: int = 3):
        """
        发送查询请求并随机提取 N 条商品记录。
        返回 (response_data, extracted_products)。
        """
        case_replaced = replace_placeholders(case, global_vars)
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
            allure.attach(
                json.dumps(response_data, ensure_ascii=False, indent=2, default=str),
                name="完整响应体",
                attachment_type=allure.attachment_type.JSON,
            )

        # 基础断言
        with allure.step("执行基础断言"):
            assert_status_code(resp.status_code, case["expected_status"])
            validate_response(case, response_data, global_vars)

        # 提取商品记录
        records = response_data.get("data", {}).get("records", [])
        if not records:
            return response_data, []

        count = min(extract_count, len(records))
        extracted = random.sample(records, count)
        products = [
            {"productId": r["productId"], "name": r["name"]}
            for r in extracted
        ]
        return response_data, products

    @staticmethod
    def _build_in_clause(product_ids: list) -> str:
        """构建 SQL IN 子句：'id1', 'id2'"""
        return ", ".join(f"'{pid}'" for pid in product_ids)

    @staticmethod
    def _verify_sql_type(db, query_template: str, product_ids: list, check_column: str, expected_value):
        """
        执行 SQL 验证：查询指定商品的某个字段，断言所有结果等于期望值。
        """
        in_clause = TestProductListOperations._build_in_clause(product_ids)
        query = query_template.format(in_clause=in_clause)
        sql_config = {"query": query, "multiple": True, "columns": ["pid", check_column]}

        with allure.step(f"SQL 验证：{check_column} == {expected_value}"):
            allure.attach(query, name="验证 SQL", attachment_type=allure.attachment_type.TEXT)
            rows = execute_sql(db, sql_config)
            logger.info(f"SQL 验证结果: {rows}")
            allure.attach(
                json.dumps(rows, ensure_ascii=False, default=str),
                name="SQL 查询结果",
                attachment_type=allure.attachment_type.TEXT,
            )

            assert rows and len(rows) > 0, f"SQL 无结果: {query}"
            for row in rows:
                actual = row[check_column]
                # 类型宽容比较（数据库可能返回 int/str）
                if str(actual) != str(expected_value):
                    assert False, (
                        f"SQL 验证失败：product_id={row['pid']}，"
                        f"期望 {check_column}={expected_value}，实际={actual}"
                    )
            logger.info(f"SQL 验证通过：{len(rows)} 条记录的 {check_column} 均为 {expected_value}")

    # ==================== 第一步：空条件获取商品列表 ====================
    @pytest.mark.order(1)
    @allure.title("PLO_001 - 空条件获取商品列表商品信息")
    def test_step1_query_all_products(self, admin_api_client, db):
        """空条件查询商品列表，随机获取3条数据的商品编码和商品名称"""
        case = get_test_data(_DATA_FILE, "step1_query_all_products")
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['step_id']} | {case['title']}")

        _, products = self._send_query_and_extract(admin_api_client, case, global_vars, extract_count=3)

        if not products:
            pytest.skip("未查询到商品数据，跳过后续测试")

        self.__class__._step1_products = products
        print("提取的商品数据:", products)
        extracted_info = "\n".join(f"商品编码: {p['productId']}  商品名称: {p['name']}" for p in products)
        allure.attach(extracted_info, name="提取的商品数据", attachment_type=allure.attachment_type.TEXT)
        logger.info(f"[PLO_001] 提取 {len(products)} 条商品:\n{extracted_info}")

    # ==================== 第二步：批量设置库存 ====================
    @pytest.mark.order(2)
    @allure.title("PLO_002 - 批量设置库存")
    def test_step2_batch_set_inventory(self, admin_api_client, db):
        """从步骤1获取2条商品编码，批量设置库存为100"""
        if len(self._step1_products) < 2:
            pytest.skip("步骤1未获取到足够的商品数据（需至少2条），跳过")

        case = get_test_data(_DATA_FILE, "step2_batch_set_inventory")
        global_vars = self._load_global_vars()

        # 从步骤1随机取2条商品编码
        selected = random.sample(self._step1_products, 2)
        product_ids = [p["productId"] for p in selected]

        # 动态计算日期
        now = datetime.now()
        date_kssj = now.strftime("%Y-%m-%d")
        date_jssj = (now + timedelta(days=15)).strftime("%Y-%m-%d")

        # 注入动态变量
        global_vars["batch_product_ids"] = product_ids
        global_vars["date_day_kssj"] = date_kssj
        global_vars["date_day_jssj"] = date_jssj

        allure.dynamic.title(f"{case['step_id']} | {case['title']}")
        allure.attach(
            f"productIds = {product_ids}\ndateDayKssj = {date_kssj}\ndateDayJssj = {date_jssj}",
            name="动态注入的变量",
            attachment_type=allure.attachment_type.TEXT,
        )

        execute_test_case(case, admin_api_client, db, global_vars)
        logger.info(f"[PLO_002] 批量设置库存成功: productIds={product_ids}")

    # ==================== 第三步：批量分类 ====================
    @pytest.mark.order(3)
    @allure.title("PLO_003 - 批量分类")
    def test_step3_batch_classify(self, admin_api_client, db):
        """从步骤1获取2条商品编码，随机设置分类类型，SQL校验submit_type"""
        if len(self._step1_products) < 2:
            pytest.skip("步骤1未获取到足够的商品数据（需至少2条），跳过")

        case = get_test_data(_DATA_FILE, "step3_batch_classify")
        global_vars = self._load_global_vars()

        # 从步骤1随机取2条商品编码
        selected = random.sample(self._step1_products, 2)
        product_ids = [p["productId"] for p in selected]

        # 随机选择分类类型（1:普通, 2:芝麻免押, 3:高危, 4:双签）
        submit_type_options = ["1", "2", "3", "4"]
        submit_type = random.choice(submit_type_options)

        global_vars["batch_product_ids"] = product_ids
        global_vars["submit_type"] = submit_type

        allure.dynamic.title(f"{case['step_id']} | {case['title']}")
        allure.attach(
            f"productIdList = {product_ids}\nsubmitType = {submit_type}",
            name="动态注入的变量",
            attachment_type=allure.attachment_type.TEXT,
        )

        execute_test_case(case, admin_api_client, db, global_vars)

        # SQL 验证：检查 submit_type 是否正确更新
        verify_config = case.get("verify_sql", {})
        if verify_config:
            self._verify_sql_type(
                db,
                verify_config["query_template"],
                product_ids,
                verify_config["check_column"],
                submit_type,
            )

        logger.info(f"[PLO_003] 批量分类成功: productIds={product_ids}, submitType={submit_type}")

    # ==================== 第四步：查询已上架的商品 ====================
    @pytest.mark.order(4)
    @allure.title("PLO_004 - 查询已上架的商品")
    def test_step4_query_on_shelf(self, admin_api_client, db):
        """查询已上架商品(type=1)，随机获取3条数据的商品编码和商品名称"""
        case = get_test_data(_DATA_FILE, "step4_query_on_shelf")
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['step_id']} | {case['title']}")

        _, products = self._send_query_and_extract(admin_api_client, case, global_vars, extract_count=3)

        if not products:
            pytest.skip("未查询到已上架商品，跳过后续测试")

        self.__class__._step4_products = products

        extracted_info = "\n".join(
            f"  商品编码: {p['productId']}  商品名称: {p['name']}" for p in products
        )
        allure.attach(extracted_info, name="提取的已上架商品数据", attachment_type=allure.attachment_type.TEXT)
        logger.info(f"[PLO_004] 提取 {len(products)} 条已上架商品:\n{extracted_info}")

    # ==================== 第五步：批量下架 ====================
    @pytest.mark.order(5)
    @allure.title("PLO_005 - 批量下架")
    def test_step5_batch_delist(self, admin_api_client, db):
        """从步骤4获取2条商品编码，批量下架(type=2)，SQL校验type"""
        if len(self._step4_products) < 2:
            pytest.skip("步骤4未获取到足够的商品数据（需至少2条），跳过")

        case = get_test_data(_DATA_FILE, "step5_batch_delist")
        global_vars = self._load_global_vars()

        # 从步骤4随机取2条商品编码
        selected = random.sample(self._step4_products, 2)
        product_ids = [p["productId"] for p in selected]

        global_vars["shelf_product_ids"] = product_ids

        # 等待10秒，避免触发接口防重复点击限制（10s内请不要连续点击）
        logger.info("[PLO_005] 等待 10 秒，避免连续点击限流...")
        time.sleep(10)

        allure.dynamic.title(f"{case['step_id']} | {case['title']}")
        allure.attach(
            f"productIds = {product_ids}\ntype = 2",
            name="动态注入的变量",
            attachment_type=allure.attachment_type.TEXT,
        )

        execute_test_case(case, admin_api_client, db, global_vars)

        # SQL 验证：检查 type 是否为 2（已下架）
        verify_config = case.get("verify_sql", {})
        if verify_config:
            self._verify_sql_type(
                db,
                verify_config["query_template"],
                product_ids,
                verify_config["check_column"],
                verify_config.get("expected_value", 2),
            )

        logger.info(f"[PLO_005] 批量下架成功: productIds={product_ids}")

    # ==================== 第六步：查询已下架商品 ====================
    @pytest.mark.order(6)
    @allure.title("PLO_006 - 查询已下架商品")
    def test_step6_query_off_shelf(self, admin_api_client, db):
        """查询已下架商品(type=2)，随机获取3条数据的商品编码和商品名称"""
        case = get_test_data(_DATA_FILE, "step6_query_off_shelf")
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['step_id']} | {case['title']}")

        _, products = self._send_query_and_extract(admin_api_client, case, global_vars, extract_count=3)

        if not products:
            pytest.skip("未查询到已下架商品，跳过后续测试")

        self.__class__._step6_products = products

        extracted_info = "\n".join(
            f"  商品编码: {p['productId']}  商品名称: {p['name']}" for p in products
        )
        allure.attach(extracted_info, name="提取的已下架商品数据", attachment_type=allure.attachment_type.TEXT)
        logger.info(f"[PLO_006] 提取 {len(products)} 条已下架商品:\n{extracted_info}")

    # ==================== 第七步：批量上架 ====================
    @pytest.mark.order(7)
    @allure.title("PLO_007 - 批量上架")
    def test_step7_batch_listing(self, admin_api_client, db):
        """从步骤6获取2条商品编码，批量上架(type=1)，SQL校验type"""
        if len(self._step6_products) < 2:
            pytest.skip("步骤6未获取到足够的商品数据（需至少2条），跳过")

        case = get_test_data(_DATA_FILE, "step7_batch_listing")
        global_vars = self._load_global_vars()

        # 从步骤6随机取2条商品编码
        selected = random.sample(self._step6_products, 2)
        product_ids = [p["productId"] for p in selected]

        global_vars["listing_product_ids"] = product_ids

        # 等待10秒，避免触发接口防重复点击限制（10s内请不要连续点击）
        logger.info("[PLO_007] 等待 10 秒，避免连续点击限流...")
        time.sleep(10)

        allure.dynamic.title(f"{case['step_id']} | {case['title']}")
        allure.attach(
            f"productIds = {product_ids}\ntype = 1",
            name="动态注入的变量",
            attachment_type=allure.attachment_type.TEXT,
        )

        execute_test_case(case, admin_api_client, db, global_vars)

        # SQL 验证：检查 type 是否为 1（已上架）
        verify_config = case.get("verify_sql", {})
        if verify_config:
            self._verify_sql_type(
                db,
                verify_config["query_template"],
                product_ids,
                verify_config["check_column"],
                verify_config.get("expected_value", 1),
            )

        logger.info(f"[PLO_007] 批量上架成功: productIds={product_ids}")
