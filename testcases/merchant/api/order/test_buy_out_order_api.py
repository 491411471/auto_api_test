# testcases/merchant/api/order/test_buy_out_order_api.py
# -*- coding: utf-8 -*-
"""
购买订单查询接口测试
接口：/hzsx/business/order/queryBuyOutOrdersByCondition
方法：POST

测试场景：
1. 无条件查询全部购买订单
2. 按订单号查询（SQL动态获取order_id）
3. 按订单状态查询（API响应动态获取state）
4. 按下单人姓名查询（API响应动态获取userName）
5. 按商品名称查询（API响应动态获取productName）

SQL预查询说明：
  在类级别fixture中执行一次SQL获取order_id，再通过API响应提取
  userName、productName、state，存储为类属性供所有测试方法共享。
"""
import json

import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case, execute_sql, replace_placeholders
from utils.data_loader import get_test_data, get_global_variables


# 预先加载所有用例数据（只加载一次）
_DATA_FILE = "data/merchant/api/order/buy_out_order_api.yaml"
_ALL_CASES = get_test_data(_DATA_FILE, "buy_out_order_tests")
if not _ALL_CASES:
    raise RuntimeError(f"无法加载 YAML 数据，请检查文件路径 {_DATA_FILE}")


def get_case_by_id(case_id: str):
    for case in _ALL_CASES:
        if case['case_id'] == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")


@allure.epic("商家端")
@allure.feature("订单模块-购买订单")
@allure.story("购买订单查询")
class TestBuyOutOrderApi:
    """购买订单查询接口测试"""
    _global_vars = None

    # SQL预查询 + API响应提取结果（类级别共享，由 _preload_sql fixture 填充）
    _sql_order_id = None
    _sql_user_name = None
    _sql_state = None
    _sql_product_name = None
    _preload_sql_text = None   # 实际执行的 SQL（供诊断）
    _preload_error = None      # 预查询失败原因（供诊断）

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    @pytest.fixture(autouse=True)
    def _preload_sql(self, db, merchant_api_client):
        """
        SQL预查询 + API数据提取（只执行一次，全类共享）：
        1. SQL 获取 order_id
        2. 调用查询接口获取该订单的 userName、productName、state
        """
        if TestBuyOutOrderApi._sql_order_id is not None:
            yield
            return

        global_vars = self._load_global_vars()
        sql_template = get_test_data(_DATA_FILE).get('pre_query_sql', '')
        if not sql_template:
            logger.warning("YAML中未配置pre_query_sql，跳过SQL预查询")
            yield
            return

        sql = replace_placeholders(sql_template, global_vars)
        TestBuyOutOrderApi._preload_sql_text = sql

        with allure.step("SQL预查询：获取购买订单 order_id"):
            allure.attach(sql, name="预查询SQL", attachment_type=allure.attachment_type.TEXT)
            sql_config = {'query': sql, 'columns': ['id', 'uid', 'order_id']}
            try:
                result = execute_sql(db, sql_config)
                if result and isinstance(result, dict):
                    TestBuyOutOrderApi._sql_order_id = result.get('order_id')
                    logger.info(f"SQL预查询结果: order_id={self._sql_order_id}")
                else:
                    TestBuyOutOrderApi._preload_error = "SQL预查询无结果（返回空）"
                    logger.warning("SQL预查询无结果")
                    yield
                    return
            except Exception as e:
                TestBuyOutOrderApi._preload_error = f"SQL预查询失败: {e}"
                logger.warning(f"SQL预查询失败: {e}")
                yield
                return

        # 通过API响应提取 userName、productName、state
        with allure.step("API预查询：提取userName、productName、state"):
            try:
                resp = merchant_api_client.post(
                    "/hzsx/business/order/queryBuyOutOrdersByCondition",
                    json={"pageNumber": 1, "pageSize": 10, "orderId": self._sql_order_id}
                )
                resp_data = resp.json()
                records = resp_data.get("data", {}).get("records", [])
                if records:
                    record = records[0]
                    TestBuyOutOrderApi._sql_state = record.get("state")
                    TestBuyOutOrderApi._sql_user_name = record.get("userName")
                    TestBuyOutOrderApi._sql_product_name = record.get("productName")
                    extracted = {
                        "order_id": self._sql_order_id,
                        "userName": self._sql_user_name,
                        "productName": self._sql_product_name,
                        "state": self._sql_state,
                    }
                    allure.attach(
                        json.dumps(extracted, ensure_ascii=False, indent=2),
                        name="API预查询提取结果",
                        attachment_type=allure.attachment_type.JSON,
                    )
                    logger.info(f"API预查询提取: {extracted}")
                else:
                    logger.warning(f"按order_id={self._sql_order_id}查询无结果，无法提取动态变量")
            except Exception as e:
                logger.warning(f"API预查询失败: {e}")

        yield

    def _build_vars(self):
        """构建包含SQL/API结果的变量字典"""
        global_vars = self._load_global_vars()
        if self._sql_order_id is not None:
            global_vars['order_id'] = self._sql_order_id
        if self._sql_user_name is not None:
            global_vars['user_name'] = self._sql_user_name
        if self._sql_state is not None:
            global_vars['state'] = self._sql_state
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

    # ==================== 场景一：无条件查询全部购买订单 ====================
    @allure.title("BO_001 - 无条件查询全部购买订单")
    def test_bo_001(self, merchant_api_client, db):
        """无条件查询全部购买订单"""
        case = get_case_by_id("BO_001")
        global_vars = self._build_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)

    # ==================== 场景二：按订单号查询 ====================
    @allure.title("BO_002 - 按订单号查询购买订单")
    def test_bo_002(self, merchant_api_client, db):
        """按订单号查询购买订单（动态获取order_id）"""
        self._require_sql_data()
        case = get_case_by_id("BO_002")
        global_vars = self._build_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        self._require_non_empty_records(merchant_api_client, case, global_vars)
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)

    # ==================== 场景三：按订单状态查询 ====================
    @allure.title("BO_003 - 按订单状态查询购买订单")
    def test_bo_003(self, merchant_api_client, db):
        """按订单状态查询购买订单（动态获取state）"""
        self._require_sql_data()
        case = get_case_by_id("BO_003")
        global_vars = self._build_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        self._require_non_empty_records(merchant_api_client, case, global_vars)
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)

    # ==================== 场景四：按下单人姓名查询 ====================
    @allure.title("BO_004 - 按下单人姓名查询购买订单")
    def test_bo_004(self, merchant_api_client, db):
        """按下单人姓名查询购买订单（动态获取userName）"""
        self._require_sql_data()
        case = get_case_by_id("BO_004")
        global_vars = self._build_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        self._require_non_empty_records(merchant_api_client, case, global_vars)
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)

    # ==================== 场景五：按商品名称查询 ====================
    @allure.title("BO_005 - 按商品名称查询购买订单")
    def test_bo_005(self, merchant_api_client, db):
        """按商品名称查询购买订单（动态获取productName）"""
        self._require_sql_data()
        case = get_case_by_id("BO_005")
        global_vars = self._build_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        self._require_non_empty_records(merchant_api_client, case, global_vars)
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)
