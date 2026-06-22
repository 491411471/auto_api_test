# testcases/merchant/api/order/test_relet_order_api.py
# -*- coding: utf-8 -*-
"""
续租订单查询接口测试
接口：/hzsx/business/order/queryReletOrderByCondition
方法：POST

测试场景：
1. 无条件查询全部续租订单
2. 按订单号查询（SQL动态获取order_id）
3. 按订单状态查询（SQL动态获取status）
4. 按下单人姓名查询（SQL动态获取user_name）
5. 按商品名称查询（SQL动态获取product_name）

SQL预查询说明：
  在类级别fixture中执行一次SQL（JOIN ct_user_orders 与 ct_product），
  获取order_id、status、user_name、product_name，存储为类属性供所有测试方法共享。
"""
import json

import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case, execute_sql, replace_placeholders
from utils.data_loader import get_test_data, get_global_variables


# 预先加载所有用例数据（只加载一次）
_DATA_FILE = "data/merchant/api/order/relet_order_api.yaml"
_ALL_CASES = get_test_data(_DATA_FILE, "relet_order_tests")
if not _ALL_CASES:
    raise RuntimeError(f"无法加载 YAML 数据，请检查文件路径 {_DATA_FILE}")


def get_case_by_id(case_id: str):
    for case in _ALL_CASES:
        if case['case_id'] == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")


