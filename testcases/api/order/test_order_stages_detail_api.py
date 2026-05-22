import allure
import pytest
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables

# 加载 YAML 中所有用例
_ALL_CASES = get_test_data("order_stages_detail_api.yaml", "order_stages_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 order_stages_detail_api.yaml")

def get_case_by_id(case_id: str):
    for case in _ALL_CASES:
        if case['case_id'] == case_id:
            return case
    raise ValueError(f"未找到 case_id: {case_id}")

@allure.feature("商家端-订单模块")
@allure.story("订单分期详情")
class TestOrderStagesDetail:
    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("order_stages_detail_api.yaml")
        return cls._global_vars.copy()

    def _fetch_expected_stages(self, db, order_id, shop_id):
        """从数据库获取该订单所有分期记录，按期数升序返回"""
        sql = """
            SELECT current_periods, statement_date ,current_periods_rent, status
            FROM llxz_order.ct_order_by_stages
            WHERE order_id = %s AND shop_id = %s
            ORDER BY current_periods ASC
        """
        rows = db.fetch_all(sql, (order_id, shop_id))
        if not rows:
            pytest.skip(f"订单 {order_id} 在数据库中无分期记录")
        return rows

    def test_os_001_periods(self, api_client, db):
        """验证订单分期每期期数"""
        case = get_case_by_id("OS_001")
        global_vars = self._load_global_vars()
        # 执行用例（包含 SQL 和接口请求，以及基础断言）
        execute_test_case(case, api_client, db, global_vars)

        order_id = global_vars.get('order_id')
        shop_id = global_vars.get('shop_id')
        if not order_id:
            pytest.fail("未能从 SQL 获取 order_id")

        # 获取数据库预期数据
        expected = self._fetch_expected_stages(db, order_id, shop_id)

        # 再次调用接口获取实际数据（因为 execute_test_case 未返回响应体）
        resp = api_client.post("/hzsx/business/order/queryOrderStagesDetail", json={"orderId": order_id})
        actual_stages = resp.json().get('data', {}).get('orderByStagesDtoList', [])

        assert len(actual_stages) == len(expected), f"分期数量不一致：期望 {len(expected)} 期，实际 {len(actual_stages)} 期"

        # 逐期验证期数字段
        for idx, (exp, act) in enumerate(zip(expected, actual_stages)):
            with allure.step(f"验证第 {exp['current_periods']} 期期数"):
                assert act['currentPeriods'] == exp['current_periods'], f"第 {exp['current_periods']} 期期数错误：实际 {act['currentPeriods']}"

    def test_os_002_rent(self, api_client, db):
        """验证订单分期每期租金"""
        case = get_case_by_id("OS_002")
        global_vars = self._load_global_vars()
        execute_test_case(case, api_client, db, global_vars)

        order_id = global_vars.get('order_id')
        shop_id = global_vars.get('shop_id')
        if not order_id:
            pytest.fail("未能从 SQL 获取 order_id")

        expected = self._fetch_expected_stages(db, order_id, shop_id)

        resp = api_client.post("/hzsx/business/order/queryOrderStagesDetail", json={"orderId": order_id})
        actual_stages = resp.json().get('data', {}).get('orderByStagesDtoList', [])

        assert len(actual_stages) == len(expected), "分期数量不一致"

        for exp, act in zip(expected, actual_stages):
            with allure.step(f"验证第 {exp['current_periods']} 期租金, 期望租金：{exp['current_periods_rent']}--实际租金：{act['currentPeriodsRent']}"):
                exp_rent = float(exp['current_periods_rent'])
                act_rent = float(act['currentPeriodsRent'])
                assert act_rent == pytest.approx(exp_rent),  f"第 {exp['current_periods']} 期租金错误：期望 {exp_rent}，实际 {act_rent}"

    def test_os_003_status(self, api_client, db):
        """验证订单分期每期状态"""
        case = get_case_by_id("OS_003")
        global_vars = self._load_global_vars()
        execute_test_case(case, api_client, db, global_vars)

        order_id = global_vars.get('order_id')
        shop_id = global_vars.get('shop_id')
        if not order_id:
            pytest.fail("未能从 SQL 获取 order_id")

        expected = self._fetch_expected_stages(db, order_id, shop_id)

        resp = api_client.post("/hzsx/business/order/queryOrderStagesDetail", json={"orderId": order_id})
        actual_stages = resp.json().get('data', {}).get('orderByStagesDtoList', [])

        assert len(actual_stages) == len(expected), "分期数量不一致"

        for exp, act in zip(expected, actual_stages):
            with allure.step(f"验证第 {exp['current_periods']} 期状态，期望租期状态：{exp['status']}--实际租期状态{act['status']}"):
                assert str(act['status']) == str(exp['status']), f"第 {exp['current_periods']} 期状态错误：期望 {exp['status']}，实际 {act['status']}"

    def test_os_004_rent_end_date(self, api_client, db):
        """循环断言每个账期的到期时间（租期结束日期）"""
        case = get_case_by_id("OS_004")
        global_vars = self._load_global_vars()
        execute_test_case(case, api_client, db, global_vars)

        order_id = global_vars.get('order_id')
        shop_id = global_vars.get('shop_id')
        if not order_id:
            pytest.fail("未能从 SQL 获取 order_id")

        expected_stages = self._fetch_expected_stages(db, order_id, shop_id)
        if not expected_stages:
            pytest.skip(f"订单 {order_id} 在数据库中无分期数据")

        resp = api_client.post("/hzsx/business/order/queryOrderStagesDetail", json={"orderId": order_id})
        actual_stages = resp.json().get('data', {}).get('orderByStagesDtoList', [])

        assert len(actual_stages) == len(expected_stages), f"分期数量不一致：期望 {len(expected_stages)}，实际 {len(actual_stages)}"

        from datetime import datetime, timedelta

        for idx, (exp, act) in enumerate(zip(expected_stages, actual_stages)):
            period = exp['current_periods']

            # 统一转为 YYYY-MM-DD 字符串
            db_date = exp['statement_date']
            expected_str = str(db_date)[:10] if db_date else ''

            actual_val = act.get('statementDate')
            actual_str = actual_val[:10] if actual_val else ''

            with allure.step(f"验证第 {period} 期到期时间（statementDate）, 期望租期：{expected_str} -- 实际租期：{actual_str}"):
                assert actual_val is not None, f"第 {period} 期 statementDate 字段缺失"
                # 数据库中的 statement_date（可能是 datetime 对象或字符串）
                db_date = exp['statement_date']
                if isinstance(db_date, datetime):
                    expected_date = db_date.strftime('%Y-%m-%d')
                else:
                    # 如果是字符串，提取前10位
                    expected_date = str(db_date)[:10] if db_date else None

                # 接口返回的 statementDate（字符串，如 "2025-09-01 23:59:59"）
                actual_end = act.get('statementDate')
                assert actual_end is not None, f"第 {period} 期 statementDate 字段缺失"
                # 提取日期部分（前10个字符）
                actual_date = actual_end[:10]
                # 验证日期格式
                try:
                    datetime.strptime(actual_date, "%Y-%m-%d")
                except ValueError:
                    raise AssertionError(f"第 {period} 期 statementDate 日期无效: {actual_date}")

                # 断言日期一致
                assert actual_date == expected_date,  f"第 {period} 期 statementDate 错误：期望 {expected_date}，实际 {actual_date}"
        allure.attach(
            f"订单 {order_id} 共 {len(actual_stages)} 期，statementDate 验证全部通过",
            "验证结果",
            attachment_type=allure.attachment_type.TEXT)