# testcases/merchant/api/order/test_update_delivery_address_api.py
# -*- coding: utf-8 -*-
"""
修改订单收货地址 完整流程测试

流程：
  步骤0  SQL 查询可修改收货地址的订单（status='13'，下单待审核）→ 获取 order_id、uid
  步骤1  POST /hzsx/userAddress/addUserAddress        → 获取 new_address_id（响应 data 字段）
  步骤2  POST /hzsx/api/order/updateOrderDeliveryAddress → 用 new_address_id 修改收货地址
  步骤3  POST /hzsx/business/order/getOrderDeliveryAddressUpdatePage → 查询并验证修改记录
"""
import json

import allure
import pytest

from common.logger import logger
from common.test_helpers import replace_placeholders, validate_response
from utils.data_loader import get_test_data, get_global_variables

# ==================== 预加载 YAML 数据 ====================
_DATA_FILE = "data/merchant/api/order/update_delivery_address_api.yaml"
_ALL_CASES = get_test_data(_DATA_FILE, "update_delivery_address_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 update_delivery_address_api.yaml")


def _get_case(case_id: str) -> dict:
    for case in _ALL_CASES:
        if case.get("case_id") == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")


# ==================== 测试类 ====================
@allure.epic("商家端")
@allure.feature("订单模块--修改订单收货地址")
@allure.story("修改订单收货地址")
class TestUpdateDeliveryAddressAPI:
    """修改订单收货地址完整流程测试"""

    @allure.title("UDA_001 - 修改订单收货地址完整流程")
    def test_update_delivery_address_full_flow(self, merchant_api_client, db, global_vars):
        case = _get_case("UDA_001")
        variables = {**global_vars}
        # 合并 YAML 顶层 variables（包含 excluded_order_id 等）
        yaml_vars = get_global_variables(_DATA_FILE)
        variables.update(yaml_vars)
        if "variables" in case and isinstance(case["variables"], dict):
            variables.update(case["variables"])

        # ------------------------------------------------------------------
        # 步骤0：从数据库获取可修改收货地址的订单
        # ------------------------------------------------------------------
        with allure.step("步骤0：从数据库获取可修改收货地址的订单（status='13'）"):
            sql_config = case["sql"]
            sql_query = replace_placeholders(sql_config["query"], variables)
            allure.attach(sql_query, name="执行 SQL", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"执行 SQL: {sql_query}")
            row = db.fetch_one(sql_query)
            if not row:
                skip_msg = "未查询到可修改收货地址的订单（status='13'，下单待审核），跳过本用例"
                allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                logger.warning(skip_msg)
                pytest.skip(skip_msg)

            variables["order_id"] = row["order_id"]
            variables["uid"] = row["uid"]
            allure.attach(
                f"order_id={row['order_id']}\nuid={row['uid']}",
                name="SQL 结果",
                attachment_type=allure.attachment_type.TEXT,
            )
            logger.info(f"获取到订单: order_id={row['order_id']}, uid={row['uid']}")

        # ------------------------------------------------------------------
        # 步骤1：新增用户收货地址，获取 new_address_id
        # ------------------------------------------------------------------
        with allure.step("步骤1：新增用户收货地址"):
            from faker import Faker
            fake = Faker("zh_CN")
            step1 = replace_placeholders(case["step1"], variables)
            step1_body = step1["json"]

            # 使用 Faker 动态生成并更新地址相关字段
            step1_body["realname"] = fake.name()
            step1_body["street"] = fake.street_address()
            # 保存动态值供步骤3断言使用
            variables["test_street"] = step1_body["street"]
            variables["test_realname"] = step1_body["realname"]

            allure.attach(
                json.dumps(step1_body, ensure_ascii=False, indent=2),
                name="步骤1 请求参数",
                attachment_type=allure.attachment_type.JSON,
            )

            resp1 = merchant_api_client.post(step1["endpoint"], json=step1_body)
            resp1_data = resp1.json()
            print("resp1_data:", resp1_data)
            allure.attach(
                json.dumps(resp1_data, ensure_ascii=False, indent=2),
                name="步骤1 响应结果",
                attachment_type=allure.attachment_type.JSON,
            )

            assert resp1.status_code == step1["expected_status"], (
                f"步骤1 状态码异常: 期望 {step1['expected_status']}, 实际 {resp1.status_code}"
            )
            assert resp1_data.get("businessSuccess") is True, (
                f"步骤1 新增地址失败: {resp1_data.get('errorMessage')}"
            )

            new_address_id = resp1_data.get("data")
            assert new_address_id is not None, "步骤1 响应 data 为空，无法获取 new_address_id"
            variables["new_address_id"] = new_address_id

            allure.attach(
                f"new_address_id = {new_address_id}",
                name="步骤1 断言结果",
                attachment_type=allure.attachment_type.TEXT,
            )
            logger.info(f"步骤1 新增地址成功，new_address_id={new_address_id}")

        # ------------------------------------------------------------------
        # 步骤2：修改订单收货地址
        # ------------------------------------------------------------------
        with allure.step("步骤2：修改订单收货地址"):
            step2 = replace_placeholders(case["step2"], variables)
            step2_body = step2["json"]

            # 执行前置 SQL（如清理旧记录），若 YAML 中配置了 pre_sql 则自动执行
            if step2.get("pre_sql"):
                pre_sql_query = step2["pre_sql"]["query"].strip()
                allure.attach(pre_sql_query, name="步骤2 前置清理 SQL", attachment_type=allure.attachment_type.TEXT)
                affected_rows = db.execute_delete(pre_sql_query)
                allure.attach(
                    f"affected_rows={affected_rows}",
                    name="步骤2 pre_sql 执行结果",
                    attachment_type=allure.attachment_type.TEXT,
                )
                logger.info(f"步骤2 pre_sql 清理完成，影响行数: {affected_rows}")

            allure.attach(
                json.dumps(step2_body, ensure_ascii=False, indent=2),
                name="步骤2 请求参数",
                attachment_type=allure.attachment_type.JSON,
            )

            resp2 = merchant_api_client.post(step2["endpoint"], json=step2_body)
            resp2_data = resp2.json()
            allure.attach(
                json.dumps(resp2_data, ensure_ascii=False, indent=2),
                name="步骤2 响应结果",
                attachment_type=allure.attachment_type.JSON,
            )
            # 执行 YAML 中步骤2 的断言规则（如 $.data == true）
            if step2.get("validate_data"):
                validate_response(step2, resp2_data, variables)

            allure.attach(
                f"businessSuccess=True, data={resp2_data.get('data')}",
                name="步骤2 断言结果",
                attachment_type=allure.attachment_type.TEXT,
            )
            logger.info(f"步骤2 修改收货地址成功，order_id={variables['order_id']}")

        # ------------------------------------------------------------------
        # 步骤3：查询收货地址修改记录并验证
        # ------------------------------------------------------------------
        with allure.step("步骤3：查询收货地址修改记录并验证"):
            step3 = replace_placeholders(case["step3"], variables)
            step3_body = step3["json"]

            allure.attach(
                json.dumps(step3_body, ensure_ascii=False, indent=2),
                name="步骤3 请求参数",
                attachment_type=allure.attachment_type.JSON,
            )

            resp3 = merchant_api_client.post(step3["endpoint"], json=step3_body)
            resp3_data = resp3.json()

            allure.attach(
                json.dumps(resp3_data, ensure_ascii=False, indent=2),
                name="步骤3 响应结果",
                attachment_type=allure.attachment_type.JSON,
            )

            assert resp3.status_code == step3["expected_status"], (
                f"步骤3 状态码异常: 期望 {step3['expected_status']}, 实际 {resp3.status_code}"
            )
            assert resp3_data.get("businessSuccess") is True, (
                f"步骤3 查询失败: {resp3_data.get('errorMessage')}"
            )

            # 执行 YAML 中定义的断言规则（rpcResult、businessSuccess、records 等）
            validate_response(case, resp3_data, variables)

            # 业务断言：验证新地址包含步骤1动态生成的地址和姓名
            records = resp3_data.get("data", {}).get("records", [])
            assert len(records) > 0, "收货地址修改记录为空"
            new_user_address = records[0].get("newUserAddress", "")
            expected_street = variables.get("test_street", "")
            expected_realname = variables.get("test_realname", "")
            assert expected_street in new_user_address, (
                f"新地址未包含街道'{expected_street}'，实际值: {new_user_address}"
            )
            assert expected_realname in new_user_address, (
                f"新地址未包含姓名'{expected_realname}'，实际值: {new_user_address}"
            )

            allure.attach(
                f"records 数量={len(records)}\n"
                f"newUserAddress={new_user_address}\n"
                f"期望包含: street={expected_street}, realname={expected_realname}",
                name="步骤3 断言结果",
                attachment_type=allure.attachment_type.TEXT,
            )
            logger.info(f"步骤3 验证通过，新地址: {new_user_address}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--alluredir=reports/allure_results"])
