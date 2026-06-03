import allure
import os
import json
import yaml
import random
import pytest
from common.logger import logger
from testcases.conftest import admin_api_client
from utils.variable_utils import validate, get_value_by_path


def load_yaml(yaml_path):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@allure.feature("订单状态流转-商家端+运营端")
@allure.story("审核 → 发货 → 确认收货 → 租用中完整流程")
class TestOrderFlow:
    @allure.title("完整流程：查询待审核订单 → 审核通过 → 获取归还地址 → 发货 → 生成PDF → 运营端查询验证 → 运营端确认收货 -> 验证租用中状态")
    def test_order_flow(self, merchant_api_client, db, global_vars, admin_api_client):
        yaml_path = os.path.join(os.path.dirname(__file__), "../../../../data/merchant/scenario/order/order_flow.yaml")
        config = load_yaml(yaml_path)
        base_vars = global_vars.copy()
        shop_id = base_vars.get('shop_id', '71008738021cd3393bacbac182bd6a86af0b5c87')

        # ---------- 步骤1：查询待审核订单 ----------
        with allure.step("1. 查询已签约、待审核的订单号"):
            try:
                # 获取 SQL 模板并替换占位符
                sql_template = config['merchant']['query_order_sql']
                sql = sql_template.replace('${shop_id}', shop_id)
                
                # 附加 SQL 语句到 Allure 报告
                allure.attach(sql, "查询订单-SQL语句", allure.attachment_type.TEXT)
                logger.info(f"执行SQL: {sql}")
                # 执行数据库查询
                result = db.fetch_one(sql)
                
                # 如果未查询到符合条件的订单，直接跳过测试
                if result is None:
                    skip_msg = (
                        f"未查询到符合条件的待审核订单，跳过此用例\n"
                        f"  查询条件: shop_id={shop_id}, status='13', user_is_signed=2, withhold_type IS NOT NULL\n"
                        f"  可能原因: 当前环境下无符合流转条件的测试订单"
                    )
                    allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                    logger.warning(skip_msg)
                    pytest.skip(skip_msg)
                    
            except Exception as e:
                skip_msg = f"数据库查询失败，跳过此用例 | 错误: {e}"
                allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                logger.error(skip_msg)
                pytest.skip(skip_msg)
            
            # 提取订单号
            order_id = result.get('order_id')
            assert order_id is not None, f"查询结果中缺少 order_id 字段: {result}"
            
            logger.info(f"获取到订单号: {order_id}")
            
            # 附加订单号到 Allure 报告
            allure.attach(
                order_id,
                "查询订单-订单号",
                allure.attachment_type.TEXT
            )

        # ---------- 步骤2：审核通过 ----------
        with allure.step("2. 调用审核通过接口"):
            audit_cfg = config['merchant']['telephone_audit']
            body = audit_cfg['body_template'].copy()
            body['orderId'] = order_id
            
            # 附加请求参数到 Allure 报告
            allure.attach(
                json.dumps(body, indent=2, ensure_ascii=False),
                "审核通过-请求参数",
                allure.attachment_type.JSON
            )
            logger.info(f"审核通过请求参数: {json.dumps(body, ensure_ascii=False)}")
            
            # 发送 POST 请求
            resp = merchant_api_client.post(audit_cfg['endpoint'], json=body)
            
            # 附加 HTTP 状态码
            allure.attach(
                str(resp.status_code),
                "HTTP 状态码",
                allure.attachment_type.TEXT
            )
            
            # 验证 HTTP 状态码
            assert resp.status_code == audit_cfg['expected_status'], (
                f"HTTP 状态码不符合预期\n"
                f"  期望值: {audit_cfg['expected_status']}\n"
                f"  实际值: {resp.status_code}"
            )
            
            # 解析响应数据
            resp_json = resp.json()
            
            # 附加完整响应体到 Allure 报告
            allure.attach(
                json.dumps(resp_json, indent=2, ensure_ascii=False),
                "审核通过-接口响应",
                allure.attachment_type.JSON
            )
            logger.info(f"审核通过响应: {json.dumps(resp_json, ensure_ascii=False)}")
            
            # 如果业务失败，记录详细错误信息
            if not resp_json.get('businessSuccess'):
                error_detail = (
                    f"审核通过业务失败\n"
                    f"  错误码: {resp_json.get('errorCode', 'N/A')}\n"
                    f"  错误类型: {resp_json.get('responseType', 'N/A')}\n"
                    f"  错误信息: {resp_json.get('errorMessage', '未知错误')}"
                )
                allure.attach(error_detail, "业务错误详情", attachment_type=allure.attachment_type.TEXT)
            
            # 执行配置中的断言
            for check in audit_cfg['validate']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                validate(actual, check['operator'], check['value'], path)
            
            logger.info("审核通过接口调用成功")

        # ---------- 步骤3：获取归还地址列表，随机选择一个地址 ----------
        with allure.step("3. 获取归还地址列表，并随机选择一个地址ID"):
            addr_cfg = config['merchant']['get_back_address_list']
            params = addr_cfg['params_template'].copy()
            params['orderId'] = order_id
            resp = merchant_api_client.get(addr_cfg['endpoint'], params=params)
            assert resp.status_code == addr_cfg['expected_status']
            resp_json = resp.json()
            for check in addr_cfg['validate']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)

                validate(actual, check['operator'], check['value'], path)

            address_list = resp_json.get('data', [])
            assert len(address_list) > 0, "归还地址列表为空"
            chosen_address = random.choice(address_list)
            return_address_id = chosen_address['id']
            logger.info(f"选择的地址ID: {return_address_id}, 地址详情: {chosen_address.get('provinceStr')} {chosen_address.get('cityStr')} {chosen_address.get('areaStr')}")
            allure.attach(f"地址ID: {return_address_id}", name="选中地址", attachment_type=allure.attachment_type.TEXT)

        # ---------- 步骤4：发货 ----------
        with allure.step("4. 调用发货接口"):
            # ==================== 新增：账期状态检查与更新 ====================
            with allure.step("4.0 检查订单账期状态, 如果状态不为2，不允许发货"):
                try:
                    # 查询当前账期状态（取最小id的那条记录）
                    check_sql = f"""
                        SELECT status 
                        FROM llxz_order.ct_order_by_stages 
                        WHERE order_id = '{order_id}'
                        AND delete_time IS NULL
                        AND shop_id = '{shop_id}'
                        ORDER BY id 
                        LIMIT 1
                    """
                    logger.info(f"查询账期状态SQL: {check_sql}")
                    allure.attach(check_sql, name="查询SQL", attachment_type=allure.attachment_type.TEXT)
                    check_result = db.fetch_one(check_sql)
                    
                    # 如果未查询到账期数据，跳过测试
                    if check_result is None:
                        skip_msg = (
                            f"未查询到订单 {order_id} 的账期数据，跳过此用例\n"
                            f"  表: ct_order_by_stages\n"
                            f"  可能原因: 订单尚未生成账期或数据异常"
                        )
                        allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                        logger.warning(skip_msg)
                        pytest.skip(skip_msg)
                    
                    current_status = check_result.get('status')
                    allure.attach(f"当前状态: {current_status}", name="账期状态",
                                  attachment_type=allure.attachment_type.TEXT)
                    logger.info(f"当前账期状态: {current_status}")
                except Exception as e:
                    skip_msg = f"查询账期状态失败，跳过此用例 | 错误: {e}"
                    allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                    logger.error(skip_msg)
                    pytest.skip(skip_msg)

            # 若状态不为2，则更新为2
            if current_status != 2:
                with allure.step("4.1 更新订单账期状态为2（最小id记录）"):
                    try:
                        update_sql = f"""
                            UPDATE llxz_order.ct_order_by_stages AS t
                            JOIN (
                                SELECT id 
                                FROM llxz_order.ct_order_by_stages 
                                WHERE order_id = '{order_id}'
                                AND delete_time IS NULL
                                AND shop_id = '{shop_id}'
                                ORDER BY id 
                                LIMIT 1
                            ) AS s ON t.id = s.id
                            SET t.status = 2
                        """
                        logger.info(f"执行SQL: {update_sql}")
                        allure.attach(update_sql, name="更新SQL", attachment_type=allure.attachment_type.TEXT)
                        affected_rows = db.execute_update(update_sql)  # 执行更新
                        
                        if affected_rows == 0:
                            logger.warning(f"账期状态更新未影响任何行，订单号: {order_id}")
                        
                        allure.attach(f"更新成功，影响行数: {affected_rows}", name="执行结果", attachment_type=allure.attachment_type.TEXT)
                        logger.info(f"账期状态更新成功，影响行数: {affected_rows}")
                    except Exception as e:
                        skip_msg = f"更新账期状态失败，跳过此用例 | 错误: {e}"
                        allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                        logger.error(skip_msg)
                        pytest.skip(skip_msg)
            else:
                with allure.step("4.1 检查是否需要更新"):
                    allure.attach("账期状态已经是2，无需更新", name="跳过更新", attachment_type=allure.attachment_type.TEXT)
                    logger.info("账期状态已经是2，无需更新")

            delivery_cfg = config['merchant']['order_delivery']
            body = delivery_cfg['body_template'].copy()
            body['orderId'] = order_id
            body['returnAddressIdList'] = [return_address_id]
            resp = merchant_api_client.post(delivery_cfg['endpoint'], json=body)
            assert resp.status_code == delivery_cfg['expected_status']
            resp_json = resp.json()
            logger.info(f"{resp_json}")
            allure.attach(json.dumps(resp_json, indent=2, ensure_ascii=False), name="发货响应", attachment_type=allure.attachment_type.JSON)
            for check in delivery_cfg['validate']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                validate(actual, check['operator'], check['value'], path)
            logger.info("发货成功")


        # ---------- 步骤5：创建PDF ----------
        with allure.step("5. 生成订单PDF"):
            pdf_cfg = config['merchant']['create_pdf']
            params = pdf_cfg['params_template'].copy()
            params['orderId'] = order_id
            resp = merchant_api_client.get(pdf_cfg['endpoint'], params=params)
            assert resp.status_code == pdf_cfg['expected_status']
            resp_json = resp.json()
            for check in pdf_cfg['validate']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                validate(actual, check['operator'], check['value'], path)
            pdf_url = resp_json.get('data')
            logger.info(f"PDF生成成功: {pdf_url}")
            allure.attach(pdf_url, name="PDF链接", attachment_type=allure.attachment_type.TEXT)

        # ---------- 步骤6：运营端查询订单，验证订单状态----------
        with allure.step("6. 运营端查询订单，验证订单状态为已发货/已确认等"):
            ope_query_cfg = config['merchant']['ope_query_order']
            body = ope_query_cfg['body_template'].copy()
            body['orderId'] = order_id
            resp = admin_api_client.post(ope_query_cfg['endpoint'], json=body)
            assert resp.status_code == ope_query_cfg['expected_status']
            resp_json = resp.json()
            for check in ope_query_cfg['validate']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                validate(actual, check['operator'], check['value'], path)

            records = resp_json.get('data', {}).get('records', [])
            assert len(records) > 0, "运营端未查询到订单"
            order_info = records[0]
            # 根据实际业务断言所需状态，例如 status='05'（已发货）、examineStatus='03'（审核通过）
            actual_status = order_info.get('status')
            expected_status = "05"   # 根据示例响应，发货后 status 应为 "05"
            assert actual_status == expected_status, f"订单状态不符合预期: 期望 {expected_status}, 实际 {actual_status}"
            logger.info(f"运营端订单状态验证通过: status={actual_status}")
            allure.attach(f"订单状态: {actual_status}", name="发货后状态", attachment_type=allure.attachment_type.TEXT)

        # ---------- 步骤7：运营端确认收货 ----------
        with allure.step("7. 运营端确认收货"):
            confirm_cfg = config['merchant']['ope_confirm_receipt']
            params = confirm_cfg['params_template'].copy()
            params['orderId'] = order_id
            resp = merchant_api_client.get(confirm_cfg['endpoint'], params=params)
            assert resp.status_code == confirm_cfg['expected_status']
            resp_json = resp.json()
            for check in confirm_cfg['validate']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                validate(actual, check['operator'], check['value'], path)
            logger.info("确认收货成功")

        # ---------- 步骤8：验证订单状态为租用中 ----------
        with allure.step("8. 验证确认收货后订单状态是否为租用中"):
            verify_cfg = config['merchant']['verify_renting_status']
            body = verify_cfg['body_template'].copy()
            body['orderId'] = order_id
            resp = admin_api_client.post(verify_cfg['endpoint'], json=body)
            assert resp.status_code == verify_cfg['expected_status']
            resp_json = resp.json()
            # 执行YAML中定义的断言（包括状态码比较）
            for check in verify_cfg['validate']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                # 如果 value 中包含 ${expected_renting_status}，需提前替换
                expected = check['value']
                if isinstance(expected, str) and expected.startswith('${'):
                    # 支持从全局变量读取实际期望状态，例如 env 配置
                    expected = global_vars.get(expected.strip('${}'), expected)
                validate(actual, check['operator'], expected, path)

            actual_status = get_value_by_path(resp_json, 'data.records[0].status')
            logger.info(f"订单状态验证通过: status={actual_status} (租用中)")
            allure.attach(f"订单状态: {actual_status}", name="租用中状态", attachment_type=allure.attachment_type.TEXT)
        logger.info("订单状态流转测试全部通过")