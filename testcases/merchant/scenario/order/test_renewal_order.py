# testcases/merchant/scenario/order/test_renewal_order.py
# -*- coding: utf-8 -*-
"""
商家端 - 订单模块 - 独立订单续租测试

流程：
  步骤1  POST /hzsx/business/order/queryOrderStagesDetail  → 获取账期详情，动态计算续租日期
  步骤2  POST /hzsx/business/order/extendOrderRelet        → 执行续租

日期计算规则：
  1. 从 orderByStagesDtoList 按 createTime 倒序取最新一条
  2. startDate = sourceRentStartDt + 1天（00:00:00）
  3. endDate   = startDate 同日（23:59:59）
"""
import os
import json
import allure
import pytest
import yaml
from datetime import datetime, timedelta

from common.logger import logger
from utils.variable_utils import validate, get_value_by_path


def _load_yaml(yaml_path: str) -> dict:
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@allure.epic("商家端")
@allure.feature("商家端-订单模块")
@allure.story("独立订单续租")
class TestRenewalOrder:
    """独立订单续租流程测试"""

    @allure.title("完整流程：查询账期详情 → 动态计算日期 → 执行续租")
    def test_renewal_order_flow(self, merchant_api_client, db, global_vars):
        yaml_path = os.path.join(
            os.path.dirname(__file__),
            "../../../../data/merchant/scenario/order/renewal_order.yaml"
        )
        config = _load_yaml(yaml_path)
        base_vars = global_vars.copy()

        # 合并 YAML 顶层 variables
        yaml_vars = config.get('variables', {})
        base_vars.update(yaml_vars)

        order_id = base_vars.get('order_id')
        shop_id = base_vars.get('shop_id', '71008738021cd3393bacbac182bd6a86af0b5c87')

        if not order_id:
            pytest.skip("YAML 中未配置 order_id，跳过此用例")

        # ==================================================================
        # 步骤1：查询订单账期详情
        # ==================================================================
        with allure.step("1. 查询订单账期详情"):
            stages_cfg = config['merchant']['query_order_stages']
            body = stages_cfg['body_template'].copy()
            body['orderId'] = order_id

            allure.attach(
                json.dumps(body, ensure_ascii=False, indent=2),
                name="步骤1 请求参数",
                attachment_type=allure.attachment_type.JSON
            )

            resp = merchant_api_client.post(stages_cfg['endpoint'], json=body)
            assert resp.status_code == stages_cfg['expected_status'], \
                f"状态码异常: 期望 {stages_cfg['expected_status']}, 实际 {resp.status_code}"
            resp_json = resp.json()

            allure.attach(
                json.dumps(resp_json, ensure_ascii=False, indent=2),
                name="步骤1 响应结果",
                attachment_type=allure.attachment_type.JSON
            )

            # 执行基础断言（businessSuccess、responseType 等）
            for check in stages_cfg['validate']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                validate(actual, check['operator'], check['value'], path)

            data = resp_json.get('data') or {}
            if not data:
                pytest.skip(f"订单 {order_id} 账期详情返回 data 为空，跳过")

            # ---------- 提取 orderByStagesDtoList ----------
            stages_list = data.get('orderByStagesDtoList') or []
            if not stages_list:
                pytest.skip(f"订单 {order_id} 的 orderByStagesDtoList 为空，无法续租")

            # 按 createTime 倒序排序，取最新一条
            stages_sorted = sorted(
                stages_list,
                key=lambda x: x.get('createTime') or '',
                reverse=True
            )
            latest_stage = stages_sorted[0]

            # 提取 sourceRentStartDt
            source_start = latest_stage.get('sourceRentStartDt')
            if not source_start:
                pytest.skip(
                    f"最新账期 (id={latest_stage.get('id')}) 的 sourceRentStartDt 为空"
                )

            # ---------- 动态计算续租日期 ----------
            # sourceRentStartDt 格式: "2026-06-05 00:00:00"
            source_dt = datetime.strptime(source_start, "%Y-%m-%d %H:%M:%S")
            # startDate = sourceRentStartDt + 1天 00:00:00
            start_date_dt = source_dt + timedelta(days=1)
            start_date = start_date_dt.strftime("%Y-%m-%d %H:%M:%S")
            # endDate = startDate 同日 23:59:59
            end_date = start_date_dt.strftime("%Y-%m-%d 23:59:59")

            # ---------- 提取续租期数（供日志记录） ----------
            # 优先从 fakeXuZuOrderByStagesList 获取下一期的 leaseTerm
            fake_list = data.get('fakeXuZuOrderByStagesList') or []
            relet_period = None
            if fake_list:
                relet_period = fake_list[0].get('leaseTerm') or fake_list[0].get('currentPeriods')

            # 降级：从已排序账期中取最大 currentPeriods + 1
            if relet_period is None:
                max_periods = max(
                    (s.get('currentPeriods') or 0 for s in stages_list),
                    default=0
                )
                relet_period = max_periods + 1

            # 将计算结果写入 base_vars 供后续步骤使用
            base_vars['start_date'] = start_date
            base_vars['end_date'] = end_date
            base_vars['relet_period'] = relet_period

            calc_summary = (
                f"订单号: {order_id}\n"
                f"sourceRentStartDt: {source_start}\n"
                f"计算后 startDate: {start_date}\n"
                f"计算后 endDate: {end_date}\n"
                f"续租期数 (relet_period): {relet_period}\n"
                f"最新账期 createTime: {latest_stage.get('createTime')}\n"
                f"最新账期 currentPeriods: {latest_stage.get('currentPeriods')}"
            )
            print("calc_summary:", calc_summary)
            allure.attach(calc_summary, name="日期计算结果", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"续租日期计算: startDate={start_date}, endDate={end_date}, period={relet_period}")

        # ==================================================================
        # 步骤2：执行续租
        # ==================================================================
        with allure.step("2. 执行续租"):
            relet_cfg = config['merchant']['extend_order_relet']
            relet_body = relet_cfg['body_template'].copy()
            relet_body['orderId'] = order_id
            relet_body['startDate'] = start_date
            relet_body['endDate'] = end_date

            allure.attach(
                json.dumps(relet_body, ensure_ascii=False, indent=2),
                name="步骤2 请求参数",
                attachment_type=allure.attachment_type.JSON
            )
            print("执行续租请求:", relet_body)
            resp = merchant_api_client.post(relet_cfg['endpoint'], json=relet_body)
            assert resp.status_code == relet_cfg['expected_status'], \
                f"状态码异常: 期望 {relet_cfg['expected_status']}, 实际 {resp.status_code}"
            resp_json = resp.json()
            print("执行续租响应:", resp_json)
            allure.attach(
                json.dumps(resp_json, ensure_ascii=False, indent=2),
                name="步骤2 响应结果",
                attachment_type=allure.attachment_type.JSON
            )

            # 业务级跳过：如果返回重复续租等业务约束
            error_msg = resp_json.get('errorMessage') or ''
            if resp_json.get('businessSuccess') is not True and error_msg:
                skip_keywords = ['已续租', '重复续租', '不允许续租', '续租已存在']
                if any(kw in error_msg for kw in skip_keywords):
                    skip_reason = f"续租业务约束: {error_msg}"
                    allure.attach(skip_reason, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                    logger.warning(skip_reason)
                    pytest.skip(skip_reason)

            # 执行断言
            for check in relet_cfg['validate']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                validate(actual, check['operator'], check['value'], path)

            # 从续租响应中提取实际期数（供日志记录）
            relet_data = resp_json.get('data') or {}
            actual_period = relet_data.get('currentPeriods') or relet_data.get('leaseTerm')
            if actual_period:
                relet_period = actual_period
                base_vars['relet_period'] = relet_period
                allure.attach(
                    f"从续租响应中提取到实际期数: {relet_period}",
                    name="续租期数(响应)",
                    attachment_type=allure.attachment_type.TEXT
                )

            logger.info(f"续租成功: orderId={order_id}, period={relet_period}")

        # ==================================================================
        # 最终汇总
        # ==================================================================
        allure.attach(
            f"步骤1-查询账期: orderId={order_id}, startDate={start_date}, endDate={end_date}\n"
            f"步骤2-执行续租: isXuZuFlag=1, relet_period={relet_period}",
            name="最终验证结果", attachment_type=allure.attachment_type.TEXT
        )
        logger.info("独立订单续租流程全部通过")
