# testcases/Ali_app/api/test_ali_app_order_management.py
"""
支付宝-小程序 订单管理 接口自动化测试

测试用例：
  测试用例1: 申请修改结算单（2步：API调用 + 善后SQL修正结算单状态）
  测试用例2: 修改归还物流信息（动态生成物流单号）
  测试用例3-7: 按不同状态查询订单数（参数化执行）

所有接口均需在请求头中添加 channelid=008
"""
import sys
import os
# 添加项目根目录到 Python 路径（解决右键运行时的模块导入问题）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case
from utils.data_generator import generate_test_data
from utils.data_loader import get_test_data, get_global_variables

_DATA_FILE = "data/Ali_app/api/ali_app_order_management.yaml"


# ==================== 模块级：请求头初始化（仅执行一次） ====================
@pytest.fixture(scope="module", autouse=True)
def _setup_channel_header_module(merchant_api_client):
    """模块级别 fixture：全文件仅执行一次，初始化 session 级请求头，后续所有测试复用"""
    merchant_api_client.session.headers["channelid"] = "008"
    merchant_api_client.session.headers["Content-Type"] = "application/json"
    logger.info("已添加请求头: channelid=008, Content-Type=application/json（模块级，仅初始化一次）")


# ==================== 测试用例1-2：复杂场景（Class 组织） ====================
@allure.epic("支付宝-小程序")
@allure.feature("支付宝-小程序订单管理")
@allure.story("订单操作相关接口")
class TestAliAppOrderOperations:
    """测试用例1: 申请修改结算单 → 善后修正 | 测试用例2: 修改归还物流信息"""

    _global_vars = None
    _order_id_for_1 = None
    _order_id_for_2 = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    # ==================== 测试用例1：申请修改结算单 ====================
    @pytest.mark.order(1)
    @allure.title("ALI_ORDER_001 - 申请修改结算单")
    def test_step1_modify_settlement(self, merchant_api_client, db):
        case = get_test_data(_DATA_FILE, "step1_modify_settlement")
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")
        execute_test_case(case, merchant_api_client, db, global_vars)
        order_id = case["json"]["orderId"]
        if order_id:
            self.__class__._order_id_for_1 = order_id
            allure.attach(str(order_id), name="order_id", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"[ALI_ORDER_001] 修改结算单成功，order_id={order_id}")

    # ==================== 测试用例1：善后修正结算单状态 ====================
    @pytest.mark.order(2)
    @allure.title("ALI_ORDER_001 - 善后修正结算单状态（04→01）")
    def test_step2_1_settlement(self, db):
        order_id = self._order_id_for_1
        if not order_id:
            skip_msg = "未获取到步骤1的order_id，跳过善后步骤"
            logger.warning(skip_msg)
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)
        cleanup_sql = (
            f"UPDATE llxz_order.ct_order_settlement "
            f"SET settlement_status = '01' "
            f"WHERE order_id = '{order_id}'"
        )
        with allure.step("执行善后SQL：修正结算单状态 04→01"):
            allure.attach(cleanup_sql, name="善后SQL", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"执行善后SQL: {cleanup_sql}")
            db.execute_update(cleanup_sql)
            logger.info(f"[ALI_ORDER_001] 善后完成：order_id={order_id}")

    # ==================== 测试用例2：修改归还物流信息 ====================
    @pytest.mark.order(3)
    @allure.title("ALI_ORDER_002 - 修改归还物流信息")
    def test_step2_update_back_express(self, merchant_api_client, db):
        case = get_test_data(_DATA_FILE, "step2_update_back_express")
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")
        logistics_no = generate_test_data("logistics_no")
        global_vars["logistics_no"] = logistics_no
        logger.info(f"动态生成物流单号: {logistics_no}")
        execute_test_case(case, merchant_api_client, db, global_vars)
        logger.info(f"[ALI_ORDER_002] 修改归还物流信息成功，物流单号={logistics_no}")
        order_id = case["json"]["orderId"]
        if order_id:
            self.__class__._order_id_for_2 = order_id
            allure.attach(str(order_id), name="order_id", attachment_type=allure.attachment_type.TEXT)

    # ==================== 测试用例2：善后修正结算单状态 ====================
    @pytest.mark.order(4)
    @allure.title("ALI_ORDER_002 - 善后修正结算单状态（04→01）")
    def test_step2_2_settlement(self, db):
        order_id = self._order_id_for_2
        if not order_id:
            skip_msg = "未获取到步骤2的order_id，跳过善后步骤"
            logger.warning(skip_msg)
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)
        cleanup_sql = (
            f"UPDATE llxz_order.ct_order_settlement "
            f"SET settlement_status = '01' "
            f"WHERE order_id = '{order_id}'"
        )
        with allure.step("执行善后SQL：修正结算单状态 04→01"):
            allure.attach(cleanup_sql, name="善后SQL", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"执行善后SQL: {cleanup_sql}")
            db.execute_update(cleanup_sql)
            logger.info(f"[ALI_ORDER_002] 善后完成：order_id={order_id}")


# ==================== 测试用例3-7：参数化查询 ====================
@allure.epic("支付宝-小程序")
@allure.feature("支付宝-小程序订单管理")
@allure.story("按状态查询订单数")
class TestAliAppOrderQueryByStatus:
    """按不同订单状态查询订单数（参数化）"""

    @pytest.mark.parametrize("case", get_test_data(_DATA_FILE, "order_query_cases"),
                             ids=lambda c: f"{c.get('case_id', '?')} | {c.get('title', '?')}")
    @allure.title("{case[case_id]} | {case[title]}")
    def test_order_query_by_status(self, case, merchant_api_client, db):
        global_vars = get_global_variables(_DATA_FILE).copy()
        execute_test_case(case, merchant_api_client, db, global_vars)
        logger.info(f"[{case.get('case_id')}] 测试通过")
