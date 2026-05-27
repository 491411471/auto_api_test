import allure
import os
from common.logger import logger
import json

class BaseCompleteApplyFlow:
    """订单完结申请流程的公共操作"""

    @staticmethod
    def execute_merchant_actions(config, merchant_api_client, db, variables):
        """
        商家端公共操作：查询订单、上传图片、提交申请
        返回 (order_id, voucher_url)
        """
        with allure.step("1. 从数据库查询可完结的订单号"):
            sql = config['merchant']['query_order_sql'].replace('${shop_id}', variables['shop_id'])
            result = db.fetch_one(sql)
            if result is None:
                logger.warning("未查询到可完结的订单，返回空结果")
                allure.attach("数据库中未找到可完结的订单", name="查询结果", attachment_type=allure.attachment_type.TEXT)
                return None, None
            order_id = result['order_id']
            logger.info(f"获取订单号: {order_id}")
            allure.attach(order_id, "订单号", attachment_type=allure.attachment_type.TEXT)

        with allure.step("2. 上传凭证图片"):
            upload_cfg = config['merchant']['upload_image']
            image_path = upload_cfg['test_image_path']
            assert os.path.exists(image_path), f"测试图片不存在: {image_path}"
            with open(image_path, 'rb') as f:
                files = {upload_cfg['file_field']: f}
                resp = merchant_api_client.post(upload_cfg['endpoint'], files=files)
            assert resp.status_code == 200
            resp_json = resp.json()
            # 断言图片上传成功
            assert resp_json.get('businessSuccess') is True, "图片上传失败"
            assert resp_json.get('data'), "未返回图片URL"
            voucher_url = resp_json['data']
            logger.info(f"图片上传成功: {voucher_url}")
            allure.attach(voucher_url, "图片URL", attachment_type=allure.attachment_type.TEXT)

        with allure.step("3. 提交订单完结申请"):
            submit_cfg = config['merchant']['submit_apply']
            body = submit_cfg['body_template']
            body['orderId'] = order_id
            body['voucher'][0] = voucher_url
            
            # 附加请求参数到 Allure 报告
            allure.attach(
                json.dumps(body, indent=2, ensure_ascii=False),
                "提交申请-请求参数",
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
                "提交申请-接口响应",
                allure.attachment_type.JSON
            )
            
            # 如果业务失败，记录详细错误信息
            if not resp_json.get('businessSuccess'):
                error_detail = (
                    f"订单完结申请业务失败\n"
                    f"  错误码: {resp_json.get('errorCode', 'N/A')}\n"
                    f"  错误类型: {resp_json.get('responseType', 'N/A')}\n"
                    f"  错误信息: {resp_json.get('errorMessage', '未知错误')}"
                )
                allure.attach(error_detail, "业务错误详情", attachment_type=allure.attachment_type.TEXT)
            
            # 验证 HTTP 状态码
            assert resp.status_code == submit_cfg['expected_status'], (
                f"HTTP 状态码不符合预期\n"
                f"  期望值: {submit_cfg['expected_status']}\n"
                f"  实际值: {resp.status_code}"
            )
            
            # 执行配置中的断言
            for check in submit_cfg['validate']:
                actual = resp_json.get(check['path'].split('.')[-1])
                if check['operator'] == '==':
                    assert actual == check['value'], (
                        f"提交申请断言失败\n"
                        f"  字段: {check['path']}\n"
                        f"  期望值: {check['value']}\n"
                        f"  实际值: {actual}\n"
                        f"  错误信息: {resp_json.get('errorMessage', 'N/A')}"
                    )
            
            logger.info("完结申请提交成功")

        return order_id, voucher_url

    @staticmethod
    def execute_admin_query(config, admin_api_client, order_id):
        """
        运营端公共操作：查询申请记录，返回 apply_id
        """
        with allure.step("4. 运营端查询完结申请记录"):
            query_cfg = config['admin']['query_apply']
            body = query_cfg['body_template'].copy()  # 避免修改原始配置
            body['orderId'] = order_id
            
            # 记录请求信息
            logger.info(f"查询申请记录 - 订单号: {order_id}")
            logger.info(f"请求参数: {body}")
            allure.attach(str(body), name="请求参数", attachment_type=allure.attachment_type.JSON)
            
            resp = admin_api_client.post(query_cfg['endpoint'], json=body)
            assert resp.status_code == query_cfg['expected_status'], \
                f"HTTP状态码错误: 期望{query_cfg['expected_status']}, 实际{resp.status_code}"
            
            resp_json = resp.json()
            logger.info(f"查询响应: {resp_json}")
            allure.attach(str(resp_json), name="接口响应", attachment_type=allure.attachment_type.JSON)
            
            # 检查业务是否成功
            if resp_json.get('businessSuccess') is False:
                error_msg = resp_json.get('errorMessage', '未知错误')
                raise AssertionError(f"查询申请记录失败: {error_msg}")
            
            # 安全地获取 data 和 records
            data = resp_json.get('data')
            if data is None:
                raise AssertionError(f"响应中 data 字段为空: {resp_json}")
            
            records = data.get('records')
            if records is None or len(records) == 0:
                raise AssertionError(
                    f"未查询到申请记录\n"
                    f"订单号: {order_id}\n"
                    f"响应数据: {resp_json}"
                )
            
            # 获取第一条记录
            first_record = records[0]
            
            # 执行配置中的断言
            if 'validate' in query_cfg:
                for check in query_cfg['validate']:
                    if check['path'] == '$.data.records[0].orderId':
                        actual_order_id = first_record.get('orderId')
                        expected_order_id = order_id
                        
                        # 记录断言信息
                        assertion_detail = (
                            f"断言: orderId 匹配\n"
                            f"期望值: {expected_order_id}\n"
                            f"实际值: {actual_order_id}\n"
                            f"类型: {type(actual_order_id)}"
                        )
                        logger.info(assertion_detail)
                        allure.attach(assertion_detail, name="断言详情", attachment_type=allure.attachment_type.TEXT)
                        
                        # 执行断言
                        assert actual_order_id == expected_order_id, (
                            f"订单号不匹配\n"
                            f"期望: {expected_order_id}\n"
                            f"实际: {actual_order_id}"
                        )
            
            # 获取 apply_id
            apply_id = first_record.get('id')
            if apply_id is None:
                raise AssertionError(
                    f"申请记录中缺少 id 字段\n"
                    f"记录内容: {first_record}"
                )
            
            logger.info(f"获取到申请ID: {apply_id}")
            allure.attach(str(apply_id), name="applyId", attachment_type=allure.attachment_type.TEXT)
            return apply_id