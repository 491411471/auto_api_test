"""
已分配订单列表查询接口测试用例
接口：/hzsx/business/order/queryOrderByCondition
对应页面：已分配订单列表页 -> 含“今日跟进状态”和“跟进人”筛选条件
测试策略：通过参数化方式加载 YAML 数据，覆盖筛选条件组合、字段完整性、分页等场景
空数据策略：AOL_006 当 records 为空且 httpStatus=200 时跳过测试，写入 Allure 报告
"""
import json

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
@allure.epic("商家端")
@allure.feature("商家端-订单分配")
@allure.story("已分配订单列表查询")
class TestAssignedOrderList:
    """
    已分配订单列表查询接口测试
    覆盖场景：
      - AOL_001: 正向查询已分配订单列表（无筛选）
      - AOL_002: 按今日跟进状态筛选（未跟进）
      - AOL_003: 按今日跟进状态筛选（已跟进）
      - AOL_004: 按跟进人筛选
      - AOL_005: 组合筛选（跟进状态+跟进人）
      - AOL_006: 验证列表字段完整性
    """
    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("assigned_order_list_api.yaml")
        return cls._global_vars.copy()

    @pytest.mark.smoke
    @pytest.mark.parametrize(
        "case",
        get_test_data("assigned_order_list_api.yaml", "assigned_order_list_tests"),
        ids=lambda case: case['case_id']
    )
    def test_assigned_order_list(self, api_client, db, case):
        """参数化执行已分配订单列表查询接口测试用例"""
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")

        # 当用例配置了 skip_on_empty_records 时，使用手动流程以支持空结果跳过
        if case.get('skip_on_empty_records'):
            # 1. 变量替换
            case_replaced = replace_placeholders(case, global_vars)

            # 2. 发送查询请求
            endpoint = case_replaced.get("endpoint", "")
            body_data = case_replaced.get("json", {})
            with allure.step("发送查询请求"):
                allure.attach(
                    json.dumps(body_data, ensure_ascii=False, indent=2, default=str),
                    name="请求体 (JSON)", attachment_type=allure.attachment_type.JSON,
                )
                resp = api_client.post(endpoint, json=body_data)
                response_data = resp.json()
                allure.attach(str(resp.status_code), name="HTTP 状态码",
                              attachment_type=allure.attachment_type.TEXT)
                allure.attach(
                    json.dumps(response_data, ensure_ascii=False, indent=2, default=str),
                    name="完整响应体", attachment_type=allure.attachment_type.JSON,
                )

            # 3. 检查 records 是否为空（httpStatus=200 且 records 为空则跳过）
            records = response_data.get("data", {}).get("records", [])
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

            # 4. 执行断言验证
            with allure.step("执行断言验证"):
                assert_status_code(resp.status_code, case["expected_status"])
                validate_response(case, response_data, global_vars)

            # 5. 提取变量
            _extract_response_vars(response_data, case.get("extract_vars"), global_vars)
        else:
            execute_test_case(case, api_client, db, global_vars)
