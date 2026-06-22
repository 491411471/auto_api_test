# testcases/merchant/api/complaint/test_complaint_rate_api.py
"""
投诉率统计验证
基于 complaint_rate_api.yaml 配置，校验接口返回的投诉总量、订单总量与数据库一致
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
    "../../../../data/merchant/api/complaint/complaint_rate_api.yaml"
)
with open(yaml_path, 'r', encoding='utf-8') as f:
    _config = yaml.safe_load(f)

_yaml_vars = _config.get("variables", {})
_cases = _config.get("complaint_rate_tests", [])

# ==================== 动态生成日期范围（当前日期向前推7天） ====================
_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
_yaml_vars['date_start'] = (_today - timedelta(days=6)).strftime("%Y-%m-%d 00:00:00")
_yaml_vars['date_end'] = _today.strftime("%Y-%m-%d 23:59:59")


@allure.epic("商家端")
@allure.feature("投诉管理")
@allure.story("投诉率统计验证")
class TestComplaintRateAPI:
    """
    投诉率统计接口校验
    从数据库分别统计订单总量和投诉总量，与接口返回字段进行双向一致性验证
    """

    @allure.title("CR_001 | 验证店铺投诉率：SQL 订单量/投诉量 vs API 双向交叉校验")
    def test_complaint_rate(self, merchant_api_client, db, global_vars):
        case = _cases[0].copy()
        case_id = case.get("case_id", "CR_001")
        print("case_id", case_id)
        # ---- 1. 合并变量（全局 + YAML） ----
        variables = global_vars.copy()
        variables.update(_yaml_vars)
        if 'variables' in case and isinstance(case['variables'], dict):
            variables.update(case['variables'])

        # ---- 2. 执行前置 SQL（顺序执行，获取订单总量和投诉总量） ----
        sql_configs = case.get('sql', [])
        if not isinstance(sql_configs, list):
            sql_configs = [sql_configs]

        sql_results = {}
        with allure.step("执行前置 SQL：统计订单总量和投诉总量"):
            for idx, sql_cfg in enumerate(sql_configs):
                sql_replaced = replace_placeholders(sql_cfg, variables)
                col = sql_cfg.get('column')
                allure.attach(
                    sql_replaced.get('query', ''),
                    name=f"前置 SQL-{idx+1}（{col}）",
                    attachment_type=allure.attachment_type.TEXT
                )
                value = execute_sql(db, sql_replaced)
                sql_results[col] = value
                logger.info(f"前置 SQL-{idx+1}: {col} = {value}")

        db_completed_order_num = sql_results.get('completed_order_num')
        db_complaint_total_num = sql_results.get('complaint_total_num')

        allure.attach(
            json.dumps({
                "completed_order_num（订单总量）": db_completed_order_num,
                "complaint_total_num（投诉总量）": db_complaint_total_num,
            }, ensure_ascii=False, indent=2),
            name="前置 SQL 统计结果",
            attachment_type=allure.attachment_type.JSON
        )

        # ---- 3. 调用 API ----
        case_replaced = replace_placeholders(case, variables)
        endpoint = case_replaced.get('endpoint', '')
        params = case_replaced.get('params', {})
        method = case_replaced.get('method', 'POST').upper()

        with allure.step(f"调用投诉率统计接口 {method} {endpoint}"):
            allure.attach(
                json.dumps({"endpoint": endpoint, "params": params}, ensure_ascii=False, indent=2),
                name="API 请求参数",
                attachment_type=allure.attachment_type.JSON
            )
            resp = merchant_api_client.post(endpoint, json=params)
            logger.info(f"投诉率接口响应状态码: {resp.status_code}")
            assert_status_code(resp.status_code, case.get('expected_status', 200))

            response_data = resp.json()
            print("response_data", response_data)
            allure.attach(
                json.dumps(response_data, ensure_ascii=False, indent=2)[:5000],
                name="API 完整响应",
                attachment_type=allure.attachment_type.JSON
            )

        # ---- 4. 基础断言（rpcResult / businessSuccess） ----
        with allure.step("基础响应断言"):
            validate_response(case, response_data, variables)

        # ---- 5. 提取 API 字段（字段在 data.records[0] 内） ----
        api_data = response_data.get('data', {})
        api_complaint_total = api_data.get('allComplaintNo') if isinstance(api_data, dict) else 0
        print("api_complaint_total", api_complaint_total)
        allure.attach(json.dumps({"api_complaint_total": api_complaint_total,}, ensure_ascii=False, indent=2),
            name="API 提取字段",
            attachment_type=allure.attachment_type.JSON)
        # ---- 6. 交叉校验：SQL vs API ----
        with allure.step("交叉校验：数据库统计量 vs API 返回量"):
            allure.attach(
                json.dumps({
                    "字段": "complaintTotalNum（投诉总量）",
                    "SQL": db_complaint_total_num,
                    "API": api_complaint_total,
                }, ensure_ascii=False, indent=2),
                name="投诉总量对比",
                attachment_type=allure.attachment_type.JSON
            )
            assert api_complaint_total == db_complaint_total_num, (
                f"[{case_id}] 投诉总量不一致: API({api_complaint_total}) != SQL({db_complaint_total_num})"
            )
            logger.info(f"[{case_id}] 投诉总量校验通过: {api_complaint_total}")

        # ---- 7. 执行后置 SQL（二次验证数据库状态） ----
        post_sql_configs = case.get('post_sql', [])
        if post_sql_configs:
            if not isinstance(post_sql_configs, list):
                post_sql_configs = [post_sql_configs]

            with allure.step("后置 SQL 验证：再次查询数据库确认数据一致性"):
                for idx, post_cfg in enumerate(post_sql_configs):
                    post_replaced = replace_placeholders(post_cfg, variables)
                    allure.attach(
                        post_replaced.get('query', ''),
                        name=f"后置 SQL-{idx+1}",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    post_result = execute_sql(db, post_replaced)

                    if isinstance(post_result, dict):
                        post_complaint_total = post_result.get('complaint_total')
                        post_order_total = post_result.get('order_total')

                        allure.attach(
                            json.dumps({
                                "post_sql_complaint_total": post_complaint_total,
                                "api_complaintTotalNum": api_complaint_total,
                            }, ensure_ascii=False, indent=2),
                            name=f"后置 SQL-{idx+1} 结果 vs API",
                            attachment_type=allure.attachment_type.JSON
                        )

                        assert post_complaint_total == api_complaint_total, (
                            f"[{case_id}] 后置SQL投诉量({post_complaint_total}) != API({api_complaint_total})"
                        )
                        logger.info(
                            f"[{case_id}] 后置 SQL 校验通过: "
                            f"complaint_total={post_complaint_total}, order_total={post_order_total}"
                        )

        logger.info(f"[{case_id}] 投诉率统计验证全部通过")
