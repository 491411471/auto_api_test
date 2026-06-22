# testcases/admin/api/goods_services/test_cancel_make_order.py
"""
运营端 - 订单管理：质选服务取消测试

流程：
  1. 查询待支付(status=01)的质选服务单
  2. 从查询结果中选择第一条，取消该质选服务单
  3. 如果没有待支付的质选服务单，跳过测试

接口：
  - 查询: POST /hzsx/ope/order/queryOpeMakeOrderList
  - 取消: POST /hzsx/ope/order/updateOpeMakeOrder

变量传递：
  CMO_001 通过 extract_vars 配置提取 cancel_order_id，
  Python 代码从响应中读取并注入到 CMO_002 的变量中。
"""
import json

import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case, replace_placeholders
from utils.assert_utils import assert_status_code
from utils.data_loader import get_test_data, get_global_variables
from utils.variable_utils import validate, get_value_by_path


_DATA_FILE = "data/admin/api/goods_services/cancel_make_order.yaml"

# 预加载所有用例数据
_ALL_CASES = get_test_data(_DATA_FILE, "cancel_make_order_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 cancel_make_order.yaml")


def _get_case_by_id(case_id: str) -> dict:
    """根据 case_id 从用例列表中获取测试用例数据"""
    for case in _ALL_CASES:
        if case["case_id"] == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")


@allure.epic("运营端")
@allure.feature("运营端-订单管理")
@allure.story("质选服务取消")
class TestCancelMakeOrder:
    """取消质选服务单 - 查询待支付订单后取消"""

    _global_vars = None
    _cancel_order_id = None  # 类级别存储，跨测试方法共享（步骤1提取 → 步骤2使用）

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    # ==================== 步骤1：查询待支付的质选服务单 ====================
    @pytest.mark.order(1)
    @allure.title("CMO_001 | 查询待支付的质选服务单")
    def test_step1_query_pending_payment(self, admin_api_client, db):
        """步骤1：查询待支付的质选服务单，提取 orderId 供取消步骤使用。
        如果没有待支付的质选服务单，则跳过整个取消流程。
        """
        case = _get_case_by_id("CMO_001")
        allure.dynamic.description(case.get("description", ""))

        # 1. 加载并合并变量
        global_vars = self._load_global_vars()
        if "variables" in case and isinstance(case["variables"], dict):
            global_vars.update(case["variables"])

        # 2. 变量替换
        case_replaced = replace_placeholders(case, global_vars)

        # 3. 发送查询请求（手动发送，以便在断言前检查空数据并跳过）
        endpoint = case_replaced.get("endpoint", "")
        body_data = case_replaced.get("json", {})
        with allure.step("发送查询请求（status=01 待支付）"):
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

        # 4. 基础断言（HTTP 状态码 + 接口常规验证）
        with allure.step("执行基础断言"):
            assert_status_code(resp.status_code, case["expected_status"])
            for check in case["validate_data"]:
                path = check["path"].lstrip("$").lstrip(".")
                actual = get_value_by_path(response_data, path)
                validate(actual, check["operator"], check["value"], path)

        # 5. 检查是否有待支付订单，无则跳过
        records = (
            response_data.get("data", {})
            .get("backstageMakeOrderDtoList", {})
            .get("records", [])
        )
        if not records:
            skip_msg = "未查询到待支付(status=01)的质选服务单，跳过取消测试"
            logger.warning(f"[跳过] {skip_msg}")
            allure.attach(
                skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT
            )
            pytest.skip(skip_msg)

        # 6. 提取 orderId 供取消步骤使用（对应 YAML 中 extract_vars 配置）
        self.__class__._cancel_order_id = records[0]["orderId"]
        logger.info(f"提取到待取消的 orderId: {self.__class__._cancel_order_id}")
        allure.attach(
            f"cancel_order_id: {self.__class__._cancel_order_id}",
            name="提取的变量（extract_vars）", attachment_type=allure.attachment_type.TEXT,
        )

    # ==================== 步骤2：取消质选服务单 ====================
    @pytest.mark.order(2)
    @allure.title("CMO_002 | 取消质选服务单")
    def test_step2_cancel_order(self, admin_api_client, db):
        """步骤2：使用步骤1提取的 cancel_order_id 调用取消接口，验证取消操作成功。"""
        # 检查前置步骤是否获取到 orderId
        if not self.__class__._cancel_order_id:
            pytest.skip("前置查询未获取到 orderId，跳过取消操作")

        case = _get_case_by_id("CMO_002")
        allure.dynamic.description(case.get("description", ""))

        # 1. 加载变量并注入步骤1提取的 cancel_order_id
        global_vars = self._load_global_vars()
        global_vars["cancel_order_id"] = self.__class__._cancel_order_id

        allure.attach(
            f"cancel_order_id: {self.__class__._cancel_order_id}",
            name="注入的取消订单ID", attachment_type=allure.attachment_type.TEXT,
        )

        # 2. 执行测试（框架自动处理变量替换、API 请求、断言）
        execute_test_case(case, admin_api_client, db, global_vars)
