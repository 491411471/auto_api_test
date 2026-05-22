import allure
import os
import random
import yaml
from common.logger import logger
from utils.variable_utils import validate, get_value_by_path


def load_yaml(yaml_path):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@allure.feature("补押金-商家端")
@allure.story("补押金完整流程")
class TestAddDepositOrder:

    @allure.title("完整流程：查询可补订单 → 补押金 → 验证补押金记录（金额+订单号）")
    def test_add_deposit_order_flow(self, merchant_api_client, db, global_vars):
        yaml_path = os.path.join(os.path.dirname(__file__), "../../../data/scenario/order/add_deposit_order.yaml")
        config = load_yaml(yaml_path)
        base_vars = global_vars.copy()

        shop_id = base_vars.get('shop_id', '71008738021cd3393bacbac182bd6a86af0b5c87')
        deposit_amount = config.get('deposit_amount', 1)

        # ---------- 步骤1：查询符合条件的订单号 ----------
        with allure.step("1. 查询可补押金的订单号"):
            order_list = config['merchant']['order_list']
            order_id = random.choice(order_list)
            logger.info(f"获取到订单号: {order_id}")
            allure.attach(order_id, name="订单号", attachment_type=allure.attachment_type.TEXT)

        # ---------- 步骤2：调用补押金接口 ----------
        with allure.step("2. 补押金接口调用"):
            add_cfg = config['merchant']['add_deposit_order']
            body = add_cfg['body_template'].copy()
            body['orderId'] = order_id
            body['amount'] = deposit_amount

            resp = merchant_api_client.post(add_cfg['endpoint'], json=body)
            assert resp.status_code == add_cfg['expected_status']
            resp_json = resp.json()
            logger.info(f"补押金响应: {resp_json}")

            # 执行通用断言
            for check in add_cfg['validate']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                operator = check['operator']
                expected = check['value']
                validate(actual, operator, expected, path)

            allure.attach(str(resp_json), name="补押金响应", attachment_type=allure.attachment_type.JSON)

        # ---------- 步骤3：查询补押金记录并验证金额和订单号 ----------
        with allure.step("3. 查询补押金记录，验证金额和原始订单号"):
            query_cfg = config['merchant']['get_deposit_order_list']
            query_body = query_cfg['body_template'].copy()
            query_body['orderId'] = order_id
            query_body['shopId'] = shop_id

            resp = merchant_api_client.post(query_cfg['endpoint'], json=query_body)
            assert resp.status_code == query_cfg['expected_status']
            resp_json = resp.json()
            logger.info(f"查询补押金记录响应: {resp_json}")

            # 基础断言：businessSuccess 和 records 非空
            assert resp_json.get('businessSuccess') is True, "businessSuccess 不为 true"
            records = resp_json.get('data', {}).get('records', [])
            assert len(records) > 0, "补押金记录列表为空"

            # 查找与原始订单号匹配的最新记录（假设记录按创建时间降序排列，records[0] 为最新）
            # 如果有多个补押金记录，取第一个匹配 originalOrderId 的
            matched_record = None
            for record in records:
                if record.get('originalOrderId') == order_id:
                    matched_record = record
                    break

            assert matched_record is not None, f"未找到 originalOrderId 为 {order_id} 的补押金记录"

            actual_amount = matched_record.get('currentDepositAmount')
            assert actual_amount == deposit_amount, f"补押金金额不一致: 期望 {deposit_amount}, 实际 {actual_amount}"

            # 可选：验证其他关键字段
            logger.info(f"验证通过: originalOrderId={order_id}, currentDepositAmount={actual_amount}")
            allure.attach(f"originalOrderId: {order_id}, amount: {actual_amount}",
                          name="验证结果", attachment_type=allure.attachment_type.TEXT)

            # 也可以对 records[0] 执行完整的 schema 校验，此处按需添加
            # 例如验证 orderStatus、paymentNo 等非空
            assert matched_record.get('orderStatus') == '01', "订单状态不是'01'(待支付)"
            assert matched_record.get('paymentNo') is not None, "支付单号为空"

        logger.info("补押金流程执行成功")