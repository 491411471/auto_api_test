import allure
import os
import pytest
import yaml
import time
from common.logger import logger
from .base_complete_apply import BaseCompleteApplyFlow

def load_yaml(yaml_path):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
@allure.epic("商家端")
@allure.feature("订单完结申请-商家端+运营端")
@allure.story("审核通过流程")
class TestCompleteApplyApprove:

    @allure.title("完整流程：商家提交完结申请 → 运营审核通过（含自动重试）")
    def test_approve_flow(self, merchant_api_client, admin_api_client, db, global_vars):
        yaml_path = os.path.join(os.path.dirname(__file__),
                                 "../../../../data/merchant/scenario/order/complete_apply_approve.yaml")
        config = load_yaml(yaml_path)
        base_vars = global_vars.copy()

        # 从 YAML 读取重试配置，若无则使用默认值
        retry_cfg = config.get('retry_config', {})
        max_retries = retry_cfg.get('max_attempts', 3)
        retry_interval = retry_cfg.get('interval_seconds', 2)
        error_keyword = retry_cfg.get('error_keyword', '支付宝状态推进异常')

        for attempt in range(1, max_retries + 1):
            logger.info(f"========== 第 {attempt} 次尝试执行审核通过流程 ==========")
            allure.attach(f"第 {attempt} 次尝试", name="重试次数", attachment_type=allure.attachment_type.TEXT)
            variables = base_vars.copy()

            # 商家端完整流程：查询订单 → 上传图片 → 提交申请
            order_id, voucher_url = BaseCompleteApplyFlow.execute_merchant_actions(
                config, merchant_api_client, db, variables
            )

            # 如果数据库中未找到可完结的订单，跳过整个测试用例
            if order_id is None:
                pytest.skip("未查询到可完结的订单，跳过此用例")

            apply_id = BaseCompleteApplyFlow.execute_admin_query(config, admin_api_client, order_id)

            # 运营审核通过
            with allure.step("5. 运营审核通过"):
                approve_cfg = config['admin']['approve']
                body = approve_cfg['body_template']
                body['orderId'] = order_id
                body['applyId'] = apply_id
                resp = admin_api_client.post(approve_cfg['endpoint'], json=body)
                assert resp.status_code == approve_cfg['expected_status']
                resp_json = resp.json()
                logger.info(f"审核通过响应: {resp_json}")

                # 判断是否为可重试的错误（支付宝异常）
                if (resp_json.get('businessSuccess') is False and
                    error_keyword in resp_json.get('errorMessage', '')):
                    error_msg = resp_json.get('errorMessage')
                    allure.attach(
                        f"遇到可重试错误: {error_msg}",
                        name=f"第 {attempt} 次审核失败详情",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    logger.warning(f"第 {attempt} 次审核遇到异常: {error_msg}")
                    if attempt < max_retries:
                        logger.info(f"等待 {retry_interval} 秒后重新执行完整流程...")
                        allure.attach(
                            f"等待 {retry_interval} 秒后重试",
                            name="重试等待",
                            attachment_type=allure.attachment_type.TEXT
                        )
                        time.sleep(retry_interval)
                        continue
                    else:
                        # 已达最大重试次数，标记失败
                        allure.attach(
                            f"已达最大重试次数 {max_retries}，最终错误: {error_msg}",
                            name="最终失败原因",
                            attachment_type=allure.attachment_type.TEXT
                        )
                        pytest.fail(f"已重试 {max_retries} 次，仍遇到支付宝异常，流程终止。最后错误: {error_msg}")

                # 正常情况：执行断言
                for check in approve_cfg['validate']:
                    actual = resp_json.get(check['path'].split('.')[-1])
                    if check['operator'] == '==':
                        assert actual == check['value'], f"审核通过断言失败: {actual} != {check['value']}"
                logger.info("审核通过，完结申请处理完成")

            # 验证订单状态变更为完结
            with allure.step("6. 验证订单状态已变更为完结 (status='09')"):
                expected_status = config.get('final_order_status', '09')
                verify_sql = f"SELECT status FROM llxz_order.ct_user_orders WHERE order_id = '{order_id}'"
                new_status = db.fetch_one(verify_sql)['status']
                assert new_status == expected_status, f"订单状态应为 {expected_status}，实际为 {new_status}"
                logger.info(f"订单状态已更新为 {new_status}")

            # 成功完成，跳出重试循环
            allure.attach("流程执行成功", name="最终结果", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"第 {attempt} 次尝试成功，流程结束")
            break