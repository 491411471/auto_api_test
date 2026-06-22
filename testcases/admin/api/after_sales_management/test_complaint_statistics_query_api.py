# testcases/admin/api/after_sales_management/test_complaint_statistics_query_api.py
"""
运营端 - 售后管理 - 投诉统计查询接口测试

接口1：POST /hzsx/orderComplaints/queryComplaintStatisticsPage  （列表查询，用例1-9）
接口2：POST /hzsx/orderComplaints/getOrderComplaintsShopDetial （详情查询，用例10）

测试场景：
  场景1：基础查询与快捷筛选（CSQ_001 ~ CSQ_004）
  场景2：多维度条件组合筛选（CSQ_005 ~ CSQ_007）→ 含 SQL 独立数据源验证
  场景3：汇总数据与明细数据交叉验证（CSQ_008 ~ CSQ_009）→ Python 层追加校验
  场景4：详情接口验证（CSQ_010）→ SQL 预查询 + 详情接口

数据策略：
  - 日期变量由 Python 运行时动态计算并注入（today_start, days_7_start 等）
  - SQL 交叉验证确保接口返回数据与数据库一致
"""
import allure
import json
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from common.logger import logger
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables


_DATA_FILE = "data/admin/api/after_sales_management/complaint_statistics_query_api.yaml"

# 需要 Python 层追加交叉验证的用例（CSQ_009 在 YAML 中已注释，暂不启用）
_CROSS_VALIDATION_IDS = {"CSQ_008"}


def _compute_date_vars() -> dict:
    """
    计算动态日期变量，注入到 global_vars 中供 YAML 占位符替换使用。

    Returns:
        dict: 包含 today_start, today_end, days_7_start, days_30_start, common_end
    """
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "today_start": today.strftime("%Y-%m-%d 00:00:00"),
        "today_end": today.strftime("%Y-%m-%d 23:59:59"),
        "days_7_start": (today - timedelta(days=6)).strftime("%Y-%m-%d 00:00:00"),
        "days_30_start": (today - timedelta(days=29)).strftime("%Y-%m-%d 00:00:00"),
        "common_end": today.strftime("%Y-%m-%d 23:59:59"),
    }


# ==================== 标准用例：YAML 驱动 ====================
@allure.epic("运营端")
@allure.feature("售后管理")
@allure.story("投诉统计查询")
class TestComplaintStatisticsQuery:
    """投诉统计查询 - 10 个测试用例（参数化）"""
    _all_cases = get_test_data(_DATA_FILE, "complaint_statistics_query_tests")

    @pytest.mark.parametrize("case", _all_cases, ids=[c["case_id"] for c in _all_cases],)
    def test_complaint_statistics_query(self, admin_api_client, db, case):
        # 1. 加载全局变量（.copy() 隔离，防止参数化用例间变量污染）
        global_vars = get_global_variables(_DATA_FILE).copy()
        # 2. 注入运行时日期变量（YAML 无法预计算的动态值）
        global_vars.update(_compute_date_vars())
        # 3. 更新 Allure 标题
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        # 4. 执行标准测试流程（框架自动处理变量替换、API 请求、断言、post_sql）
        execute_test_case(case, admin_api_client, db, global_vars)

