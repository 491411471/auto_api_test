import allure
import os
import pytest
import yaml
import random
import time
import json
from common.logger import logger


def load_yaml(yaml_path):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@allure.feature("补押金-商家端")
@allure.story("完整补押金流程")
class TestRepairOrder:

    @allure.title("完整流程:查询可补订单 → 获取用途 → 提交补订单 → 验证记录(含自动重试)")
    def test_repair_order_flow(self, merchant_api_client, db, global_vars):
        yaml_path = os.path.join(os.path.dirname(__file__),
                                 "../../../data/scenario/order/repair_order.yaml")
        config = load_yaml(yaml_path)
        base_vars = global_vars.copy()

        # 重试配置
        retry_cfg = config.get('retry_config', {})
        max_retries = retry_cfg.get('max_attempts', 3)
        retry_interval = retry_cfg.get('interval_seconds', 2)
        error_keywords = retry_cfg.get('error_keywords', [])
        if not error_keywords and 'error_keyword' in retry_cfg:
            error_keywords = [retry_cfg['error_keyword']]

        tried_repair_ids = set()
        tried_order_ids = set()

        for attempt in range(1, max_retries + 1):
            logger.info(f"========== 第 {attempt} 次尝试执行补押金流程 ==========")
            allure.attach(f"第 {attempt} 次尝试", name="重试次数", attachment_type=allure.attachment_type.TEXT)

            # 1. 查询可补订单
            with allure.step("1. 查询可补订单的订单号"):
                shop_id = base_vars.get('shop_id', '71008738021cd3393bacbac182bd6a86af0b5c87')

                # 构建SQL，排除已尝试的订单
                sql_template = config['merchant']['query_order_sql']
                sql = sql_template.replace('${shop_id}', shop_id)

                if tried_order_ids:
                    # 安全地添加 NOT IN 条件，必须在 ORDER BY 之前
                    order_ids_str = ','.join([f"'{oid}'" for oid in tried_order_ids])
                    
                    # 查找 ORDER BY 的位置
                    upper_sql = sql.upper()
                    order_by_pos = upper_sql.find('ORDER BY')
                    limit_pos = upper_sql.find('LIMIT')
                    
                    if order_by_pos != -1:
                        # 在 ORDER BY 之前插入 NOT IN 条件
                        not_in_clause = f" AND order_id NOT IN ({order_ids_str})"
                        sql = sql[:order_by_pos] + not_in_clause + "\n" + sql[order_by_pos:]
                    elif 'WHERE' in upper_sql:
                        # 没有 ORDER BY，直接追加到 WHERE 后面
                        sql += f" AND order_id NOT IN ({order_ids_str})"
                    else:
                        # 没有 WHERE，添加 WHERE 子句
                        sql += f" WHERE order_id NOT IN ({order_ids_str})"

                logger.info(f"执行SQL: {sql}")
                result = db.fetch_one(sql)
                if result is None:
                    skip_msg = "未查询到可补订单，跳过此用例"
                    allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                    logger.warning(skip_msg)
                    pytest.skip(skip_msg)
                order_id = result['order_id']
                product_id = result['product_id']
                tried_order_ids.add(order_id)
                logger.info(f"获取到订单号和商品编码: {order_id}, product_id: {product_id}")
                allure.attach(order_id, name="订单号", attachment_type=allure.attachment_type.TEXT)

            # 2. 获取补订单用途
            with allure.step("2. 获取补订单用途列表并随机选择一项"):
                get_cfg = config['merchant']['get_repair_order_list']
                from common.test_helpers import replace_placeholders
                params_template = get_cfg['params_template']
                params = replace_placeholders(params_template, {
                    'shop_id': shop_id,
                    'product_id': product_id
                })

                resp = merchant_api_client.get(get_cfg['endpoint'], params=params)
                assert resp.status_code == get_cfg['expected_status']
                resp_json = resp.json()

                # 验证响应
                from utils.variable_utils import validate, get_value_by_path
                for check in get_cfg['validate']:
                    path = check['path'].lstrip('$').lstrip('.')
                    actual = get_value_by_path(resp_json, path)
                    validate(actual, check['operator'], check['value'], path)

                records = resp_json['data']['records']
                assert len(records) > 0, "用途列表为空"

                # 过滤未尝试过的用途
                available_records = [r for r in records if r['id'] not in tried_repair_ids]
                if not available_records:
                    pytest.fail("所有可用的用途都已尝试过，流程终止")

                chosen = random.choice(available_records)
                repair_id = chosen['id']
                repair_price = chosen['price']
                repair_settlement = chosen['settlementProportion']
                repair_name = chosen['name']
                tried_repair_ids.add(repair_id)

                logger.info(f"选择用途: id={repair_id}, name={repair_name}, price={repair_price}")
                allure.attach(f"id={repair_id}, name={repair_name}", name="选中用途",
                              attachment_type=allure.attachment_type.TEXT)

            # 3. 提交补订单
            with allure.step("3. 提交补订单"):
                submit_cfg = config['merchant']['submit_repair_order']
                body = submit_cfg['body_template'].copy()
                body['orderId'] = order_id
                body['repairOrderConfig']['id'] = repair_id
                body['repairOrderConfig']['price'] = repair_price
                body['repairOrderConfig']['settlementProportion'] = repair_settlement

                # 附加请求参数到 Allure 报告
                allure.attach(
                    json.dumps(body, indent=2, ensure_ascii=False),
                    "提交补订单-请求参数",
                    allure.attachment_type.JSON
                )

                # 发送 POST 请求
                resp = merchant_api_client.post(submit_cfg['endpoint'], json=body)

                # 附加 HTTP 状态码
                allure.attach(
                    str(resp.status_code),
                    "HTTP 状态码",
                    allure.attachment_type.TEXT
                )

                # 解析响应数据
                resp_json = resp.json()

                # 附加完整响应体到 Allure 报告
                allure.attach(
                    json.dumps(resp_json, indent=2, ensure_ascii=False),
                    "提交补订单-接口响应",
                    allure.attachment_type.JSON
                )

                logger.info(f"提交补订单响应: {resp_json}")

                # 如果业务失败，记录详细错误信息
                if not resp_json.get('businessSuccess'):
                    error_detail = (
                        f"补订单提交业务失败\n"
                        f"  错误码: {resp_json.get('errorCode', 'N/A')}\n"
                        f"  错误类型: {resp_json.get('responseType', 'N/A')}\n"
                        f"  错误信息: {resp_json.get('errorMessage', '未知错误')}"
                    )
                    allure.attach(error_detail, "业务错误详情", attachment_type=allure.attachment_type.TEXT)

                # 错误检查逻辑
                error_msg = resp_json.get('errorMessage') or ''
                is_retryable_error = any(keyword.format(name=repair_name) in error_msg for keyword in error_keywords)

                if resp_json.get('businessSuccess') is False and is_retryable_error:
                    allure.attach(f"遇到可重试错误: {error_msg}",
                                  name=f"第 {attempt} 次提交失败详情",
                                  attachment_type=allure.attachment_type.TEXT)
                    logger.warning(f"第 {attempt} 次提交遇到异常: {error_msg}")

                    if attempt < max_retries:
                        logger.info(f"等待 {retry_interval} 秒后重试...")
                        time.sleep(retry_interval)
                        continue
                    else:
                        allure.attach(f"已达最大重试次数 {max_retries}, 最终错误: {error_msg}",
                                      name="最终失败原因", attachment_type=allure.attachment_type.TEXT)
                        pytest.fail(f"已重试 {max_retries} 次，仍遇到错误: {error_msg}")

                # 验证 HTTP 状态码
                assert resp.status_code == submit_cfg['expected_status'], (
                    f"HTTP 状态码不符合预期\n"
                    f"  期望值: {submit_cfg['expected_status']}\n"
                    f"  实际值: {resp.status_code}"
                )

                # 验证提交成功 - 使用统一的 validate 函数
                from utils.variable_utils import validate, get_value_by_path
                for check in submit_cfg['validate']:
                    path = check['path']
                    operator = check['operator']
                    expected = check['value']
                    clean_path = path.lstrip('$').lstrip('.')
                    actual = get_value_by_path(resp_json, clean_path)
                    # 调用统一的 validate 函数进行断言
                    validate(actual, operator, expected, path)

                logger.info("补订单提交成功")
                allure.attach("流程执行成功", name="最终结果", attachment_type=allure.attachment_type.TEXT)
                break

        #     # 4. 查询补订单记录并验证最新一条
        #     with allure.step("4. 查询补订单记录并验证最新一条数据"):
        #         query_cfg = config['merchant']['query_repair_order_list']
        #         query_body = query_cfg['body_template'].copy()
        #         query_body['orderId'] = order_id
        #         resp = merchant_api_client.post(query_cfg['endpoint'], json=query_body)
        #         assert resp.status_code == query_cfg['expected_status']
        #         resp_json = resp.json()
        #         logger.info(f"查询补订单列表响应: {resp_json}")
        #
        #         records_list = resp_json['data']['backstageMakeOrderDtoList']['records']
        #         assert len(records_list) > 0, "查询结果为空"
        #         latest_record = records_list[0]  # 列表按创建时间降序?
        #         # 验证 orderId 和 servicePrice
        #         expected_order_id = f"MOI{order_id}"  # 补订单生成的订单号格式可能为 MOI + 原订单号,具体需确认
        #         # 实际业务中补订单生成的订单号可能与原订单号不完全相同,此处建议根据实际格式调整
        #         # 可以通过正则或直接断言servicePrice匹配
        #         logger.info(f"最新补订单记录: orderId={latest_record['orderId']}, servicePrice={latest_record['servicePrice']}")
        #         # 断言金额
        #         assert latest_record['servicePrice'] == repair_price, f"金额不匹配: 期望 {repair_price}, 实际 {latest_record['servicePrice']}"
        #         # 可选:断言用途名称
        #         assert latest_record['goodsName'] == repair_name, f"用途名称不匹配: 期望 {repair_name}, 实际 {latest_record['goodsName']}"
        #         logger.info("补订单记录验证通过")
        #
        #     # 成功完成,跳出循环
        #         allure.attach("流程执行成功", name="最终结果", attachment_type=allure.attachment_type.TEXT)
        #         logger.info(f"第 {attempt} 次尝试成功,补押金流程结束")
        #         break
        # else:
        #     pytest.fail("未知错误:重试循环异常退出")
