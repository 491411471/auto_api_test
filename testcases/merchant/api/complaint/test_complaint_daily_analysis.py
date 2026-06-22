# testcases/merchant/api/complaint/test_complaint_daily_analysis.py
"""
投诉分析 - 近7天每日投诉订单数量验证（总数/内容/外部）
3 个 SQL 维度（投诉总数 / 内部投诉 / 外部投诉）× 7 天 = 21 个参数化用例
API 响应仅调用一次并缓存，逐日逐字段与数据库 COUNT 进行一致性校验
"""
import copy
import json
import os
from datetime import datetime, timedelta

import allure
import pytest
import yaml

from common.logger import logger
from common.test_helpers import (
    execute_sql,
    replace_placeholders,
    validate_response,
)
from utils.assert_utils import assert_status_code


# ==================== 加载 YAML ====================
yaml_path = os.path.join(
    os.path.dirname(__file__),
    "../../../../data/merchant/api/complaint/complaint_daily_analysis.yaml"
)
with open(yaml_path, 'r', encoding='utf-8') as f:
    _config = yaml.safe_load(f)

_api_config = _config.get("api_config", {})
_cases = _config.get("complaint_daily_analysis_tests", [])


# ==================== 动态生成近 7 天日期参数 ====================
_TODAY = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
_DAYS_BACK = 6  # 含首尾共 7 天
_DATES = [_TODAY - timedelta(days=i) for i in range(_DAYS_BACK, -1, -1)]

# 构建参数化列表：3 个 SQL 用例 × 7 天 = 21 个测试点
# 每项为 (用例索引, 日期字符串)
_params = []
_param_ids = []
for _ci, _case in enumerate(_cases):
    _api_field = _case.get('api_field', 'unknown')
    for _d in _DATES:
        _day_str = _d.strftime("%Y-%m-%d")
        _params.append((_ci, _day_str))
        _param_ids.append(f"{_api_field}-{_day_str}")


# ==================== 模块级 API 响应缓存 ====================
# 21 个参数化用例共享同一份 API 响应，避免重复调用接口
_api_response_cache: dict = {}


def _call_api(merchant_api_client, variables):
    """调用投诉分析接口，执行基础断言，返回响应 JSON"""
    api_replaced = replace_placeholders(_api_config, variables)
    endpoint = api_replaced.get('endpoint', '')
    params = api_replaced.get('params', {})

    allure.attach(
        json.dumps({"endpoint": endpoint, "params": params}, ensure_ascii=False, indent=2),
        name="API 请求参数",
        attachment_type=allure.attachment_type.JSON
    )

    resp = merchant_api_client.post(endpoint, json=params)
    logger.info(f"投诉分析接口响应状态码: {resp.status_code}")
    assert_status_code(resp.status_code, _api_config.get('expected_status', 200))

    response_data = resp.json()

    # 基础断言：rpcResult / businessSuccess
    validate_response(_api_config, response_data, variables)

    allure.attach(
        json.dumps(response_data, ensure_ascii=False, indent=2)[:5000],
        name="API 完整响应",
        attachment_type=allure.attachment_type.JSON
    )
    return response_data

@allure.epic("商家端")
@allure.feature("数据报表")
@allure.story("投诉分析 - 近7天每日投诉数量")
class TestComplaintDailyAnalysis:
    """
    近7天每日投诉订单数量校验
    每个 SQL 用例对应一个 API 响应字段，逐日比对数据库 COUNT 与接口返回值
    """

    @pytest.mark.parametrize(
        "case_idx, day",
        _params,
        ids=_param_ids
    )
    def test_daily_complaint_count(self, case_idx, day, merchant_api_client, db, global_vars):
        """逐日逐字段校验：SQL COUNT vs API 响应字段"""
        case = _cases[case_idx].copy()
        api_field = case.get('api_field', 'complaintsCount')
        case_id = case.get('case_id', f'CDA_{case_idx:03d}')

        allure.dynamic.title(f"{case_id} | {case.get('title', '')} - {day}")
        allure.dynamic.description(
            f"用例ID: {case_id}\n"
            f"校验日期: {day}\n"
            f"API 字段: {api_field}\n"
            f"描述: {case.get('description', '')}"
        )

        # ---- 合并全局变量 + YAML 私有变量 ----
        variables = global_vars.copy()
        case_vars = _config.get("variables", {})
        variables.update(case_vars)

        # ---- 注入动态日期范围 ----
        start_time = (_TODAY - timedelta(days=_DAYS_BACK)).strftime("%Y-%m-%d 00:00:00")
        end_time = _TODAY.strftime("%Y-%m-%d 23:59:59")
        variables['start_time'] = start_time
        variables['end_time'] = end_time

        # ---- API 响应缓存（首次执行时调用，后续复用） ----
        if 'response' not in _api_response_cache:
            with allure.step("调用投诉分析接口（全量7天数据，仅执行一次）"):
                _api_response_cache['response'] = _call_api(merchant_api_client, variables)

        response_data = _api_response_cache['response']

        # ---- 当前日期参数 ----
        day_date = datetime.strptime(day, "%Y-%m-%d")
        day_start = day_date.strftime("%Y-%m-%d 00:00:00")
        day_end = day_date.strftime("%Y-%m-%d 23:59:59")

        # ---- 执行每日 SQL 查询 ----
        daily_sql_config = copy.deepcopy(case.get('daily_sql', {}))
        variables['day_start'] = day_start
        variables['day_end'] = day_end
        sql_replaced = replace_placeholders(daily_sql_config, variables)

        with allure.step(f"执行 {day} 的 SQL 查询（{case.get('title', '')}）"):
            allure.attach(
                sql_replaced.get('query', ''),
                name="替换后 SQL",
                attachment_type=allure.attachment_type.TEXT
            )
            sql_count = execute_sql(db, sql_replaced)

        # ---- 从 API 响应中匹配当前日期记录 ----
        api_data_list = response_data.get('data', [])
        day_record = next((r for r in api_data_list if r.get('everyDay', '').startswith(day)),None)

        # ---- 断言：SQL COUNT == API 字段值 ----
        with allure.step(f"校验 {day}：{api_field} vs 数据库 COUNT"):
            allure.attach(
                f"日期: {day}\n用例: {case_id}\nAPI字段: {api_field}",
                name="校验上下文",
                attachment_type=allure.attachment_type.TEXT
            )

            if day_record is None:
                pytest.fail(f"API 响应中未找到 {day} 对应的数据记录")

            api_value = day_record.get(api_field)

            allure.attach(
                json.dumps({
                    "date": day,
                    "case_id": case_id,
                    "api_field": api_field,
                    f"api_{api_field}": api_value,
                    "db_complaint_total_num": sql_count,
                    "everyDay": day_record.get('everyDay'),
                }, ensure_ascii=False, indent=2),
                name="校验详情",
                attachment_type=allure.attachment_type.JSON
            )

            assert api_value == sql_count, (
                f"[{case_id}] {day}: API {api_field}({api_value}) != SQL COUNT({sql_count})"
            )
            logger.info(f"[{case_id}] {day}: 校验通过 {api_field}={api_value}")
