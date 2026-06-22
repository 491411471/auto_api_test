"""
订单详情接口测试用例
接口：/hzsx/dcm/order/detailOrder
对应页面：已分配订单列表页 -> 操作列"详情"按钮
测试策略：通过调用 /hzsx/dcm/order/list 接口动态获取已分配逾期订单号，
         若无逾期订单则跳过依赖订单号的用例；异常用例（OD_007/OD_008）不受影响。
"""
import allure
import pytest
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables
@allure.epic("商家端")
@allure.feature("商家端-租后管理")
@allure.story("订单详情查询")
class TestOrderDetail:
    _global_vars = None
    _cached_order_id = None
    _order_id_fetched = False

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("order_detail_api.yaml")
        return cls._global_vars.copy()

    @classmethod
    def _get_overdue_order_id(cls, api_client):
        """从已分配逾期订单列表接口获取第一个订单号（类级别缓存，带降级查询）"""
        if cls._order_id_fetched:
            return cls._cached_order_id
        cls._order_id_fetched = True

        queries = [
            ("已分配逾期订单", {
                "overdueTime": "0",
                "assignStatus": "1",
                "overdueDaysDesc": 1,
                "followTimeDesc": 0,
                "pageNum": 1,
                "pageSize": 10,
                "tabName": "0"
            }),
            ("未分配逾期订单", {
                "assignStatus": "0",
                "overdueTime": "0",
                "overdueDaysDesc": 1,
                "followTimeDesc": 0,
                "pageNum": 1,
                "pageSize": 10,
                "tabName": "0"
            }),
        ]

        try:
            for desc, payload in queries:
                with allure.step(f"前置步骤：查询{desc}"):
                    resp = api_client.post("/hzsx/dcm/order/list", json=payload)
                    data = resp.json()
                    records = data.get("data", {}).get("records", [])
                    if records:
                        cls._cached_order_id = records[0].get("orderId")
                        allure.attach(
                            f"查询{desc}成功: {cls._cached_order_id}\n共 {len(records)} 条记录",
                            name="前置-获取订单号成功",
                            attachment_type=allure.attachment_type.TEXT
                        )
                        return cls._cached_order_id
                    else:
                        allure.attach(
                            f"查询{desc}无结果，尝试下一策略",
                            name="查询结果"
                        )

            allure.attach(
                "所有查询策略均无结果\n接口: /hzsx/dcm/order/list",
                name="前置-获取订单号结果",
                attachment_type=allure.attachment_type.TEXT
            )
        except Exception as e:
            allure.attach(f"获取逾期订单失败: {str(e)}", name="前置-获取订单号异常",
                          attachment_type=allure.attachment_type.TEXT)

        return cls._cached_order_id

    @pytest.mark.smoke
    @pytest.mark.parametrize(
        "case",
        get_test_data("order_detail_api.yaml", "order_detail_tests"),
        ids=lambda case: case['case_id']
    )
    def test_order_detail(self, api_client, db, case):
        """参数化执行订单详情接口测试用例"""
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])

        # 判断当前用例是否需要从列表接口动态获取 order_id
        json_body = case.get('json', {})
        needs_order_id = '${order_id}' in str(json_body.get('orderId', ''))

        if needs_order_id:
            order_id = self._get_overdue_order_id(api_client)
            if not order_id:
                skip_msg = f"没有逾期订单，跳过用例 {case['case_id']}"
                allure.attach(
                    f"{skip_msg}\n\n"
                    f"查询策略:\n"
                    f"1. assignStatus=1 + overdueTime=0（已分配逾期）\n"
                    f"2. overdueTime=0（任意逾期，降级）\n"
                    f"接口: /hzsx/dcm/order/list",
                    name="跳过原因",
                    attachment_type=allure.attachment_type.TEXT
                )
                pytest.skip(skip_msg)
            global_vars['order_id'] = order_id

        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)
