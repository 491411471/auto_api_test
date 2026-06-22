# testcases/merchant/api/operational_report/test_operational_report.py
"""
运营报表 - 每日运营数据验证（进件量/下单量/发货量/发货率）
4 个指标 × N 天（由 API 实际返回记录数决定）参数化用例
模块加载时调用 API 获取实际日期，逐日逐指标与数据库 SUM 进行一致性校验
"""
import copy
import json
import os
from datetime import datetime, timedelta

import allure
import pytest
import yaml

from common.api_client import APIClient
from common.config_manager import config_manager
from common.logger import logger
from common.test_helpers import (
    execute_sql,
    replace_placeholders,
    validate_response,
)
from utils.assert_utils import assert_status_code


# ==================== 加载 YAML ====================
yaml_path = os.path.join(os.path.dirname(__file__), "../../../../data/merchant/api/operational_report/operational_report_api.yaml")
with open(yaml_path, 'r', encoding='utf-8') as f:
    _config = yaml.safe_load(f)

_api_config = _config.get("api_config", {})
_cases = _config.get("operational_report_tests", [])


# ==================== 模块级 API 调用，获取实际日期列表 ====================
_TODAY = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
_DAYS_BACK = 6  # 含首尾共 7 天


def _get_child_records(response_data):
    """从 data.datas[0].children 中提取子记录列表"""
    data = response_data.get('data', {})
    if not isinstance(data, dict):
        return []
    datas = data.get('datas', [])
    if not isinstance(datas, list) or not datas:
        return []
    first_entry = datas[0]
    children = first_entry.get('children') if isinstance(first_entry, dict) else None
    return children if isinstance(children, list) else []


def _fetch_api_dates():
    """模块加载时调用 API，返回 (response_json, dates_list)
    失败时降级为近 7 天预设日期范围
    """
    yml_vars = _config.get("variables", {}) or {}
    start_date = (_TODAY - timedelta(days=_DAYS_BACK)).strftime("%Y-%m-%d")
    end_date = _TODAY.strftime("%Y-%m-%d")
    api_params = {
        "startTime": start_date,
        "endTime": end_date,
        "shopId": yml_vars.get("shop_id", ""),
        "titleType": "zrrtj",
    }
    try:
        cfg = config_manager.get_api_client_config(endpoint='merchant')
        # 确保传入 endpoint，以支持 token 刷新逻辑
        cfg['endpoint'] = 'merchant'
        client = APIClient(**cfg)
        endpoint = _api_config.get("endpoint", "")
        resp = client.post(endpoint, json=api_params)
        resp_json = resp.json()
        children = _get_child_records(resp_json)
        dates = sorted([
            r['createDate'] for r in children
            if r.get('createDate')
        ])
        logger.info(f"API 返回 {len(dates)} 个日期: {dates}")
        return resp_json, dates
    except Exception as e:
        logger.warning(f"模块级 API 调用失败，降级使用 7 天预设日期: {e}")
        fallback = [(_TODAY - timedelta(days=i)).strftime("%Y-%m-%d")
                    for i in range(_DAYS_BACK, -1, -1)]
        return None, fallback


_cached_response, _dates = _fetch_api_dates()

# 构建参数化列表：4 个指标 × N 个实际日期
_params = []
_param_ids = []
for _ci, _case in enumerate(_cases):
    _api_field = _case.get('api_field', 'unknown')
    for _day_str in _dates:
        _params.append((_ci, _day_str))
        _param_ids.append(f"{_api_field}-{_day_str}")


@allure.epic("商家端")
@allure.feature("数据报表")
@allure.story("运营报表 - 近7天每日运营数据")
class TestOperationalReport:
    """
    近7天每日运营数据校验（进件量/下单量/发货量/发货率）
    每个指标用例对应一个 API 响应字段，逐日比对数据库 SUM 与接口返回值
    """

    @pytest.mark.parametrize(
        "case_idx, day",
        _params,
        ids=_param_ids
    )
    def test_daily_metric(self, case_idx, day, dw_db, global_vars):
        """逐日逐指标校验：SQL SUM vs API 响应字段"""
        case = _cases[case_idx].copy()
        api_field = case.get('api_field', 'jjl')
        case_id = case.get('case_id', f'OR_{case_idx:03d}')

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

        # ---- 注入动态日期范围（YYYY-MM-DD 格式，用于 SQL 占位符替换） ----
        start_date = (_TODAY - timedelta(days=_DAYS_BACK)).strftime("%Y-%m-%d")
        end_date = _TODAY.strftime("%Y-%m-%d")
        variables['start_date'] = start_date
        variables['end_date'] = end_date

        # ---- 模块级 API 响应已缓存，直接使用 ----
        response_data = _cached_response
        if response_data is None:
            pytest.skip(f"[{case_id}] {day}: 模块级 API 调用失败，无法获取响应数据")

        # ---- 从 API 响应 data.datas[0].children 中匹配当前日期记录 ----
        children = _get_child_records(response_data)
        day_record = next((r for r in children if r.get('createDate') == day), None)

        # API 无此日记录 → 跳过
        if day_record is None:
            pytest.skip(f"[{case_id}] {day}: API响应中无此日期记录，跳过验证")

        api_value = day_record.get(api_field)

        # ---- 执行当日 SQL 查询 ----
        daily_sql_config = copy.deepcopy(case.get('daily_sql', {}))
        day_date = datetime.strptime(day, "%Y-%m-%d")
        variables['day_date'] = day
        variables['next_day_date'] = (day_date + timedelta(days=1)).strftime("%Y-%m-%d")
        sql_replaced = replace_placeholders(daily_sql_config, variables)

        with allure.step(f"执行 {day} 的 SQL 查询（{case.get('title', '')}）"):
            allure.attach(
                sql_replaced.get('query', ''),
                name="替换后 SQL",
                attachment_type=allure.attachment_type.TEXT
            )
            sql_value = execute_sql(dw_db, sql_replaced)
            print(f"SQL 查询结果: {sql_value}")

        # ---- 断言 ----
        with allure.step(f"校验 {day}：{api_field} vs 数据库"):
            allure.attach(
                f"日期: {day}\n用例: {case_id}\nAPI字段: {api_field}",
                name="校验上下文",
                attachment_type=allure.attachment_type.TEXT
            )

            # 类型对齐后比较
            sql_str = str(sql_value) if sql_value is not None else None
            api_str = str(api_value) if api_value is not None else None

            allure.attach(
                json.dumps({
                    "date": day,
                    "case_id": case_id,
                    "api_field": api_field,
                    f"api_{api_field}": api_value,
                    "db_metric_value": sql_value,
                    "api_str": api_str,
                    "sql_str": sql_str,
                    "createDate": day_record.get('createDate'),
                }, ensure_ascii=False, indent=2, default=str),
                name="校验详情",
                attachment_type=allure.attachment_type.JSON
            )
            assert api_str == sql_str, (f"[{case_id}] {day}: API {api_field}({api_value}) != SQL({sql_value})")
            logger.info(f"[{case_id}] {day}: 校验通过 {api_field}={api_value}")
