# testcases/admin/api/insurance_order/test_picc_insurance_order.py
"""
运营端 - 订单管理：投保订单查询与操作测试

查询接口：POST /hzsx/ope/picc/queryLogPage
操作接口：
  - 修改险种: POST /hzsx/ope/picc/updateLog
  - 取消投保: POST /hzsx/ope/picc/cancelInsured
  - 分配投保: POST /hzsx/ope/picc/selectInsurance

数据流：
  TC01（空条件查询）→ 提取 dynamic_order_id, dynamic_record_id
  TC03 → 使用 dynamic_order_id 按订单号查询
  TC04 → 提取 status_order_id（投保中订单）
  OP01 → 使用 dynamic_record_id 修改险种
  OP02 → 使用 status_order_id 取消投保
  OP03 → 实时查询投保中订单 → 分配投保
"""
import json
from datetime import datetime, timedelta

import allure
import pytest

from common.logger import logger
from common.test_helpers import (
    execute_test_case,
    replace_placeholders,
    validate_response,
    _extract_response_vars,
)
from utils.assert_utils import assert_status_code
from utils.data_loader import get_test_data, get_global_variables
from utils.variable_utils import validate, get_value_by_path


_QUERY_FILE = "data/admin/api/insurance_order/picc_insurance_query.yaml"
_OP_FILE = "data/admin/api/insurance_order/picc_insurance_operation.yaml"


def _get_case(data_file: str, key: str, case_id: str) -> dict:
    """从指定 YAML 文件中按 case_id 获取用例数据"""
    cases = get_test_data(data_file, key)
    for case in cases:
        if case["case_id"] == case_id:
            return case
    raise ValueError(f"未找到 case_id={case_id} (file={data_file}, key={key})")


