# testcases/admin/api/after_sales_management/test_complaint_order_query_api.py
"""
运营端 - 售后管理 - 投诉订单接口测试

接口1：POST /hzsx/orderComplaints/queryOrderComplaintsPageNew  （查询投诉订单，用例1-12）
接口2：POST /hzsx/orderComplaints/addOffOrderComplaints         （工单上报，用例13）

数据策略：
  - 查询接口：模块级懒加载，首次调用 API 获取动态数据（orderId），所有用例复用
  - 工单上报：SQL 预查询获取无投诉订单，动态生成请求参数
"""
import allure
import pytest
from datetime import datetime

from common.logger import logger
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables


_DATA_FILE = "data/admin/api/after_sales_management/complaint_order_query_api.yaml"


# ==================== 模块级懒加载：获取动态 orderId ====================
_first_query_data: dict | None = None


def _fetch_first_query_data(admin_api_client) -> dict:
    """
    首次调用投诉订单查询接口，提取第一条记录的 orderId 供后续用例（COQ_007/008）复用。
    仅执行一次，结果缓存至模块级变量。
    """
    global _first_query_data
    if _first_query_data is not None:
        return _first_query_data

    endpoint = "/hzsx/orderComplaints/queryOrderComplaintsPageNew"
    json_body = {
        "pageNumber": 1,
        "pageSize": 10,
        "ChannelGroupId": "001",
        "shopName": None,
        "status": "",
        "sourceType": "",
        "complaintsType": "",
        "rentType": "",
        "complaintCreateTime": None,
        "orderLabel": "",
        "sceneLabel": "",
        "channelGroupCode": "001",
    }
    with allure.step("预查询：获取首条投诉订单记录（动态数据）"):
        resp = admin_api_client.post(endpoint, json=json_body)
        data = resp.json()
        records = data.get("data", {}).get("orderComplaintsDtoPage", {}).get("records", [])
        if records:
            _first_query_data = {
                "first_order_id": records[0].get("orderId", ""),
                "first_rent_type": str(records[0].get("rentType", "")),
            }
            logger.info(f"[COQ] 预查询完成: {_first_query_data}")
        else:
            _first_query_data = {}
            logger.warning("[COQ] 预查询未获取到投诉订单数据")
    return _first_query_data


# ==================== 用例1-12：投诉订单查询 ====================
@allure.epic("运营端")
@allure.feature("售后管理")
@allure.story("投诉订单查询")
class TestComplaintOrderQuery:
    """投诉订单查询 - 12 个查询场景（参数化）"""

    _all_cases = get_test_data(_DATA_FILE, "complaint_order_query_tests")

    @pytest.mark.parametrize(
        "case",
        _all_cases,
        ids=[c["case_id"] for c in _all_cases],
    )
    def test_complaint_order_query(self, admin_api_client, db, case):
        # 1. 加载全局变量（.copy() 隔离缓存，防止参数化用例间变量污染）
        global_vars = get_global_variables(_DATA_FILE).copy()

        # 2. 注入动态数据（first_order_id，供 COQ_007/008 使用）
        query_data = _fetch_first_query_data(admin_api_client)
        if not query_data:
            pytest.skip("预查询未获取到投诉订单数据，跳过本次测试")
        global_vars.update(query_data)

        # 3. 更新 Allure 标题
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")

        # 4. 执行测试（框架自动处理变量替换、API 请求、YAML 声明式断言、post_sql 独立数据库断言）
        execute_test_case(case, admin_api_client, db, global_vars)


# ==================== 用例13：工单上报 ====================
@allure.epic("运营端")
@allure.feature("售后管理")
@allure.story("工单上报")
class TestAddOffOrderComplaint:
    """工单上报 - YAML 数据驱动，SQL 预查询动态填充参数"""

    _all_cases = get_test_data(_DATA_FILE, "add_off_order_complaint_tests")

    @pytest.mark.parametrize(
        "case",
        _all_cases,
        ids=[c["case_id"] for c in _all_cases],
    )
    def test_add_off_order_complaint(self, admin_api_client, db, case):
        # 1. 加载全局变量（.copy() 隔离缓存）
        global_vars = get_global_variables(_DATA_FILE).copy()

        # 2. 注入运行时动态变量（YAML 无法预计算的值）
        global_vars["complaint_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 3. 更新 Allure 标题
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")

        # 4. 执行测试（框架自动处理 SQL 数据提取、变量替换、API 请求、断言）
        execute_test_case(case, admin_api_client, db, global_vars)
