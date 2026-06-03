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

@allure.feature("订单完结申请-商家端+运营端")
@allure.story("审核拒绝流程")
class TestCompleteApplyReject:

    @allure.title("完整流程：商家提交完结申请 → 运营审核拒绝（含自动重试）")
    def test_reject_flow(self, merchant_api_client, admin_api_client, db, global_vars):
        yaml_path = os.path.join(os.path.dirname(__file__),
                                 "../../../../data/merchant/scenario/order/complete_apply_reject.yaml")
        config = load_yaml(yaml_path)
        base_vars = global_vars.copy()

        # 重试配置（默认使用审核通过相同的错误关键词，也可以单独配置）
        retry_cfg = config.get('retry_config', {})
        max_retries = retry_cfg.get('max_attempts', 3)
        retry_interval = retry_cfg.get('interval_seconds', 2)
        error_keyword = retry_cfg.get('error_keyword', '支付宝状态推进异常')

        for attempt in range(1, max_retries + 1):
            logger.info(f"========== 第 {attempt} 次尝试执行审核拒绝流程 ==========")
            allure.attach(f"第 {attempt} 次尝试", name="重试次数", attachment_type=allure.attachment_type.TEXT)
            variables = base_vars.copy()

            # 商家端完整流程：查询订单 → 上传图片 → 提交申请
            order_id, voucher_url = BaseCompleteApplyFlow.execute_merchant_actions(
                config, merchant_api_client, db, variables
            )

            # 如果数据库中未找到可完结的订单，跳过整个测试用例
            if order_id is None:
                skip_msg = "未查询到可完结的订单，跳过此用例"
                allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                logger.warning(skip_msg)
                pytest.skip(skip_msg)

            apply_id = BaseCompleteApplyFlow.execute_admin_query(config, admin_api_client, order_id)

            # 运营审核拒绝
            with allure.step("5. 运营审核拒绝"):
                reject_cfg = config['admin']['reject']
                body = reject_cfg['body_template']
                body['orderId'] = order_id
                body['applyId'] = apply_id
                resp = admin_api_client.post(reject_cfg['endpoint'], json=body)
                assert resp.status_code == reject_cfg['expected_status']
                resp_json = resp.json()
                logger.info(f"审核拒绝响应: {resp_json}")

                # 判断是否需要重试（可选，通常拒绝不会触发支付宝异常，但保留机制）
                if (resp_json.get('businessSuccess') is False and
                    error_keyword in resp_json.get('errorMessage', '')):
                    error_msg = resp_json.get('errorMessage')
                    allure.attach(
                        f"遇到可重试错误: {error_msg}",
                        name=f"第 {attempt} 次审核失败详情",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    logger.warning(f"第 {attempt} 次审核拒绝遇到异常: {error_msg}")
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
                        allure.attach(
                            f"已达最大重试次数 {max_retries}，最终错误: {error_msg}",
                            name="最终失败原因",
                            attachment_type=allure.attachment_type.TEXT
                        )
                        pytest.fail(f"已重试 {max_retries} 次，仍遇到异常，流程终止。最后错误: {error_msg}")

                # 正常断言
                for check in reject_cfg['validate']:
                    actual = resp_json.get(check['path'].split('.')[-1])
                    if check['operator'] == '==':
                        assert actual == check['value'], f"审核拒绝断言失败: {actual} != {check['value']}"
                logger.info("审核拒绝成功")

            # 验证申请记录状态变更为拒绝
            with allure.step("6. 验证申请记录状态变更为拒绝 (status='06')"):
                expected_status = config.get('expected_apply_status', '06')
                verify_sql = f"SELECT status FROM llxz_order.ct_user_orders WHERE order_id = '{order_id}'"
                record = db.fetch_one(verify_sql)
                assert record is not None, "未查询到申请记录"
                assert record['status'] == expected_status, f"申请状态应为 {expected_status}，实际为 {record['status']}"
                logger.info("申请状态已更新为拒绝")

            # 成功完成，跳出重试循环
            allure.attach("流程执行成功", name="最终结果", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"第 {attempt} 次尝试成功，流程结束")
            break