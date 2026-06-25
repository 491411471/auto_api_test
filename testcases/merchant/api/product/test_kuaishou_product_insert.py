# testcases/merchant/api/product/test_kuaishou_product_insert.py
"""
商家端 - 新增快手商品 + 运营端审核快手商品流程测试

步骤1: 商家端新增快手商品 → 保存 product_title → SQL 查询商品 id（带重试机制）
步骤2: 运营端审核快手商品
"""
import allure
import pytest
import time
from datetime import datetime, timedelta

from common.logger import logger
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables
from utils.data_generator import generate_test_data

_DATA_FILE = "data/merchant/api/product/kuaishou_product_insert_api.yaml"


@allure.epic("商家端")
@allure.feature("商家端-商品管理模块")
@allure.story("新增快手商品+运营端审核流程")
class TestKuaishouProductInsert:
    """快手商品新增与审核流程：商家端新增 → 运营端审核"""

    _global_vars = None
    _product_id = None
    _product_title = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    @pytest.mark.order(1)
    @allure.title("KPI_001 - 商家端新增快手商品")
    def test_step1_insert_kuaishou_product(self, merchant_api_client, db):
        """调用 busInsertProduct 接口新增快手商品，保存 product_title 用于后续 SQL 查询"""
        cases = get_test_data(_DATA_FILE, "kuaishou_product_insert_tests")
        case = cases[0]
        global_vars = self._load_global_vars()

        # 生成动态变量
        now = datetime.now()
        one_month_later = now + timedelta(days=30)

        # 生成商品标题和详情
        product_title = generate_test_data("product_title")
        product_detail = generate_test_data("product_detail")

        global_vars["product_title"] = product_title
        global_vars["product_detail"] = product_detail
        global_vars["uid_1"] = generate_test_data("uid")
        global_vars["uid_2"] = generate_test_data("uid")
        
        # createDate 格式: "2026-06-23T16:00:00.000Z"
        global_vars["create_date_start"] = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        global_vars["create_date_end"] = one_month_later.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        # soldStart/soldEnd 格式: "2026-06-24 00:00:00"
        global_vars["sold_start"] = now.strftime("%Y-%m-%d 00:00:00")
        global_vars["sold_end"] = one_month_later.strftime("%Y-%m-%d 23:59:59")

        # 保存商品标题用于 SQL 查询
        self.__class__._product_title = product_title

        allure.dynamic.title(f"{case['case_id']} | {case['title']}")
        execute_test_case(case, merchant_api_client, db, global_vars)

        logger.info(f"[KPI_001] 新增快手商品成功: product_title={product_title}")

        # 带重试的 SQL 查询商品 id（API 写入后数据库可能有短暂延迟）
        product_id = None
        query = (
            "SELECT id FROM llxz_product.ct_product "
            f"WHERE name = '{product_title}' "
            "AND product_type = 'kuaishou' "
            "AND delete_time IS NULL "
            "ORDER BY create_time DESC LIMIT 1"
        )
        
        for attempt in range(1, 6):
            try:
                result = db.fetch_one(query)
                if result:
                    product_id = result.get("id") if isinstance(result, dict) else result[0]
                if product_id:
                    logger.info(f"[KPI_001] 第 {attempt} 次查询成功: product_id={product_id}")
                    break
            except Exception as e:
                logger.warning(f"[KPI_001] 第 {attempt} 次查询异常: {e}")
            logger.info(f"[KPI_001] product_id 未就绪，等待 1 秒后重试 ({attempt}/5)...")
            time.sleep(1)

        self.__class__._product_id = product_id

        allure.attach(
            f"商品标题: {product_title}\n"
            f"商品ID: {product_id}",
            name="新增快手商品信息",
            attachment_type=allure.attachment_type.TEXT,
        )
        logger.info(f"[KPI_001] product_title={product_title}, product_id={product_id}")

        assert product_id is not None, "SQL 重试 5 次后仍未查询到商品 id"

    @pytest.mark.order(2)
    @allure.title("KPI_002 - 运营端审核快手商品")
    def test_step2_audit_kuaishou_product(self, admin_api_client, db):
        """商家端新增快手商品后，调用运营端 examineProductConfirm 接口审核通过，id 通过 SQL 从 ct_product 动态获取"""
        cases = get_test_data(_DATA_FILE, "kuaishou_product_insert_tests")
        case = cases[1]
        global_vars = self._load_global_vars()

        if not self._product_id:
            pytest.skip("步骤1未获取到 product_id，跳过审核")

        # 设置商品标题用于 SQL 查询
        global_vars["product_title"] = self._product_title

        allure.dynamic.title(f"{case['case_id']} | {case['title']} (productTitle={self._product_title})")
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info(f"[KPI_002] 审核快手商品成功: product_title={self._product_title}, product_id={self._product_id}")
