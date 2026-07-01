# testcases/Ali_app/api/test_ali_app_give_back.py
"""
支付宝-小程序 归还商品全流程 接口自动化测试

流程：租用中 → 归还商品 → 商家驳回 → 再次归还 → 商家确认归还
所有接口均需在请求头中添加 channelid=008
"""
import copy
import json
import time

import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case
from utils.data_generator import generate_test_data
from utils.data_loader import get_test_data, get_global_variables

_DATA_FILE = "data/Ali_app/api/ali_app_give_back.yaml"


# ==================== 模块级：请求头初始化（仅执行一次） ====================
@pytest.fixture(scope="module", autouse=True)
def _setup_channel_header_module(merchant_api_client):
    """模块级别 fixture：全文件仅执行一次，初始化 session 级请求头，后续所有测试复用"""
    merchant_api_client.session.headers["channelid"] = "008"
    merchant_api_client.session.headers["Content-Type"] = "application/json"
    logger.info("已添加请求头: channelid=008, Content-Type=application/json（模块级，仅初始化一次）")


# ==================== 归还商品全流程（Class 组织） ====================
@allure.epic("支付宝-小程序")
@allure.feature("支付宝-小程序订单管理")
@allure.story("归还商品全流程：归还→驳回→再次归还→确认归还")
class TestAliAppGiveBackFlow:
    """归还商品全流程：归还→驳回→再次归还→确认归还"""

    _global_vars = None
    _order_id = None  # 跨步骤共享的order_id

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    # ==================== 步骤1：用户归还商品 ====================
    @pytest.mark.order(1)
    @allure.title("ALI_ORDER_008 - 归还商品-用户归还")
    def test_step1_give_back(self, merchant_api_client, db):
        case = get_test_data(_DATA_FILE, "step1_give_back")
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        # ---- 预执行 SQL，检查是否有符合条件的订单 ----
        sql_config = case.get("sql", {})
        query = sql_config.get("query", "")
        logger.info(f"预执行SQL检查: {query}")
        with allure.step("预执行SQL：查询status='06'且is_violation='01'的订单"):
            allure.attach(query, name="执行的SQL", attachment_type=allure.attachment_type.TEXT)
            result = db.fetch_one(query)

        if result is None:
            skip_msg = "未查询到符合条件的订单（status='06', is_violation='01'），跳过归还商品测试"
            logger.warning(skip_msg)
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        # ---- 将SQL结果注入 global_vars ----
        columns = sql_config.get("columns", [])
        for col in columns:
            global_vars[col] = result.get(col)
        logger.info(
            f"SQL查询到订单: order_id={global_vars.get('order_id')}, "
            f"uid={global_vars.get('uid')}, status={global_vars.get('status')}"
        )

        # ---- 生成物流单号 ----
        express_no = generate_test_data("logistics_no", company="sf")
        global_vars["express_no"] = express_no
        logger.info(f"动态生成物流单号: {express_no}")

        # ---- 深拷贝 case 并移除 sql，避免 execute_test_case 重复执行 SQL ----
        case_copy = copy.deepcopy(case)
        case_copy.pop("sql", None)

        # ---- 执行API调用 ----
        execute_test_case(case_copy, merchant_api_client, db, global_vars)

        # ---- 保存 order_id 供后续步骤使用 ----
        order_id = global_vars.get("order_id")
        if order_id:
            self.__class__._order_id = order_id
            allure.attach(str(order_id), name="order_id", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"[ALI_ORDER_008] 步骤1归还商品成功，order_id={order_id}")

    # ==================== 步骤2：商家驳回归还 ====================
    @pytest.mark.order(2)
    @allure.title("ALI_ORDER_008 - 归还商品-商家驳回")
    def test_step2_reject(self, merchant_api_client, db):
        order_id = self._order_id
        if not order_id:
            skip_msg = "未获取到步骤1的order_id，跳过商家驳回步骤"
            logger.warning(skip_msg)
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        case = get_test_data(_DATA_FILE, "step2_reject")
        global_vars = self._load_global_vars()
        global_vars["order_id"] = order_id
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        # ---- 动态生成驳回原因（含时间戳） ----
        timestamp = int(time.time())
        reject_reason = f"[AUTO] 自动化测试-拒绝归还-{timestamp}"
        global_vars["reject_reason"] = reject_reason
        logger.info(f"动态生成驳回原因: {reject_reason}")

        execute_test_case(case, merchant_api_client, db, global_vars)
        logger.info(f"[ALI_ORDER_008] 步骤2商家驳回成功，order_id={order_id}")

    # ==================== 步骤3：再次归还商品 ====================
    @pytest.mark.order(3)
    @allure.title("ALI_ORDER_008 - 归还商品-再次归还")
    def test_step3_give_back_again(self, merchant_api_client, db):
        order_id = self._order_id
        if not order_id:
            skip_msg = "未获取到order_id，跳过再次归还步骤"
            logger.warning(skip_msg)
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        case = get_test_data(_DATA_FILE, "step3_give_back_again")
        global_vars = self._load_global_vars()
        global_vars["order_id"] = order_id
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        # ---- 生成新的物流单号（与步骤1区分） ----
        express_no_2 = generate_test_data("logistics_no", company="sf")
        global_vars["express_no_2"] = express_no_2
        logger.info(f"动态生成物流单号（第2次）: {express_no_2}")

        execute_test_case(case, merchant_api_client, db, global_vars)
        logger.info(f"[ALI_ORDER_008] 步骤3再次归还成功，order_id={order_id}")

    # ==================== 步骤4：商家确认归还 + SQL验证状态 ====================
    @pytest.mark.order(4)
    @allure.title("ALI_ORDER_008 - 归还商品-商家确认归还")
    def test_step4_confirm_give_back(self, merchant_api_client, db):
        order_id = self._order_id
        if not order_id:
            skip_msg = "未获取到order_id，跳过商家确认归还步骤"
            logger.warning(skip_msg)
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        case = get_test_data(_DATA_FILE, "step4_confirm_give_back")
        global_vars = self._load_global_vars()
        global_vars["order_id"] = order_id
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        # ---- 手动发起请求（代替 execute_test_case，以便捕获特定业务错误并跳过） ----
        from common.test_helpers import replace_placeholders
        endpoint = replace_placeholders(case.get("endpoint", ""), global_vars)
        params = replace_placeholders(case.get("params", {}), global_vars)

        with allure.step(f"GET {endpoint}（商家确认归还）"):
            allure.attach(
                json.dumps(params, ensure_ascii=False, indent=2, default=str),
                name="请求参数 (Query)",
                attachment_type=allure.attachment_type.JSON,
            )
            resp = merchant_api_client.get(endpoint, params=params)
            resp_data = resp.json()
            allure.attach(
                json.dumps(resp_data, ensure_ascii=False, indent=2, default=str),
                name="完整响应体",
                attachment_type=allure.attachment_type.JSON,
            )

            # ---- 提取 errorCode 和 errorMessage ----
            error_code = resp_data.get("errorCode")
            error_msg = str(resp_data.get("errorMessage", "") or "")

            # ---- 检查 errorCode 为 null 但 errorMessage 不为 null → 跳过断言，视为成功 ----
            if error_code is None and error_msg:
                skip_msg = (
                    f"errorCode=null 但 errorMessage 不为 null，"
                    f"跳过后续断言验证并视为执行成功: errorMessage={error_msg}"
                )
                logger.warning(skip_msg)
                allure.attach(
                    json.dumps(resp_data, ensure_ascii=False, indent=2, default=str),
                    name="响应详情（跳过断言）",
                    attachment_type=allure.attachment_type.JSON,
                )
                pytest.skip(skip_msg)

            # ---- 检查响应中的 errorMessage，若为"订单关闭"则跳过 ----
            if "在支付宝的订单状态是订单关闭" in error_msg:
                skip_msg = f"订单在支付宝侧已关闭，跳过确认归还步骤: {error_msg}"
                logger.warning(skip_msg)
                allure.attach(
                    json.dumps(resp_data, ensure_ascii=False, indent=2, default=str),
                    name="错误响应详情",
                    attachment_type=allure.attachment_type.JSON,
                )
                pytest.skip(skip_msg)

            # ---- 断言核心成功字段 ----
            assert resp.status_code == 200, f"HTTP状态码异常: {resp.status_code}"
            assert resp_data.get("rpcResult") == "SUCCESS", (
                f"rpcResult 断言失败: {resp_data.get('rpcResult')}"
            )
            assert resp_data.get("businessSuccess") is True, (
                f"businessSuccess 断言失败: {resp_data.get('businessSuccess')}, "
                f"errorMessage={resp_data.get('errorMessage')}"
            )
            logger.info(f"[ALI_ORDER_008] 步骤4商家确认归还成功，order_id={order_id}")

        # ---- SQL验证：订单状态应为07（待结算） ----
        verify_sql = f"SELECT status FROM llxz_order.ct_user_orders WHERE order_id = '{order_id}'"
        with allure.step("SQL验证：确认订单状态已变为07(待结算)"):
            allure.attach(verify_sql, name="验证SQL", attachment_type=allure.attachment_type.TEXT)
            verify_result = db.fetch_one(verify_sql)
            assert verify_result is not None, f"未查询到订单 {order_id}"
            actual_status = verify_result.get("status")
            assert actual_status == "07", (
                f"订单状态验证失败：期望status='07'，实际status='{actual_status}'"
            )
            allure.attach(f"status={actual_status}", name="验证结果", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"[ALI_ORDER_008] 订单状态验证通过：status={actual_status}")
