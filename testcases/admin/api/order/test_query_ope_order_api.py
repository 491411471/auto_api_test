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

# 模块级缓存：SQL 只查一次
_cached_order_data: dict | None = None

_PRELOAD_SQL = (
    # 仅查询 ct_user_orders 表，不 JOIN ct_shops，避免跨库权限问题
    "SELECT o.order_id, o.product_id, o.user_name, o.status, o.shop_id "
    "FROM llxz_order.ct_user_orders o "
    "WHERE o.shop_id = '71008738021cd3393bacbac182bd6a86af0b5c87' "
    "AND o.status = '06' "
    "ORDER BY o.create_time DESC LIMIT 1"
)


def _fetch_order_data(db) -> dict:
    """懒加载：首次调用执行 SQL 并缓存，后续直接返回缓存结果"""
    global _cached_order_data
    if _cached_order_data is not None:
        return _cached_order_data
    # 尝试从 YAML 的 variables 中读取预查询 SQL（便于测试配置化）
    try:
        globals_from_yaml = get_global_variables(_DATA_FILE)
    except Exception:
        globals_from_yaml = {}
    # 从 YAML variables 获取 shop_id，替换 SQL 中的 ${shop_id} 占位符
    shop_id = globals_from_yaml.get("shop_id", "71008738021cd3393bacbac182bd6a86af0b5c87")
    raw_sql = globals_from_yaml.get("preload_sql", _PRELOAD_SQL)
    sql = raw_sql.replace("${shop_id}", shop_id)
    logger.info(f"[OQ_OPE] 执行预查询 SQL: {sql[:200]}")
    result = db.fetch_one(sql)
    if result:
        _cached_order_data = {k: str(v) for k, v in result.items()}
        logger.info(f"[OQ_OPE] SQL 预查询完成: {_cached_order_data}")
    else:
        _cached_order_data = {}
        logger.warning("[OQ_OPE] SQL 预查询未获取到数据")
    return _cached_order_data


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
    def test_query_ope_order(self, admin_api_client, db, case):
        # 1. 加载全局变量
        global_vars = self._load_global_vars()

        # 2. 注入预查询的订单数据（SQL 只执行一次，所有用例共享缓存）
        order_data = _fetch_order_data(db)
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
