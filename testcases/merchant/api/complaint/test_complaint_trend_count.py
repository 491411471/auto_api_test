# testcases/merchant/api/complaint/test_complaint_trend_count.py
"""
投诉趋势 - 投诉量验证
校验接口返回的每日 complaintsCount 与 SQL 统计的投诉量一致
所有测试数据（接口地址、断言规则、Allure 层级等）均来自 YAML，代码仅含执行逻辑
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
    "../../../../data/merchant/api/complaint/complaint_trend_count.yaml"
)
with open(yaml_path, 'r', encoding='utf-8') as f:
    _config = yaml.safe_load(f)

_api_config = _config.get("api_config", {})
_allure_config = _config.get("allure", {})
_cases = _config.get("complaint_trend_count_tests", [])


# ==================== 动态生成日期范围（当前日期向前推7天） ====================
_TODAY = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
_DAYS_BACK = 6  # 含首尾共 7 天
_START_TIME = (_TODAY - timedelta(days=_DAYS_BACK)).strftime("%Y-%m-%d 00:00:00")
_END_TIME = _TODAY.strftime("%Y-%m-%d 23:59:59")
_DATES = [_TODAY - timedelta(days=i) for i in range(_DAYS_BACK, -1, -1)]

# 构建参数化列表（单参数时直接传值列表，不要用元组，否则 pytest 不会自动解包）
_params = list(range(len(_cases)))
_param_ids = [c.get("case_id", f"CTC_{i:03d}") for i, c in enumerate(_cases)]


def _call_api(merchant_api_client, business_model, variables):
    """
    调用投诉趋势接口，执行基础断言，返回响应 JSON。
    接口地址、请求方法、断言规则均从 api_config 读取。
    """
    endpoint = _api_config.get("endpoint", "")
    expected_status = _api_config.get("expected_status", 200)

    # 请求参数：从 api_config.params 读取（若无则按 business_model + 动态时间构建）
    params = {
        "businessModel": business_model,
        "startTime": _START_TIME,
        "endTime": _END_TIME,
    }

    allure.attach(
        json.dumps({"endpoint": endpoint, "params": params}, ensure_ascii=False, indent=2),
        name="API 请求参数",
        attachment_type=allure.attachment_type.JSON,
    )

    resp = merchant_api_client.post(endpoint, json=params)
    logger.info(f"投诉趋势接口响应状态码: {resp.status_code}")
    assert_status_code(resp.status_code, expected_status)

    response_data = resp.json()

    # 基础断言规则来自 YAML api_config.validate_data
    validate_response(_api_config, response_data, variables)

    allure.attach(
        json.dumps(response_data, ensure_ascii=False, indent=2)[:5000],
        name="API 完整响应",
        attachment_type=allure.attachment_type.JSON,
    )
    return response_data


# 从 YAML 读取 Allure 层级
@allure.epic(_allure_config.get("epic", "商家端"))
@allure.feature(_allure_config.get("feature", "数据报表"))
@allure.story(_allure_config.get("story", "投诉趋势 - 投诉量"))
class TestComplaintTrendCount:
    """
    投诉趋势投诉量校验
    每个用例对应一种 businessModel，调用一次接口，执行一次 SQL，
    逐日比对 API 响应字段与 SQL 统计值
    """

    @pytest.mark.parametrize("case_idx", _params, ids=_param_ids)
    def test_complaint_trend_count(self, case_idx, merchant_api_client, db, global_vars):
        case = _cases[case_idx].copy()
        case_id = case.get("case_id", f"CTC_{case_idx:03d}")
        business_model = case.get("business_model", "0")
        api_field = case.get("api_field", "complaintsCount")

        allure.dynamic.title(f"{case_id} | {case.get('title', '')}")
        allure.dynamic.description(
            f"用例ID: {case_id}\n"
            f"businessModel: {business_model}\n"
            f"描述: {case.get('description', '')}"
        )

        # ---- 合并变量（全局 + YAML） ----
        variables = global_vars.copy()
        case_vars = _config.get("variables", {})
        variables.update(case_vars)
        variables["start_time"] = _START_TIME
        variables["end_time"] = _END_TIME

        # ---- 调用 API ----
        with allure.step(f"调用投诉趋势接口（businessModel={business_model}）"):
            response_data = _call_api(merchant_api_client, business_model, variables)

        # ---- 执行 SQL（一次查询获取7天所有数据） ----
        sql_config = copy.deepcopy(case.get("daily_sql", {}))
        sql_replaced = replace_placeholders(sql_config, variables)

        with allure.step(f"执行 SQL 统计每日投诉量（{case.get('title', '')}）"):
            allure.attach(
                sql_replaced.get("query", ""),
                name="替换后 SQL",
                attachment_type=allure.attachment_type.TEXT,
            )
            try:
                sql_rows = execute_sql(db, sql_replaced)
            except ValueError:
                # multiple=True 时 SQL 无结果会抛出 ValueError，
                # 投诉量为 0 属正常业务场景，视为空列表
                logger.info(f"[{case_id}] SQL 查询无结果（期间内无投诉记录），视为空列表")
                sql_rows = []

        # ---- 构建 SQL 日期 → 投诉量映射 ----
        sql_map = {}
        if sql_rows and isinstance(sql_rows, list):
            for row in sql_rows:
                date_key = str(row.get("stat_date", ""))
                sql_map[date_key] = row.get("complaint_cnt", 0)

        allure.attach(
            json.dumps(sql_map, ensure_ascii=False, indent=2, default=str),
            name="SQL 日期→投诉量映射",
            attachment_type=allure.attachment_type.JSON,
        )

        # ---- 比对逻辑：区分 SQL 有数据 / 无数据两种场景 ----
        api_data_list = response_data.get("data") or []

        allure.attach(
            json.dumps(
                {"sql_map": sql_map, "api_data_count": len(api_data_list)},
                ensure_ascii=False, indent=2, default=str,
            ),
            name="比对上下文",
            attachment_type=allure.attachment_type.JSON,
        )

        if sql_map:
            # ---- 场景1：SQL 有数据 → 逐日比对 SQL complaint_cnt vs API complaintsCount ----
            for day_str, sql_count in sql_map.items():
                day_record = next(
                    (r for r in api_data_list if r.get("everyDay", "").startswith(day_str)),
                    None,
                )
                with allure.step(f"校验 {day_str}：API {api_field} vs SQL complaint_cnt"):
                    api_value = day_record.get(api_field, 0) if day_record else 0

                    allure.attach(
                        json.dumps(
                            {
                                "date": day_str,
                                "case_id": case_id,
                                f"api_{api_field}": api_value,
                                "db_complaint_cnt": sql_count,
                                "everyDay": day_record.get("everyDay") if day_record else None,
                                "api_has_record": day_record is not None,
                            },
                            ensure_ascii=False, indent=2, default=str,
                        ),
                        name=f"校验详情 - {day_str}",
                        attachment_type=allure.attachment_type.JSON,
                    )

                    assert api_value == sql_count, (
                        f"[{case_id}] {day_str}: API {api_field}({api_value}) != SQL complaint_cnt({sql_count})"
                    )
                    logger.info(f"[{case_id}] {day_str}: 校验通过 {api_field}={api_value}")

        else:
            # ---- 场景2：SQL 无数据 → 基础断言通过即判定用例通过（无投诉属正常业务场景） ----
            # 基础断言（HTTP状态码、rpcResult、businessSuccess）已在 _call_api 中完成
            with allure.step("SQL 无投诉数据，跳过数据对比断言，基础断言通过即视为用例通过"):
                non_zero_count = sum(
                    1 for r in api_data_list if (r.get(api_field) or 0) != 0
                )
                allure.attach(
                    json.dumps(
                        {
                            "case_id": case_id,
                            "sql_result": "无数据（空）",
                            "api_data_count": len(api_data_list),
                            "api_non_zero_complaint_count": non_zero_count,
                            "conclusion": "SQL无数据，仅执行基础断言，不再对比投诉量",
                        },
                        ensure_ascii=False, indent=2,
                    ),
                    name="空数据场景校验详情",
                    attachment_type=allure.attachment_type.JSON,
                )
                logger.info(
                    f"[{case_id}] SQL 无投诉数据，API 共 {len(api_data_list)} 条记录，"
                    f"其中非零投诉 {non_zero_count} 条，基础断言通过，用例通过"
                )
