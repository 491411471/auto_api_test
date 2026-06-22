# testcases/admin/api/douyin_closed/test_douyin_closed_query_api.py
"""
运营端 - 抖音关单查询接口测试

接口：POST /hzsx/ope/order/queryOpeOrderByCondition
流程：前置SQL获取抖音渠道已关闭订单 → 按订单号查询 → 验证返回数据与SQL结果一致

用例列表：
  - DCQ_001: 验证订单号、下单人姓名和订单状态与SQL查询结果一致

执行流程：
  1. 前置SQL：查询抖音渠道(channel_provenance=2)已关闭(status=10)的订单
  2. 使用SQL返回的 order_id 调用查询接口
  3. 响应断言：验证 orderId、realName、status 与SQL查询结果一致
"""
import json

import allure
import pytest

from common.logger import logger
from common.test_helpers import (
    replace_placeholders,
    process_dynamic_data,
    validate_response,
)
from utils.assert_utils import assert_status_code
from utils.data_loader import get_test_data, get_global_variables


_DATA_FILE = "data/admin/api/douyin_closed/douyin_closed_query_api.yaml"


@allure.epic("运营端")
@allure.feature("运营端-订单管理")
@allure.story("抖音关单查询")
class TestDouyinClosedQuery:
    """抖音关单查询 - 验证订单号、下单人姓名和订单状态"""

    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    @pytest.mark.parametrize(
        "case",
        get_test_data(_DATA_FILE, "douyin_closed_query_tests"),
        ids=[c["case_id"] for c in get_test_data(_DATA_FILE, "douyin_closed_query_tests")],
    )
    def test_douyin_closed_query(self, admin_api_client, db, case):
        # ── 1. 加载并合并变量 ──
        global_vars = self._load_global_vars()
        if "variables" in case and isinstance(case["variables"], dict):
            global_vars.update(case["variables"])

        # ── 2. 更新 Allure 标题 ──
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")

        # ── 3. 第一次变量替换（全局变量 → 请求参数/SQL） ──
        case = replace_placeholders(case, global_vars)

        # ── 4. 执行前置 SQL 获取动态数据（order_id, user_name, status） ──
        try:
            process_dynamic_data(case, db, global_vars)
        except ValueError as e:
            if "SQL 无结果" in str(e):
                skip_msg = f"无符合条件的测试数据，跳过用例\n\n{e}"
                logger.warning(f"[无数据] {skip_msg}")
                allure.attach(skip_msg, name="跳过原因-无测试数据",
                              attachment_type=allure.attachment_type.TEXT)
                pytest.skip(skip_msg)
            raise

        # ── 5. 第二次变量替换（SQL 结果 → 请求参数占位符） ──
        case = replace_placeholders(case, global_vars)

        # ── 6. 发送 API 请求 ──
        endpoint = case.get("endpoint", "")
        body_data = case.get("json", {})
        with allure.step("发送查询请求"):
            allure.attach(
                json.dumps(body_data, ensure_ascii=False, indent=2, default=str),
                name="请求体 (JSON)", attachment_type=allure.attachment_type.JSON,
            )
            resp = admin_api_client.post(endpoint, json=body_data)
            response_data = resp.json()
            allure.attach(str(resp.status_code), name="HTTP 状态码",
                          attachment_type=allure.attachment_type.TEXT)
            allure.attach(
                json.dumps(response_data, ensure_ascii=False, indent=2, default=str),
                name="完整响应体", attachment_type=allure.attachment_type.JSON,
            )

        # ── 7. 响应断言 ──
        with allure.step("执行断言验证"):
            assert_status_code(resp.status_code, case["expected_status"])
            validate_response(case, response_data, global_vars)
