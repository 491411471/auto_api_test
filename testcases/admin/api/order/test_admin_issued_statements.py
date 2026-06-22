# testcases/admin/api/order/test_admin_issued_statements.py
"""
运营端 - 订单列表：完结订单接口测试

接口：
  - POST /hzsx/business/order/merchantsIssuedStatements（完结申请）
  - POST /hzsx/order/completeApply/verifyOrderCompleteApply（审核通过/拒绝）

用例列表：
  - MIS_001: 状态完好完结订单（settlementType=01）
  - MIS_002: 状态损坏完结订单（settlementType=02）
  - MIS_003: 完结申请单--审核通过（status=01）
  - MIS_004: 完结申请单--审核拒绝（status=02）

执行流程：
  1. 前置SQL：查询可用订单号或申请ID
  2. 调用完结/审核接口
  3. 响应断言：验证 rpcResult=SUCCESS、businessSuccess=true
  4. 后置SQL：验证订单状态变为09

数据隔离：
  - MIS_001/002 通过 NOT IN + LIMIT offset 获取不同订单
  - MIS_003/004 各自获取待审核申请记录（审核后状态变更，自然隔离）
"""
import json

import allure
import pytest

from common.logger import logger
from common.test_helpers import (
    replace_placeholders,
    process_dynamic_data,
    validate_response,
    process_post_operations,
)
from utils.assert_utils import assert_status_code
from utils.data_loader import get_test_data, get_global_variables


_DATA_FILE = "data/admin/api/order/admin_issued_statements.yaml"


@allure.epic("运营端")
@allure.feature("运营端-订单管理")
@allure.story("完结订单")
class TestAdminIssuedStatements:
    """完结订单 - 完好完结、损坏完结、审核通过、审核拒绝
    _consumed_order_ids：类级别集合，记录已消费的订单号。
    参数化用例间共享，配合 NOT IN 条件防止不同用例使用相同订单。
    """
    _global_vars = None
    _consumed_order_ids: set = set()
    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()
    @pytest.mark.parametrize(
        "case",
        get_test_data(_DATA_FILE, "admin_issued_statements_tests"),
        ids=[c["case_id"] for c in get_test_data(_DATA_FILE, "admin_issued_statements_tests")],
    )
    def test_issued_statements(self, admin_api_client, db, case):
        # ── 1. 加载并合并变量 ──
        global_vars = self._load_global_vars()
        if "variables" in case and isinstance(case["variables"], dict):
            global_vars.update(case["variables"])

        # ── 2. 提取后置配置 ──
        skip_on = case.pop("skip_on", [])
        post_sql_case = {"post_sql": case.pop("post_sql")} if "post_sql" in case else None

        # ── 3. 更新 Allure 标题 ──
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")

        # ── 4. 第一次变量替换（全局变量 → 请求参数/SQL） ──
        case = replace_placeholders(case, global_vars)

        # ── 5. 执行前置 SQL 获取动态数据（applyId/orderId） ──
        try:
            process_dynamic_data(case, db, global_vars)
        except ValueError as e:
            if "SQL 无结果" in str(e):
                skip_msg = f"无符合条件的测试数据，跳过用例\n\n{e}"
                logger.warning(f"[无数据] {skip_msg}")
                allure.attach(skip_msg, name="跳过原因-无测试数据", attachment_type=allure.attachment_type.TEXT)
                pytest.skip(skip_msg)
            raise

        # ── 6. 第二次变量替换（SQL 结果 → 请求参数占位符） ──
        case = replace_placeholders(case, global_vars)

        # ── 7. 发送 API 请求 ──
        method = case.get("method", "POST").upper()
        endpoint = case.get("endpoint", "")
        body_data = case.get("json", {})
        allure.attach(
            json.dumps(body_data, ensure_ascii=False, indent=2, default=str),
            name="请求体 (JSON)", attachment_type=allure.attachment_type.JSON,
        )
        resp = admin_api_client.post(endpoint, json=body_data)

        response_data = resp.json()
        allure.attach(
            json.dumps(response_data, ensure_ascii=False, indent=2),
            name="完整响应体", attachment_type=allure.attachment_type.JSON,
        )

        # ── 8. 业务约束跳过检查（httpStatus=200 + errorMessage 匹配 skip_on） ──
        if skip_on and response_data.get("httpStatus") == 200:
            error_msg = response_data.get("errorMessage") or ""
            matched = next((kw for kw in skip_on if kw in error_msg), None)
            if matched:
                skip_reason = f"触发业务约束条件: {error_msg}"
                logger.info(f"[业务约束] {skip_reason}")
                allure.attach(
                    f"跳过原因: 触发业务约束条件（非技术错误）\n\n"
                    f"匹配关键词: {matched}\n"
                    f"错误信息: {error_msg}\n"
                    f"响应类型: {response_data.get('responseType', 'N/A')}\n\n"
                    f"说明: 这是正常的业务限制，不是接口故障",
                    name="用例跳过-业务约束",
                    attachment_type=allure.attachment_type.TEXT,
                )
                pytest.skip(skip_reason)

        # ── 9. 响应断言 ──
        assert_status_code(resp.status_code, case["expected_status"])
        validate_response(case, response_data, global_vars)

        # ── 10. 执行后置 SQL 验证（订单状态校验） ──
        if post_sql_case:
            process_post_operations(post_sql_case, db, global_vars)

