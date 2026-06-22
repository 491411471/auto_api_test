# testcases/api/order/test_rental_order_api.py
import allure
import json
import pytest
from common.test_helpers import execute_test_case
from common.logger import logger
from utils.data_loader import get_test_data, get_global_variables

# ==================== 模块级共享：获取第一个逾期待分配订单 ====================
_first_order_info_cache = None
_first_order_fetched = False


def _fetch_first_overdue_order(api_client):
    """
    获取第一个逾期订单的关键信息（带降级查询）。
    
    查询策略：
      1. 优先查询未分配逾期订单（assignStatus="0"）
      2. 若无结果，降级查询任意逾期订单（不限分配状态）
    模块级缓存，多次调用仅请求一次API。
    返回 dict 或 None。
    """
    global _first_order_info_cache, _first_order_fetched
    if _first_order_fetched:
        return _first_order_info_cache
    _first_order_fetched = True

    # 查询策略：先严格查询，再降级放宽
    queries = [
        ("未分配逾期订单", {
            "followTimeDesc": 0,
            "assignStatus": "0",
            "pageNum": 1,
            "pageSize": 10,
            "tabName": "0",
            "overdueTime": "0",
            "overdueDaysDesc": 1
        }),
        ("任意逾期订单（降级）", {
            "followTimeDesc": 0,
            "pageNum": 1,
            "pageSize": 10,
            "tabName": "0",
            "overdueTime": "0",
            "overdueDaysDesc": 1
        }),
    ]

    try:
        for desc, payload in queries:
            with allure.step(f"前置步骤：查询{desc}"):
                resp = api_client.post("/hzsx/dcm/order/list", json=payload)
                data = resp.json()
                records = data.get("data", {}).get("records", [])
                if records:
                    first = records[0]
                    _first_order_info_cache = {
                        "first_order_id": first.get("orderId"),
                        "first_user_name": first.get("userName"),
                        "first_responsible_name": first.get("responsibleName"),
                        "first_channel_id": first.get("channelId"),
                        "first_overdue_days": first.get("overdueDays"),
                    }
                    allure.attach(
                        json.dumps(_first_order_info_cache, ensure_ascii=False, indent=2),
                        name=f"获取到{desc}",
                        attachment_type=allure.attachment_type.JSON
                    )
                    return _first_order_info_cache
                else:
                    allure.attach(
                        f"查询{desc}无结果，尝试下一策略",
                        name="查询结果",
                        attachment_type=allure.attachment_type.TEXT
                    )

        allure.attach(
            "所有查询策略均无结果，后续依赖用例将被跳过",
            name="前置-查询结果",
            attachment_type=allure.attachment_type.TEXT
        )
    except Exception as e:
        allure.attach(f"获取订单失败: {str(e)}", name="前置-异常",
                      attachment_type=allure.attachment_type.TEXT)

    return _first_order_info_cache

@allure.epic("商家端")
@allure.feature("商家端-租后管理模块")
@allure.story("租后订单查询")
class TestRentalOrderQuery:
    """租后订单列表查询接口测试"""
    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("rental_order_api.yaml")
        return cls._global_vars.copy()

    @pytest.mark.smoke
    @pytest.mark.parametrize(
        "case",
        get_test_data("rental_order_api.yaml", "rental_order_query_tests"),
        ids=lambda case: case['case_id']
    )
    def test_rental_order_query(self, merchant_api_client, db, case):
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])

        # 如果用例中引用了 ${first_* 占位符，则获取第一个逾期待分配订单信息并注入
        case_str = json.dumps(case, ensure_ascii=False)
        if '${first_' in case_str:
            order_info = _fetch_first_overdue_order(merchant_api_client)
            if not order_info:
                skip_msg = f"未找到逾期待分配订单，跳过用例 {case['case_id']}"
                allure.attach(
                    f"{skip_msg}\n\n"
                    f"查询策略:\n"
                    f"1. assignStatus=0 + overdueTime=0（未分配逾期）\n"
                    f"2. overdueTime=0（任意逾期，降级）\n"
                    f"接口: /hzsx/dcm/order/list",
                    name="跳过原因",
                    attachment_type=allure.attachment_type.TEXT
                )
                pytest.skip(skip_msg)
            global_vars.update(order_info)
            logger.info(f"[{case['case_id']}] 注入订单信息: order_id={order_info.get('first_order_id')}, "
                        f"user_name={order_info.get('first_user_name')}, "
                        f"responsible_name={order_info.get('first_responsible_name')}")

        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)

