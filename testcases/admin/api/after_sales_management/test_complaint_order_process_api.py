# testcases/admin/api/after_sales_management/test_complaint_order_process_api.py
"""
运营端 - 售后管理 - 工单处理接口测试

接口：POST /hzsx/orderComplaints/modifyOrderComplaints（工单处理）

数据策略：
  - SQL 预查询：按状态从 DB 获取一条投诉工单的 id + 分类字段
  - 状态流转：待处理(0) → 跟进中(3) → 已完结(1) / 已撤诉(2)
  - 执行顺序：参数化列表顺序即为 COP_001 → COP_002 → COP_003
  - 状态校验：post_sql 从 DB 验证目标状态已变更
"""
import allure
import pytest

from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables


_DATA_FILE = "data/admin/api/after_sales_management/complaint_order_process_api.yaml"

# 各用例的目标状态映射（case_id → 目标 status 值）
_TARGET_STATUS_MAP = {
    "COP_001": 3,  # 待处理 → 跟进中
    "COP_002": 1,  # 跟进中 → 已完结
    "COP_003": 2,  # 跟进中 → 已撤诉
}


@allure.epic("运营端")
@allure.feature("售后管理")
@allure.story("工单处理")
class TestComplaintOrderProcess:
    """工单处理 - 投诉工单状态流转（参数化，按顺序执行）"""

    _all_cases = get_test_data(_DATA_FILE, "complaint_order_process_tests")

    @pytest.mark.parametrize(
        "case",
        _all_cases,
        ids=[c["case_id"] for c in _all_cases],
    )
    def test_complaint_order_process(self, admin_api_client, db, case):
        # 1. 加载全局变量（.copy() 隔离缓存，防止参数化用例间变量污染）
        global_vars = get_global_variables(_DATA_FILE).copy()

        # 2. 注入目标状态（YAML 无法预定义每个用例不同的目标状态）
        case_id = case["case_id"]
        global_vars["target_status"] = _TARGET_STATUS_MAP[case_id]

        # 3. 更新 Allure 标题
        allure.dynamic.title(f"{case_id} | {case.get('title', '')}")

        # 4. 执行测试（框架自动处理 SQL 数据提取、变量替换、API 请求、断言、post_sql 状态校验）
        execute_test_case(case, admin_api_client, db, global_vars)
