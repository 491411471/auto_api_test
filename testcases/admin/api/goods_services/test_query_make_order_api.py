# testcases/admin/api/goods_services/test_query_make_order_api.py
"""
运营端 - 订单管理：质选服务查询接口测试

接口：POST /hzsx/ope/order/queryOpeMakeOrderList
覆盖场景：无查询条件、商品品种、商品名称、商户ID、支付时间范围、订单号、复合查询

数据策略：模块级参数化，YAML 驱动请求参数与断言
空数据策略：当 records 为空且 httpStatus=200 时跳过测试，写入 Allure 报告
"""
import json
from datetime import datetime, timedelta

import allure
import pytest

from common.logger import logger
from common.test_helpers import (
    replace_placeholders,
    validate_response,
    _extract_response_vars,
)
from utils.assert_utils import assert_status_code
from utils.data_loader import get_test_data, get_global_variables


_DATA_FILE = "data/admin/api/goods_services/query_make_order_api.yaml"


@allure.epic("运营端")
@allure.feature("运营端-订单管理")
@allure.story("质选服务查询")
class TestQueryMakeOrder:
    """质选服务查询 - 7 个查询场景"""

    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    @staticmethod
    def _add_dynamic_time_vars(global_vars: dict) -> dict:
        """动态计算支付时间范围并注入变量：
        payment_time_start = 30 天前（YYYY-MM-DD）
        payment_time_end   = 今天（YYYY-MM-DD）
        create_date_start  = payment_time_start 前一天（ISO 格式）
        create_date_end    = payment_time_end 前一天（ISO 格式）
        """
        now = datetime.now()
        past_30 = now + timedelta(days=-30)

        # 支付时间范围：使用日期+时间（开始时分秒为当天 00:00:00，结束为当天 23:59:59）
        # 这样可以和接口返回的带时间戳的 paymentTime 字符串直接比较（all_between 使用字符串或数值比较）
        global_vars["payment_time_start"] = past_30.strftime("%Y-%m-%d 00:00:00")
        global_vars["payment_time_end"] = now.strftime("%Y-%m-%d 23:59:59")

        # createDate 是支付日期前一天（ISO 格式，与前端传参一致）
        global_vars["create_date_start"] = (past_30 + timedelta(days=-1)).strftime("%Y-%m-%dT16:00:00.000Z")
        global_vars["create_date_end"] = (now + timedelta(days=-1)).strftime("%Y-%m-%dT16:00:00.000Z")

        return global_vars

    @pytest.mark.parametrize(
        "case",
        get_test_data(_DATA_FILE, "make_order_query_tests"),
        ids=[c["case_id"] for c in get_test_data(_DATA_FILE, "make_order_query_tests")],
    )
    def test_query_make_order(self, admin_api_client, db, case):
        # 1. 加载全局变量
        global_vars = self._load_global_vars()

        # 2. 合并用例级别变量（如果有）
        if "variables" in case and isinstance(case["variables"], dict):
            global_vars.update(case["variables"])

        # 3. 动态注入时间范围变量（用于支付时间查询场景 MQ_005）
        global_vars = self._add_dynamic_time_vars(global_vars)

        # 4. 更新 Allure 标题
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")

        # 5. 变量替换
        case_replaced = replace_placeholders(case, global_vars)

        # 6. 发送查询请求
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

        # 7. 检查 records 是否为空（httpStatus=200 且 records 为空则跳过）
        records = (
            response_data.get("data", {})
            .get("backstageMakeOrderDtoList", {})
            .get("records", [])
        )
        if not records and resp.status_code == 200:
            skip_reason = (
                f"跳过原因：查询结果为空\n"
                f"用例ID：{case['case_id']}\n"
                f"请求参数：{json.dumps(body_data, ensure_ascii=False, default=str)}\n"
                f"HTTP 状态码：{resp.status_code}"
            )
            logger.warning(f"[跳过] {case['case_id']}: {skip_reason}")
            allure.attach(
                skip_reason, name="跳过原因",
                attachment_type=allure.attachment_type.TEXT,
            )
            pytest.skip(skip_reason)

        # 8. 执行断言验证
        with allure.step("执行断言验证"):
            assert_status_code(resp.status_code, case["expected_status"])
            validate_response(case, response_data, global_vars)

        # 9. 从响应中提取变量（如果配置了 extract_vars）
        _extract_response_vars(response_data, case.get("extract_vars"), global_vars)
