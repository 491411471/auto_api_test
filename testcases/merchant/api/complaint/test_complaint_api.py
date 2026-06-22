# testcases/api/complaint/test_complaint_api.py
import json

import allure
import yaml
import os
from common.test_helpers import execute_test_case, validate_response
from utils.data_generator import generate_random_value
from common.logger import logger

def load_yaml(yaml_path):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
yaml_path = os.path.join(os.path.dirname(__file__), "../../../../data/merchant/api/complaint/complaint_api.yaml")
# 合并全局变量与用例私有变量
config = load_yaml(yaml_path)
variables = config.get("variables", {})
@allure.epic("商家端")
@allure.feature("投诉管理")
@allure.story("小程序投诉商家")
class TestComplaintAPI:
    @allure.title("完整流程：小程序发起投诉 → 查询投诉订单 → 查看投诉详情")
    def test_full_complaint_flow(self, merchant_api_client, db, global_vars):
        """ 完整投诉流程：
    #       1. 从数据库获取可投诉订单（user_name, order_id, uid）
    #       2. 发起投诉
    #       3. 根据 order_id 查询投诉记录，验证存在"""
        # ---------- 步骤1：小程序发起投诉 ----------
        case = next((c for c in config["complaint_tests"] if c['case_id'] == "CP_001"), None)
        sql = case['sql']['query']
        # 步骤1：从数据库获取订单信息
        with allure.step("从数据库获取可投诉订单"):
            result = db.fetch_one(sql)
            assert result, "未找到可投诉订单"
            user_name = result['user_name']
            order_id = result['order_id']
            uid = result['uid']
            logger.info(f"获取到订单: order_id={order_id}, uid={uid}, user_name={user_name}")
        # 封装请求参数
        request_json=case["json"]
        request_json["name"] = user_name
        request_json["orderId"] = order_id
        request_json["uid"] = uid
        request_json["telphone"] = generate_random_value("phone")
        print("request_json:", request_json)
        allure.attach(f"发起投诉的请求参数: {json.dumps(request_json, indent=4, ensure_ascii=False)}", "请求参数", allure.attachment_type.JSON)
        # 步骤2：发起投诉
        with allure.step("发起投诉请求"):
            resp = merchant_api_client.post("/llxz-api-web/hzsx/aliPay/orderComplaints/addOrderComplaints", json=request_json)
            assert resp.status_code == 200
            resp_data = resp.json()
            assert resp_data.get('businessSuccess') is True, f"投诉失败: {resp_data.get('errorMessage')}"
            logger.info("投诉发起成功")
        allure.attach(f"发起投诉的响应结果: {json.dumps(resp_data, indent=4, ensure_ascii=False)}", "响应结果", allure.attachment_type.JSON)
        # 步骤3：根据 order_id 查询投诉记录
        query_payload = { "pageNumber": 1,
                          "pageSize": 10,
                          "orderId": order_id,
                          "complaintCreateTime": None,
                          "sourceType": "",
                          "complaintsType": "",
                          "rentType": "",
                          "status": ""
                         }
        with allure.step(f"查询订单 {order_id} 的投诉记录"):
            resp = merchant_api_client.post("/hzsx/orderComplaints/queryShopOrderComplaintsPage", json=query_payload)
            assert resp.status_code == 200
            query_data = resp.json()
            case = next((c for c in config["complaint_tests"] if c['case_id'] == "CP_001"), None)
            validate_response(case, query_data, variables)

    def test_withdrawn_complaint_flow(self, merchant_api_client, db, global_vars):
        """投诉订单查询：app来源"""
        case = next((c for c in config["complaint_tests"] if c['case_id'] == "CP_002"), None)
        # 如果用例内部定义了 variables，合并（用例级优先级更高）
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])

        # 执行标准测试流程（SQL处理、请求、基础断言、post_sql）
        execute_test_case(case, merchant_api_client, db, global_vars)

    def test_complaint_orders_by_rent_type(self, merchant_api_client, db, global_vars):
        """按租期类型查询投诉订单"""
        case = next((c for c in config["complaint_tests"] if c['case_id'] == "CP_003"), None)
        # 如果用例内部定义了 variables，合并（用例级优先级更高）
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        # 执行标准测试流程（SQL处理、请求、基础断言、post_sql）
        execute_test_case(case, merchant_api_client, db, global_vars)

    def test_complaint_orders_by_type(self, merchant_api_client, db, global_vars):
        """按涉诉类型查询投诉订单"""
        case = next((c for c in config["complaint_tests"] if c['case_id'] == "CP_004"), None)
        # 如果用例内部定义了 variables，合并（用例级优先级更高）
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        # 执行标准测试流程（SQL处理、请求、基础断言、post_sql）
        execute_test_case(case, merchant_api_client, db, global_vars)

    def test_complaint_orders_by_channel(self, merchant_api_client, db, global_vars):
        """按渠道来源查询投诉订单"""
        case = next((c for c in config["complaint_tests"] if c['case_id'] == "CP_004"), None)
        # 如果用例内部定义了 variables，合并（用例级优先级更高）
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        # 执行标准测试流程（SQL处理、请求、基础断言、post_sql）
        execute_test_case(case, merchant_api_client, db, global_vars)