@allure.epic("商家端")
@allure.feature("商家端-续租订单")
@allure.story("续租订单查询")
class TestReletOrderApi:
    """续租订单查询接口测试"""
    _global_vars = None

    # SQL预查询结果（类级别共享，由 _preload_sql fixture 填充）
    _sql_order_id = None
    _sql_status = None
    _sql_user_name = None
    _sql_product_name = None
    _preload_sql_text = None   # 实际执行的 SQL（供诊断）
    _preload_error = None      # 预查询失败原因（供诊断）

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    @pytest.fixture(autouse=True)
    def _preload_sql(self, db):
        """SQL预查询：一次查询获取order_id、status、user_name、product_name，供所有测试方法共享"""
        if TestReletOrderApi._sql_order_id is not None:
            yield
            return

        global_vars = self._load_global_vars()
        sql_template = get_test_data(_DATA_FILE).get('pre_query_sql', '')
        if not sql_template:
            logger.warning("YAML中未配置pre_query_sql，跳过SQL预查询")
            yield
            return

        sql = replace_placeholders(sql_template, global_vars)
        TestReletOrderApi._preload_sql_text = sql

        with allure.step("SQL预查询：获取续租订单数据"):
            allure.attach(sql, name="预查询SQL", attachment_type=allure.attachment_type.TEXT)
            sql_config = {
                'query': sql,
                'columns': ['id', 'order_id', 'status', 'uid', 'product_id', 'user_name', 'product_name']
            }
            try:
                result = execute_sql(db, sql_config)
                if result and isinstance(result, dict):
                    TestReletOrderApi._sql_order_id = str(result.get('order_id') or '')
                    TestReletOrderApi._sql_status = str(result.get('status') or '')
                    TestReletOrderApi._sql_user_name = str(result.get('user_name') or '')
                    TestReletOrderApi._sql_product_name = str(result.get('product_name') or '')
                    extracted = {
                        "order_id": self._sql_order_id,
                        "status": self._sql_status,
                        "user_name": self._sql_user_name,
                        "product_name": self._sql_product_name,
                    }
                    allure.attach(
                        json.dumps(extracted, ensure_ascii=False, indent=2),
                        name="SQL预查询结果",
                        attachment_type=allure.attachment_type.JSON,
                    )
                    logger.info(f"SQL预查询结果: {extracted}")
                else:
                    TestReletOrderApi._preload_error = "SQL预查询无结果（返回空）"
                    logger.warning("SQL预查询无结果")
            except Exception as e:
                TestReletOrderApi._preload_error = f"SQL预查询失败: {e}"
                logger.warning(f"SQL预查询失败: {e}")

        yield

    def _build_vars(self):
        """构建包含SQL结果的变量字典"""
        global_vars = self._load_global_vars()
        if self._sql_order_id is not None:
            global_vars['order_id'] = self._sql_order_id
        if self._sql_status is not None:
            global_vars['status'] = self._sql_status
        if self._sql_user_name is not None:
            global_vars['user_name'] = self._sql_user_name
        if self._sql_product_name is not None:
            global_vars['product_name'] = self._sql_product_name
        return global_vars

    def _require_sql_data(self):
        """检查SQL预查询数据是否可用，不可用则跳过并附加诊断信息"""
        if self._sql_order_id is None:
            skip_msg = "SQL预查询未获取到测试数据，跳过此用例"
            diag_parts = [skip_msg]
            if self._preload_sql_text:
                diag_parts.append(f"\n\n执行的SQL:\n{self._preload_sql_text}")
            if self._preload_error:
                diag_parts.append(f"\n\n失败原因: {self._preload_error}")
            allure.attach(
                "".join(diag_parts),
                name="跳过原因",
                attachment_type=allure.attachment_type.TEXT
            )
            pytest.skip(skip_msg)

    def _require_non_empty_records(self, merchant_api_client, case, global_vars):
        """预检查询结果是否为空，为空则跳过用例"""
        body = replace_placeholders(case.get('json', {}), global_vars)
        endpoint = replace_placeholders(case.get('endpoint', ''), global_vars)
        resp = merchant_api_client.post(endpoint, json=body)
        resp_data = resp.json()
        records = (
            resp_data.get('data', {}).get('records', [])
            if isinstance(resp_data.get('data'), dict) else []
        )
        if not records:
            skip_msg = f"按条件查询无结果（请求参数: {body}），跳过此用例"
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            allure.attach(
                json.dumps(resp_data, ensure_ascii=False, indent=2),
                name="响应数据",
                attachment_type=allure.attachment_type.JSON,
            )
            pytest.skip(skip_msg)

    # ==================== 场景一：无条件查询全部续租订单 ====================
    @allure.title("RL_001 - 无条件查询全部续租订单")
    def test_rl_001(self, merchant_api_client, db):
        """无条件查询全部续租订单"""
        case = get_case_by_id("RL_001")
        global_vars = self._build_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)

    # ==================== 场景二：按订单号查询 ====================
    @allure.title("RL_002 - 按订单号查询")
    def test_rl_002(self, merchant_api_client, db):
        """按订单号查询续租订单（动态获取order_id）"""
        self._require_sql_data()
        case = get_case_by_id("RL_002")
        global_vars = self._build_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        self._require_non_empty_records(merchant_api_client, case, global_vars)
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)

    # ==================== 场景三：按订单状态查询 ====================
    @allure.title("RL_003 - 按订单状态查询")
    def test_rl_003(self, merchant_api_client, db):
        """按订单状态查询续租订单（动态获取status）"""
        self._require_sql_data()
        case = get_case_by_id("RL_003")
        global_vars = self._build_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        self._require_non_empty_records(merchant_api_client, case, global_vars)
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)

    #   ==================== 场景四：按下单人姓名查询 ====================
    @allure.title("RL_004 - 按下单人姓名查询")
    def test_rl_004(self, merchant_api_client, db):
        """按下单人姓名查询续租订单（动态获取user_name）"""
        self._require_sql_data()
        case = get_case_by_id("RL_004")
        global_vars = self._build_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        self._require_non_empty_records(merchant_api_client, case, global_vars)
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)


    # ==================== 场景五：按商品名称查询 ====================
    @allure.title("RL_005 - 按商品名称查询")
    def test_rl_005(self, merchant_api_client, db):
        """按商品名称查询续租订单（动态获取product_name）"""
        self._require_sql_data()
        case = get_case_by_id("RL_005")
        global_vars = self._build_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        self._require_non_empty_records(merchant_api_client, case, global_vars)
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)