@allure.epic("运营端")
@allure.feature("运营端-订单管理")
@allure.story("投保订单")
class TestPiccInsuranceOrder:
    """投保订单 - 查询（8 场景）+ 操作（3 步骤）"""

    _query_vars = None
    _op_vars = None

    # 跨步骤共享：TC01 提取 → TC03 / OP01 使用
    _extracted_order_id = None
    _extracted_record_id = None
    # TC04 提取 → OP02 使用
    _status_order_id = None

    @classmethod
    def _load_query_vars(cls):
        if cls._query_vars is None:
            cls._query_vars = get_global_variables(_QUERY_FILE)
        return cls._query_vars.copy()

    @classmethod
    def _load_op_vars(cls):
        if cls._op_vars is None:
            cls._op_vars = get_global_variables(_OP_FILE)
        return cls._op_vars.copy()

    @staticmethod
    def _add_dynamic_time_vars(gv: dict) -> dict:
        """动态计算创建时间范围（最近30天）并注入变量"""
        now = datetime.now()
        past_30 = now + timedelta(days=-30)
        gv["begin_date"] = past_30.strftime("%Y-%m-%d 00:00:00")
        gv["end_date"] = now.strftime("%Y-%m-%d 23:59:59")
        gv["create_date_start"] = (past_30 + timedelta(days=-1)).strftime("%Y-%m-%dT16:00:00.000Z")
        gv["create_date_end"] = (now + timedelta(days=-1)).strftime("%Y-%m-%dT16:00:00.000Z")
        return gv

    # ==================== 步骤1：TC01 空条件查询 + 提取数据 ====================
    @pytest.mark.order(1)
    @allure.title("IOQ_001 | 空条件查询投保订单")
    def test_query_extract(self, admin_api_client, db):
        """空条件查询投保订单，提取 orderId 和 id 供后续用例使用。
        如果没有查询到数据，则跳过全部依赖数据的测试。
        """
        case = _get_case(_QUERY_FILE, "picc_query_tests", "IOQ_001")

        # 1. 加载变量
        global_vars = self._load_query_vars()

        # 2. 变量替换
        case_replaced = replace_placeholders(case, global_vars)

        # 3. 手动发送请求（便于在断言前检查空数据并跳过）
        endpoint = case_replaced.get("endpoint", "")
        body_data = case_replaced.get("json", {})
        with allure.step("发送查询请求（空条件）"):
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
                validate(actual, check["operator"], check["value"], path)

        # 5. 检查空数据
        records = (
            response_data.get("data", {})
            .get("piccInsurenceLogDtoList", {})
            .get("records", [])
        )
        if not records:
            skip_msg = "投保订单列表为空，无可用测试数据，跳过后续测试"
            logger.warning(f"[跳过] {skip_msg}")
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        # 6. 提取变量（对应 YAML 中 extract_vars 配置）
        self.__class__._extracted_order_id = records[0]["orderId"]
        self.__class__._extracted_record_id = records[0]["id"]
        logger.info(
            f"提取 dynamic_order_id={self._extracted_order_id}, "
            f"dynamic_record_id={self._extracted_record_id}"
        )
        allure.attach(
            f"dynamic_order_id: {self._extracted_order_id}\n"
            f"dynamic_record_id: {self._extracted_record_id}",
            name="提取的变量（extract_vars）", attachment_type=allure.attachment_type.TEXT,
        )

    # ==================== 步骤2：TC02-TC08 参数化条件查询 ====================
    @pytest.mark.order(2)
    @pytest.mark.parametrize(
        "case",
        [c for c in get_test_data(_QUERY_FILE, "picc_query_tests") if c["case_id"] != "IOQ_001"],
        ids=[c["case_id"] for c in get_test_data(_QUERY_FILE, "picc_query_tests") if c["case_id"] != "IOQ_001"],
    )
    def test_query_conditions(self, admin_api_client, db, case):
        """TC02-TC08: 多种条件组合查询（渠道、订单号、投保状态、扣款状态、险种、时间、复合）"""
        global_vars = self._load_query_vars()
        global_vars = self._add_dynamic_time_vars(global_vars)

        # TC03 依赖 TC01 提取的 orderId
        if case["case_id"] == "IOQ_003":
            if not self.__class__._extracted_order_id:
                pytest.skip("TC01 未提取到 orderId，跳过 TC03")
            global_vars["dynamic_order_id"] = self.__class__._extracted_order_id

        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")

        # 变量替换
        case_replaced = replace_placeholders(case, global_vars)

        # 发送查询请求
        endpoint = case_replaced.get("endpoint", "")
        body_data = case_replaced.get("json", {})
        with allure.step("发送查询请求"):
            allure.attach(
                json.dumps(body_data, ensure_ascii=False, indent=2, default=str),
                name="请求体 (JSON)", attachment_type=allure.attachment_type.JSON,
            )
            resp = admin_api_client.post(endpoint, json=body_data)
            response_data = resp.json()
            allure.attach(str(resp.status_code), name="HTTP 状态码", attachment_type=allure.attachment_type.TEXT)
            allure.attach(
                json.dumps(response_data, ensure_ascii=False, indent=2, default=str),
                name="完整响应体", attachment_type=allure.attachment_type.JSON,
            )

        # 检查 records 是否为空（httpStatus=200 且 records 为空则跳过）
        records = (response_data.get("data", {}).get("piccInsurenceLogDtoList", {}).get("records", []))
        if not records and resp.status_code == 200:
            skip_reason = (
                f"跳过原因：查询结果为空\n"
                f"用例ID：{case['case_id']}\n"
                f"请求参数：{json.dumps(body_data, ensure_ascii=False, default=str)}\n"
                f"HTTP 状态码：{resp.status_code}"
            )
            logger.warning(f"[跳过] {case['case_id']}: {skip_reason}")
            allure.attach(skip_reason, name="跳过原因",attachment_type=allure.attachment_type.TEXT,)
            pytest.skip(skip_reason)

        # 执行断言验证
        with allure.step("执行断言验证"):
            assert_status_code(resp.status_code, case["expected_status"])
            validate_response(case, response_data, global_vars)

        # 从响应中提取变量
        _extract_response_vars(response_data, case.get("extract_vars"), global_vars)

        # TC04 执行后提取 status_order_id 供取消操作用
        if case["case_id"] == "IOQ_004":
            self.__class__._status_order_id = global_vars.get("status_order_id")
            if self.__class__._status_order_id:
                logger.info(f"TC04 提取 status_order_id={self._status_order_id}")
                allure.attach(
                    f"status_order_id: {self._status_order_id}",
                    name="TC04 提取的变量", attachment_type=allure.attachment_type.TEXT,
                )

    # ==================== 步骤3：OP01 修改险种 ====================
    @pytest.mark.order(3)
    @allure.title("IOP_001 | 修改险种")
    def test_op_modify_insurance(self, admin_api_client, db):
        """使用 TC01 提取的 record_id 修改险种为2(天安财险)"""
        if not self.__class__._extracted_record_id:
            pytest.skip("TC01 未提取到 record_id，跳过修改险种操作")

        case = _get_case(_OP_FILE, "picc_operation_tests", "IOP_001")
        global_vars = self._load_op_vars()
        global_vars["dynamic_record_id"] = self.__class__._extracted_record_id

        allure.attach(
            f"dynamic_record_id: {self._extracted_record_id}",
            name="注入的记录ID", attachment_type=allure.attachment_type.TEXT,
        )
        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== 步骤4：OP02 取消投保订单 ====================
    @pytest.mark.order(4)
    @allure.title("IOP_002 | 取消投保订单")
    def test_op_cancel_order(self, admin_api_client, db):
        """使用 TC04 提取的 status_order_id 取消投保订单"""
        if not self.__class__._status_order_id:
            pytest.skip("TC04 未提取到 status_order_id，跳过取消操作")

        case = _get_case(_OP_FILE, "picc_operation_tests", "IOP_002")
        global_vars = self._load_op_vars()
        global_vars["status_order_id"] = self.__class__._status_order_id

        allure.attach(
            f"status_order_id: {self._status_order_id}",
            name="注入的订单ID", attachment_type=allure.attachment_type.TEXT,
        )
        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== 步骤5：OP03 分配投保订单 ====================
    @pytest.mark.order(5)
    @allure.title("IOP_003 | 分配投保订单")
    def test_op_assign_order(self, admin_api_client, db):
        """查询投保中(status=1)的订单号，将其分配给险种1(人保)"""
        case = _get_case(_OP_FILE, "picc_operation_tests", "IOP_003")
        global_vars = self._load_op_vars()

        # 实时查询投保中的订单号
        with allure.step("查询投保中(status=1)的订单号"):
            query_body = {
                "pageNumber": 1,
                "pageSize": 10,
                "orderId": "",
                "status": 1,
                "beginDate": "",
                "endDate": "",
                "policySelectStart": "",
                "policySelectEnd": "",
            }
            allure.attach(
                json.dumps(query_body, ensure_ascii=False, indent=2),
                name="查询请求体", attachment_type=allure.attachment_type.JSON,
            )
            resp = admin_api_client.post("/hzsx/ope/picc/queryLogPage", json=query_body)
            resp_data = resp.json()
            allure.attach(
                json.dumps(resp_data, ensure_ascii=False, indent=2, default=str)[:3000],
                name="查询响应体", attachment_type=allure.attachment_type.JSON,
            )
            records = (
                resp_data.get("data", {})
                .get("piccInsurenceLogDtoList", {})
                .get("records", [])
            )
            if not records:
                skip_reason = (
                    f"跳过原因：查询结果为空\n"
                    f"说明：无投保中(status=1)的订单可供分配\n"
                    f"HTTP 状态码：{resp.status_code}"
                )
                logger.warning(f"[跳过] {skip_reason}")
                allure.attach(
                    skip_reason, name="跳过原因",
                    attachment_type=allure.attachment_type.TEXT,
                )
                pytest.skip(skip_reason)

            assign_order_id = records[0]["orderId"]
            global_vars["assign_order_id"] = assign_order_id
            logger.info(f"分配订单 orderId={assign_order_id}")
            allure.attach(
                f"assign_order_id: {assign_order_id}",
                name="注入的分配订单ID", attachment_type=allure.attachment_type.TEXT,
            )

        # 执行分配操作
        execute_test_case(case, admin_api_client, db, global_vars)
