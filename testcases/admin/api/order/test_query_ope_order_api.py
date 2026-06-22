# testcases/admin/api/order/test_query_ope_order_api.py
"""
运营端 - 订单列表查询接口测试
接口：POST /hzsx/ope/order/queryOpeOrderByCondition
覆盖场景：订单号、下单人姓名、订单状态、店铺名称、商品编码、APP来源、渠道来源、
下单时间范围、下单人手机号、组合查询、空条件查询

数据策略：模块级懒加载，SQL 只执行一次，结果缓存供所有用例复用
"""
import allure
import pytest
from datetime import datetime, timedelta
from common.database import DatabaseManager
from common.logger import logger
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables


_DATA_FILE = "data/admin/api/order/query_ope_order_api.yaml"

# 预加载 SQL（默认只查询 ct_user_orders 表，避免跨库权限问题）
_PRELOAD_SQL = (
    "SELECT o.order_id, o.product_id, o.user_name, o.status, o.shop_id "
    "FROM llxz_order.ct_user_orders o "
    "WHERE o.shop_id = '71008738021cd3393bacbac182bd6a86af0b5c87' "
    "AND o.status = '06' "
    "ORDER BY o.create_time DESC LIMIT 1"
)


@pytest.fixture(scope="module")
def preloaded_order_data():
    """模块级懒加载：首次执行 SQL 并返回字典结果，所有用例共享该 fixture 的返回值。
    使用 fixture 替代模块级全局缓存，更适配 pytest 的执行模型和并行场景。
    """
    try:
        with DatabaseManager() as db:
            result = db.fetch_one(_PRELOAD_SQL)
    except Exception as e:
        logger.error(f"[OQ_OPE] 预查询数据库失败: {e}")
        return {}
    if result:
        data = {k: str(v) for k, v in result.items()}
        logger.info(f"[OQ_OPE] SQL 预查询完成: {data}")
        return data
    else:
        logger.warning("[OQ_OPE] SQL 预查询未获取到数据")
        return {}


@allure.epic("运营端")
@allure.feature("运营端-订单管理")
@allure.story("订单列表查询")
class TestQueryOpeOrder:
    """运营端订单列表查询 - 11 个查询场景"""

    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    @staticmethod
    def _add_dynamic_time_vars(global_vars: dict) -> dict:
        """动态计算下单时间范围并注入变量：
        create_time_start = 当前时间
        create_time_end   = 当前时间往后推 30 天
        """
        now = datetime.now()
        past_days = now + timedelta(days=-30)
        global_vars["create_time_start"] = past_days.strftime("%Y-%m-%d 00:00:00")
        global_vars["create_time_end"] = now.strftime("%Y-%m-%d 23:59:59")
        return global_vars

    @pytest.mark.parametrize(
        "case",
        get_test_data(_DATA_FILE, "ope_order_query_tests"),
        ids=[c["case_id"] for c in get_test_data(_DATA_FILE, "ope_order_query_tests")],
    )
    def test_query_ope_order(self, admin_api_client, db, case, preloaded_order_data):
        # 1. 加载全局变量
        global_vars = self._load_global_vars()

        # 2. 注入预查询的订单数据（SQL 只执行一次，所有用例共享缓存）
        order_data = preloaded_order_data
        if not order_data:
            pytest.skip("SQL 预查询未获取到订单数据，跳过本次测试")
        global_vars.update(order_data)

        # 3. 合并用例级别变量（如果有）
        if "variables" in case and isinstance(case["variables"], dict):
            global_vars.update(case["variables"])

        # 4. 动态注入时间范围变量（用于下单时间查询场景 OQ_OPE_008）
        global_vars = self._add_dynamic_time_vars(global_vars)

        # 5. 更新 Allure 标题
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")

        # 6. 执行测试（框架自动处理变量替换、API 请求、断言）
        execute_test_case(case, admin_api_client, db, global_vars)