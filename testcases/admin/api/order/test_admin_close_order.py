# testcases/admin/api/order/test_admin_close_order.py
"""
运营端 - 订单列表：关闭订单接口测试

接口：POST /hzsx/ope/order/closeUserOrderAndRefundPrice

用例列表：
  - CO_001: 关闭订单并退款（closeType=07）

执行流程：
  1. 前置SQL：查询租用中(06)状态的订单号
  2. 调用关闭订单接口
  3. 响应断言：验证 rpcResult=SUCCESS、businessSuccess=true
  4. 后置SQL：验证订单状态变为10（关闭）
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


_DATA_FILE = "data/admin/api/order/admin_close_order.yaml"


@allure.epic("运营端")
@allure.feature("运营端-订单管理")
@allure.story("关闭订单")
class TestAdminCloseOrder:
    """关闭订单 - 关闭订单并退款"""

    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    @pytest.mark.parametrize(
        "case",
        get_test_data(_DATA_FILE, "admin_close_order_tests"),
        ids=[c["case_id"] for c in get_test_data(_DATA_FILE, "admin_close_order_tests")],
    )
    def test_close_order(self, admin_api_client, db, case):
        # ── 1. 加载并合并变量 ──
        global_vars = self._load_global_vars()
        if "variables" in case and isinstance(case["variables"], dict):
            global_vars.update(case["variables"])

        # ── 2. 提取后置配置 ──
        post_sql_case = {"post_sql": case.pop("post_sql")} if "post_sql" in case else None

        # ── 3. 更新 Allure 标题 ──
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")

        # ── 4. 第一次变量替换（全局变量 → 请求参数/SQL） ──
        case = replace_placeholders(case, global_vars)
        print("case", case)
        # ── 5. 执行前置 SQL 获取动态数据（orderId） ──
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

        # ── 8. 响应断言 ──
        assert_status_code(resp.status_code, case["expected_status"])
        validate_response(case, response_data, global_vars)

        # ── 9. 执行后置 SQL 验证（订单状态校验） ──
        if post_sql_case:
            process_post_operations(post_sql_case, db, global_vars)
