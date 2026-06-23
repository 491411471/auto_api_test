# testcases/merchant/api/product/test_douyin_product_draft.py
"""
商家端 - 抖音新建商品（草稿箱）流程测试

步骤1: 保存草稿箱 → 提取 draft_id → SQL 查询 product_id
步骤2: 查询草稿箱验证商品存在
步骤3: 从草稿箱发布商品
"""
import allure
import pytest
import time
from datetime import datetime, timedelta
import calendar

from common.logger import logger
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables

_DATA_FILE = "data/merchant/api/product/douyin_product_draft.yaml"


@allure.epic("商家端")
@allure.feature("商家端-商品管理模块")
@allure.story("抖音新建商品--保存草稿箱--查询草稿箱验证--发布商品流程")
class TestDouyinProductDraft:
    """抖音商品草稿箱流程：保存草稿 → 查询草稿箱验证 → 发布商品"""

    _global_vars = None
    _draft_id = None
    _product_id = None
    _product_name = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    @pytest.mark.order(1)
    @allure.title("DPD_001 - 保存抖音商品到草稿箱")
    def test_step1_save_draft(self, merchant_api_client, db):
        """调用 addDraftProduct 保存抖音商品草稿，提取 draft_id 并通过 SQL 查询 product_id"""
        cases = get_test_data(_DATA_FILE, "douyin_product_draft_tests")
        case = cases[0]
        global_vars = self._load_global_vars()

        # 生成动态变量
        now = datetime.now()
        # 推迟一个月（精确到日历月）
        next_month = now.month + 1
        next_year = now.year + (next_month - 1) // 12
        next_month = (next_month - 1) % 12 + 1
        next_day = min(now.day, calendar.monthrange(next_year, next_month)[1])
        one_month_later = now.replace(year=next_year, month=next_month, day=next_day)

        global_vars["product_name"] = f"自动化测试-抖音商品-{now.strftime('%Y%m%d%H%M%S')}"
        self.__class__._product_name = global_vars["product_name"]
        global_vars["create_date_start"] = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        global_vars["create_date_end"] = one_month_later.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        global_vars["sold_start"] = now.strftime("%Y-%m-%d %H:%M:%S")
        global_vars["sold_end"] = one_month_later.strftime("%Y-%m-%d %H:%M:%S")

        allure.dynamic.title(f"{case['case_id']} | {case['title']}")
        execute_test_case(case, merchant_api_client, db, global_vars)

        # 保存提取的 draft_id
        self.__class__._draft_id = global_vars.get("draft_id")
        assert self._draft_id is not None, "保存草稿箱后未获取到 draft_id"

        # 带重试的 SQL 查询 product_id（API 写入后数据库可能有短暂延迟）
        product_id = None
        query = f"SELECT product_id FROM llxz_product.ct_product_draft WHERE id = {self._draft_id}"
        for attempt in range(1, 6):
            try:
                result = db.fetch_one(query)
                if result:
                    product_id = result.get("product_id") if isinstance(result, dict) else result[0]
                if product_id:
                    logger.info(f"[DPD_001] 第 {attempt} 次查询成功: product_id={product_id}")
                    break
            except Exception as e:
                logger.warning(f"[DPD_001] 第 {attempt} 次查询异常: {e}")
            logger.info(f"[DPD_001] product_id 未就绪，等待 1 秒后重试 ({attempt}/5)...")
            time.sleep(1)

        self.__class__._product_id = product_id

        allure.attach(
            f"draft_id = {self._draft_id}\nproduct_id = {self._product_id}\n"
            f"商品名称: {global_vars.get('product_name', '')}",
            name="提取的草稿信息",
            attachment_type=allure.attachment_type.TEXT,
        )
        logger.info(f"[DPD_001] draft_id={self._draft_id}, product_id={self._product_id}")

        assert self._product_id is not None, "SQL 重试 5 次后仍未查询到 product_id"

    @pytest.mark.order(2)
    @allure.title("DPD_002 - 查询草稿箱验证抖音商品")
    def test_step2_query_draft_box(self, merchant_api_client, db):
        """使用 SQL 获取的 product_id 查询草稿箱，验证商品存在"""
        cases = get_test_data(_DATA_FILE, "douyin_product_draft_tests")
        case = cases[1]
        global_vars = self._load_global_vars()

        if not self._product_id:
            pytest.skip("步骤1未获取到 product_id，跳过草稿箱查询")

        global_vars["product_id"] = str(self._product_id)
        allure.dynamic.title(f"{case['case_id']} | {case['title']} (productId={self._product_id})")
        execute_test_case(case, merchant_api_client, db, global_vars)
        logger.info(f"[DPD_002] 草稿箱查询验证通过 productId={self._product_id}")

    @pytest.mark.order(3)
    @allure.title("DPD_003 - 从草稿箱发布抖音商品")
    def test_step3_publish_product(self, merchant_api_client, db):
        """使用草稿箱中的商品信息调用发布接口，完成商品上架"""
        cases = get_test_data(_DATA_FILE, "douyin_product_draft_tests")
        case = cases[2]
        global_vars = self._load_global_vars()

        if not self._draft_id or not self._product_id:
            pytest.skip("步骤1未获取到 draft_id 或 product_id，跳过发布")

        # 生成动态日期变量
        now = datetime.now()
        next_month = now.month + 1
        next_year = now.year + (next_month - 1) // 12
        next_month = (next_month - 1) % 12 + 1
        next_day = min(now.day, calendar.monthrange(next_year, next_month)[1])
        one_month_later = now.replace(year=next_year, month=next_month, day=next_day)

        global_vars["draft_id"] = str(self._draft_id)
        global_vars["product_id"] = str(self._product_id)
        global_vars["product_name"] = self._product_name
        global_vars["create_date_start"] = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        global_vars["create_date_end_pub"] = one_month_later.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        global_vars["sold_start"] = now.strftime("%Y-%m-%d %H:%M:%S")
        global_vars["sold_end"] = one_month_later.strftime("%Y-%m-%d %H:%M:%S")

        allure.dynamic.title(f"{case['case_id']} | {case['title']} (draftId={self._draft_id}, productId={self._product_id})")
        execute_test_case(case, merchant_api_client, db, global_vars)

        # 发布后从 ct_product 查询正式商品的 product_id（草稿和正式商品 product_id 不同）
        query_published = (
            "SELECT product_id FROM llxz_product.ct_product "
            f"WHERE name = '{self._product_name}' "
            "AND product_of_dou_yin = 1 "
            "AND delete_time IS NULL "
            "ORDER BY create_time DESC LIMIT 1"
        )
        published_product_id = None
        for attempt in range(1, 6):
            try:
                result = db.fetch_one(query_published)
                if result:
                    published_product_id = result.get("product_id") if isinstance(result, dict) else result[0]
                if published_product_id:
                    logger.info(f"[DPD_003] 第 {attempt} 次查询已发布商品: product_id={published_product_id}")
                    break
            except Exception as e:
                logger.warning(f"[DPD_003] 第 {attempt} 次查询异常: {e}")
            logger.info(f"[DPD_003] 已发布商品 product_id 未就绪，等待 2 秒后重试 ({attempt}/5)...")
            time.sleep(2)

        if published_product_id:
            self.__class__._product_id = published_product_id
            logger.info(f"[DPD_003] 已更新 product_id: 草稿={global_vars.get('product_id')} -> 已发布={published_product_id}")
        else:
            logger.warning(f"[DPD_003] 未查询到已发布商品的 product_id，继续使用草稿值={self._product_id}")

        logger.info(f"[DPD_003] 发布成功 draftId={self._draft_id}, productId={self._product_id}")

    @pytest.mark.order(4)
    @allure.title("DPD_004 - 运营端审核通过抖音商品")
    def test_step4_audit_product(self, admin_api_client, db):
        """草稿箱发布商品后，调用运营端 examineProductConfirm 接口审核通过，id 由 SQL 从 ct_product 动态获取"""
        cases = get_test_data(_DATA_FILE, "douyin_product_draft_tests")
        case = cases[3]  # DPD_004
        global_vars = self._load_global_vars()

        if not self._product_id:
            pytest.skip("步骤1未获取到 product_id，跳过审核")

        global_vars["product_id"] = str(self._product_id)
        allure.dynamic.title(f"{case['case_id']} | {case['title']} (productId={self._product_id})")
        execute_test_case(case, admin_api_client, db, global_vars)
        logger.info(f"[DPD_004] 审核通过 productId={self._product_id}")