@allure.epic("商家端")
@allure.feature("商家端-租后管理")
@allure.story("租后订单-批量发送短信")
class TestRentalOrderSms:
    """租后订单批量发送短信接口测试"""
    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("rental_order_api.yaml")
        return cls._global_vars.copy()

    def test_batch_rental_order_sms(self, merchant_api_client, db):
        global_vars = self._load_global_vars()
        case = next((c for c in get_test_data("rental_order_api.yaml", "rental_order_sms_tests") if c['case_id'] == "ROS_001"), None)
        print("case:",case)
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")

        order_info = _fetch_first_overdue_order(merchant_api_client)
        if not order_info:
            skip_msg = f"未找到逾期待分配订单，跳过用例 {case['case_id']}"
            allure.attach(
                f"{skip_msg}\n\n"
                f"查询策略:\n"
                f"1. assignStatus=0 + overdueTime=0（未分配逾期）\n"
                f"2. overdueTime=0（任意逾期，降级）\n"
                f"接口: /hzsx/dcm/order/list",
                name="跳过原因",
                attachment_type=allure.attachment_type.TEXT
            )
            pytest.skip(skip_msg)
        global_vars.update(order_info)

        execute_test_case(case, merchant_api_client, db, global_vars)

    # def test_debt_order_sms(self, api_client, db):
    #     global_vars = self._load_global_vars()
    #     case = next((c for c in get_test_data("rental_order_api.yaml", "rental_order_sms_tests") if c['case_id'] == "ROS_002"), None)
    #     print("case:",case)
    #     if 'variables' in case and isinstance(case['variables'], dict):
    #         global_vars.update(case['variables'])
    #     allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
    #
    #     order_info = _fetch_first_overdue_order(api_client)
    #     if not order_info:
    #         skip_msg = f"未找到逾期待分配订单，跳过用例 {case['case_id']}"
    #         allure.attach(
    #             f"{skip_msg}\n\n"
    #             f"查询策略:\n"
    #             f"1. assignStatus=0 + overdueTime=0（未分配逾期）\n"
    #             f"2. overdueTime=0（任意逾期，降级）\n"
    #             f"接口: /hzsx/dcm/order/list",
    #             name="跳过原因",
    #             attachment_type=allure.attachment_type.TEXT
    #         )
    #         pytest.skip(skip_msg)
    #     global_vars.update(order_info)
    #
    #     execute_test_case(case, api_client, db, global_vars)


# @allure.feature("商家端-租后管理模块")
# @allure.story("租后订单-批量分配责任人")
# class TestRentalOrderAssign:
#     """租后订单批量分配责任人接口测试"""
#     _global_vars = None
#
#     @classmethod
#     def _load_global_vars(cls):
#         if cls._global_vars is None:
#             cls._global_vars = get_global_variables("rental_order_api.yaml")
#         return cls._global_vars.copy()
#
#     @pytest.mark.parametrize(
#         "case",
#         get_test_data("rental_order_api.yaml", "rental_order_assign_tests"),
#         ids=[case['case_id'] for case in get_test_data("rental_order_api.yaml", "rental_order_assign_tests")]
#     )
#     def test_rental_order_assign(self, api_client, db, case):
#         global_vars = self._load_global_vars()
#         if 'variables' in case and isinstance(case['variables'], dict):
#             global_vars.update(case['variables'])
#         allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
#
#         # ROA_001: memberIdOrderMap 的 key 是动态的 backstage_user_id，
#         # 框架无法在 YAML 中替换 dict key，需要 Python 侧构建 JSON
#         if case.get('custom_json'):
#             self._execute_custom_assign(case, api_client, db, global_vars)
#         else:
#             execute_test_case(case, api_client, db, global_vars)
#
#     @staticmethod
#     def _execute_custom_assign(case, api_client, db, variables):
#         """自定义执行分配责任人用例，动态构建 memberIdOrderMap"""
#         import json
#         from common.test_helpers import (
#             replace_placeholders, process_dynamic_data,
#             validate_response, assert_status_code
#         )
#         from common.logger import logger
#
#         # 1. 替换 SQL 中的占位符并执行
#         with allure.step("执行 SQL 获取待分配订单及对应后台用户"):
#             case_replaced = replace_placeholders(case, variables)
#             process_dynamic_data(case_replaced, db, variables)
#
#         sql_result = variables.get('sql_result', [])
#         logger.info(f"SQL 查询结果: {sql_result}")
#         allure.attach(json.dumps(sql_result, ensure_ascii=False, indent=2),
#                       name="SQL 查询结果", attachment_type=allure.attachment_type.JSON)
#
#         # 2. 按 backstage_user_id 分组构建 memberIdOrderMap
#         member_id_order_map = {}
#         for row in sql_result:
#             uid = str(row.get('backstage_user_id', ''))
#             oid = row.get('order_id', '')
#             if not uid or not oid:
#                 continue
#             if uid not in member_id_order_map:
#                 member_id_order_map[uid] = []
#             member_id_order_map[uid].append(oid)
#
#         logger.info(f"构建的 memberIdOrderMap: {member_id_order_map}")
#         allure.attach(json.dumps(member_id_order_map, ensure_ascii=False, indent=2),
#                       name="memberIdOrderMap", attachment_type=allure.attachment_type.JSON)
#
#         # 3. 构建请求体
#         body = {
#             "memberIdOrderMap": member_id_order_map
#         }
#         # 合并 variables 中的 shop_id（如果有）
#         if variables.get('shop_id'):
#             body['shopId'] = variables['shop_id']
#
#         logger.info(f"请求体: {body}")
#         allure.attach(json.dumps(body, ensure_ascii=False, indent=2),
#                       name="请求体 (JSON)", attachment_type=allure.attachment_type.JSON)
#
#         # 4. 发送请求
#         with allure.step(f"发送 POST {case['endpoint']}"):
#             resp = api_client.post(case['endpoint'], json=body)
#             logger.info(f"响应状态码: {resp.status_code}")
#
#             response_data = resp.json()
#             response_str = json.dumps(response_data, ensure_ascii=False)[:5000]
#             allure.attach(response_str, name="完整响应体", attachment_type=allure.attachment_type.JSON)
#
#         # 5. 断言验证
#         assert_status_code(resp.status_code, case.get('expected_status', 200))
#         # 替换 validate_data 中的占位符
#         case_with_vars = replace_placeholders(case, variables)
#         validate_response(case_with_vars, response_data, variables)
#
#         logger.info(f"测试通过: {case['case_id']} - {case['title']}")
#

