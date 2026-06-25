# -*- coding: utf-8 -*-
"""
闲鱼商品操作测试用例
包含：上架、下架、修改闲鱼商品
"""
import json
import copy
import allure
import pytest
from pathlib import Path
from utils.data_loader import get_test_data
from common.test_helpers import replace_placeholders, validate
from common.logger import logger


# YAML 数据文件路径
_XIANYU_OPS_YAML = "data/merchant/scenario/product/xianyu_product_operations.yaml"


@allure.epic("商家端")
@allure.feature("闲鱼商品管理")
@allure.story("闲鱼商品操作")
class TestXianYuProductOperations:
    """闲鱼商品操作测试类：上架、下架、修改"""
    
    # 类属性：在所有测试方法间共享
    test_vars = {}
    
    @staticmethod
    def log_response(response, step_name="", request_data=None):
        """
        记录API响应信息到日志和Allure报告
        
        Args:
            response: requests.Response对象
            step_name: 步骤名称（用于日志标识）
            request_data: 请求数据（可选，用于Allure报告）
        
        Returns:
            dict: 解析后的JSON响应
        """
        result = response.json()
        
        # 1. 记录到日志
        log_prefix = f"[{step_name}]" if step_name else "[响应]"
        logger.info(f"{log_prefix} HTTP状态码: {response.status_code}")
        logger.info(f"{log_prefix} RPC结果: {result.get('rpcResult', 'N/A')}")
        logger.info(f"{log_prefix} 业务成功: {result.get('businessSuccess', 'N/A')}")
        
        # 记录完整响应（前500字符）
        response_str = json.dumps(result, indent=2, ensure_ascii=False)
        if len(response_str) > 500:
            logger.info(f"{log_prefix} 响应内容: {response_str[:500]}...")
        else:
            logger.info(f"{log_prefix} 响应内容: {response_str}")
        
        # 如果是错误响应，记录详细错误信息
        if not result.get('businessSuccess', False):
            logger.error(f"{log_prefix} ❌ 业务失败！")
            logger.error(f"{log_prefix} 错误码: {result.get('errorCode', 'N/A')}")
            logger.error(f"{log_prefix} 错误消息: {result.get('errorMessage', 'N/A')}")
        
        # 2. 附加到Allure报告
        # 附加HTTP状态码
        allure.attach(
            f"HTTP状态码: {response.status_code}",
            f"{step_name} - HTTP状态码" if step_name else "HTTP状态码",
            attachment_type=allure.attachment_type.TEXT
        )
        
        # 附加完整响应（JSON格式，超过5000字符截断）
        response_json = json.dumps(result, indent=2, ensure_ascii=False)
        if len(response_json) > 5000:
            truncated_response = result.copy()
            # 如果data字段过大，截断data
            if 'data' in truncated_response and isinstance(truncated_response['data'], (dict, list)):
                truncated_response['data'] = str(truncated_response['data'])[:1000] + "... (已截断)"
            response_json = json.dumps(truncated_response, indent=2, ensure_ascii=False)
            attachment_name = f"{step_name} - 接口响应 (已截断)" if step_name else "接口响应 (已截断)"
        else:
            attachment_name = f"{step_name} - 接口响应" if step_name else "接口响应"
        
        allure.attach(
            response_json,
            attachment_name,
            attachment_type=allure.attachment_type.JSON
        )
        
        # 如果有请求数据，附加请求参数
        if request_data:
            request_json = json.dumps(request_data, indent=2, ensure_ascii=False)
            allure.attach(
                request_json,
                f"{step_name} - 请求参数" if step_name else "请求参数",
                attachment_type=allure.attachment_type.JSON
            )
        
        # 如果是错误响应，附加错误详情
        if not result.get('businessSuccess', False):
            error_detail = (
                f"业务失败详情:\n"
                f"  HTTP状态码: {response.status_code}\n"
                f"  错误码: {result.get('errorCode', 'N/A')}\n"
                f"  错误类型: {result.get('responseType', 'N/A')}\n"
                f"  错误消息: {result.get('errorMessage', 'N/A')}\n"
                f"  RPC结果: {result.get('rpcResult', 'N/A')}\n"
                f"  businessSuccess: {result.get('businessSuccess', 'N/A')}\n"
                f"  data: {result.get('data', 'N/A')}"
            )
            allure.attach(
                error_detail,
                f"{step_name} - 业务错误详情" if step_name else "业务错误详情",
                attachment_type=allure.attachment_type.TEXT
            )
        
        return result

    # ==================== 测试用例1：上架闲鱼商品 ====================

    @pytest.mark.order(1)
    @allure.title("上架闲鱼商品-查询已下架商品")
    def test_step1_query_offline_product(self, merchant_api_client, db):
        """步骤1：查询已下架的闲鱼商品"""
        with allure.step("查询已下架的闲鱼商品列表"):
            # 加载测试数据
            case = get_test_data(_XIANYU_OPS_YAML, "xianyu_query_offline_product_test")[0]

            # 发送请求
            response = merchant_api_client.post(case['endpoint'], json=case['json'])

            # 验证HTTP状态码
            assert response.status_code == case.get('expected_status', 200), \
                f"HTTP状态码不符合预期！期望: {case.get('expected_status', 200)}, 实际: {response.status_code}"

            # 记录响应到日志和Allure报告
            result = self.log_response(response, "查询已下架商品")

            # 验证业务成功
            assert result.get('businessSuccess') is True, \
                f"查询业务失败：{result.get('errorMessage', '未知错误')}"

            # 从records中获取最后一个商品的productId
            records = result.get('data', {}).get('records', [])
            assert len(records) > 0, "未查询到已下架的闲鱼商品"

            # 取最后一个商品（索引为9或最后一个）
            last_index = min(9, len(records) - 1)
            product_id = records[last_index].get('productId')
            product_db_id = records[last_index].get('id')

            assert product_id is not None, "商品productId为空"
            assert product_db_id is not None, "商品id为空"

            # 保存到self.test_vars供后续步骤使用
            self.test_vars['product_id'] = product_id
            self.test_vars['product_db_id'] = product_db_id

            allure.attach(
                f"productId: {product_id}\n数据库id: {product_db_id}",
                "选中的商品信息",
                attachment_type=allure.attachment_type.TEXT
            )

    @pytest.mark.order(2)
    @allure.title("上架闲鱼商品-执行上架操作")
    def test_step2_online_product(self, merchant_api_client, db):
        """步骤2：上架闲鱼商品"""
        with allure.step("执行上架操作"):
            # 加载测试数据
            case = get_test_data(_XIANYU_OPS_YAML, "xianyu_online_product_test")[0]

            # 替换占位符
            case_copy = copy.deepcopy(case)
            if 'json' in case_copy:
                case_copy['json'] = replace_placeholders(case_copy['json'], self.test_vars)

            allure.attach(
                json.dumps(case_copy['json'], indent=2, ensure_ascii=False),
                "上架请求体",
                attachment_type=allure.attachment_type.JSON
            )

            # 发送请求
            response = merchant_api_client.post(case_copy['endpoint'], json=case_copy['json'])

            # 验证HTTP状态码
            assert response.status_code == case_copy.get('expected_status', 200), \
                f"HTTP状态码不符合预期！期望: {case_copy.get('expected_status', 200)}, 实际: {response.status_code}"

            # 记录响应到日志和Allure报告
            result = self.log_response(response, "上架商品")

            # 执行动态断言
            for validate_item in case_copy.get('validate_data', []):
                path = validate_item['path']
                operator = validate_item['operator']
                expected_value = validate_item.get('value')

                # 提取实际值
                if path.startswith("$."):
                    key = path[2:]
                    actual_value = result.get(key)
                else:
                    actual_value = result.get(path)

                validate(actual_value, operator, expected_value, path)

            allure.attach("闲鱼商品上架成功", "上架阶段结果", attachment_type=allure.attachment_type.TEXT)

    @pytest.mark.order(3)
    @allure.title("上架闲鱼商品-运营端审核通过")
    def test_step3_audit_online_product(self, admin_api_client, db):
        """步骤3：运营端审核上架商品"""
        with allure.step("运营端审核上架商品（审核通过）"):
            # 加载测试数据
            case = get_test_data(_XIANYU_OPS_YAML, "xianyu_audit_online_product_test")[0]

            # 替换占位符
            case_copy = copy.deepcopy(case)
            if 'json' in case_copy:
                case_copy['json'] = replace_placeholders(case_copy['json'], self.test_vars)

            allure.attach(
                json.dumps(case_copy['json'], indent=2, ensure_ascii=False),
                "审核请求体",
                attachment_type=allure.attachment_type.JSON
            )

            # 发送请求（使用运营端客户端）
            response = admin_api_client.post(case_copy['endpoint'], json=case_copy['json'])

            # 验证HTTP状态码
            assert response.status_code == case_copy.get('expected_status', 200), \
                f"HTTP状态码不符合预期！期望: {case_copy.get('expected_status', 200)}, 实际: {response.status_code}"

            # 记录响应到日志和Allure报告
            result = self.log_response(response, "审核上架商品")

            # 执行动态断言
            for validate_item in case_copy.get('validate_data', []):
                path = validate_item['path']
                operator = validate_item['operator']
                expected_value = validate_item.get('value')

                # 提取实际值
                if path.startswith("$."):
                    key = path[2:]
                    actual_value = result.get(key)
                else:
                    actual_value = result.get(path)

                validate(actual_value, operator, expected_value, path)

            # 验证数据库中的审核状态
            product_db_id = self.test_vars.get('product_db_id')
            if product_db_id:
                db_result = db.fetch_one(
                    "SELECT audit_state FROM llxz_product.ct_product WHERE id = %s",
                    (product_db_id,)
                )
                assert db_result is not None, f"未找到商品记录，id={product_db_id}"
                actual_audit_state = db_result.get('audit_state')
                assert actual_audit_state == 2, \
                    f"商品审核状态不符合预期！期望值: 2 实际值: {actual_audit_state} 商品ID: {product_db_id}"

                allure.attach(
                    f"商品ID: {product_db_id}\n审核状态: {actual_audit_state}",
                    "数据库审核状态",
                    attachment_type=allure.attachment_type.TEXT
                )

            allure.attach("闲鱼商品上架审核通过", "审核阶段结果", attachment_type=allure.attachment_type.TEXT)

    # ==================== 测试用例2：下架闲鱼商品 ====================

    @pytest.mark.order(4)
    @allure.title("下架闲鱼商品-查询已上架商品")
    def test_step4_query_online_product(self, merchant_api_client, db):
        """步骤4：查询已上架的闲鱼商品"""
        with allure.step("查询已上架的闲鱼商品列表"):
            # 加载测试数据
            case = get_test_data(_XIANYU_OPS_YAML, "xianyu_query_online_product_test")[0]

            # 发送请求
            response = merchant_api_client.post(case['endpoint'], json=case['json'])

            # 验证HTTP状态码
            assert response.status_code == case.get('expected_status', 200), \
                f"HTTP状态码不符合预期！期望: {case.get('expected_status', 200)}, 实际: {response.status_code}"

            # 记录响应到日志和Allure报告
            result = self.log_response(response, "查询已上架商品")

            # 验证业务成功
            assert result.get('businessSuccess') is True, \
                f"查询业务失败：{result.get('errorMessage', '未知错误')}"

            # 从records中获取最后一个商品的productId
            records = result.get('data', {}).get('records', [])
            assert len(records) > 0, "未查询到已上架的闲鱼商品"

            # 取最后一个商品（索引为9或最后一个）
            last_index = min(9, len(records) - 1)
            product_id = records[last_index].get('productId')
            product_db_id = records[last_index].get('id')

            assert product_id is not None, "商品productId为空"
            assert product_db_id is not None, "商品id为空"

            # 保存到self.test_vars供后续步骤使用
            self.test_vars['product_id'] = product_id
            self.test_vars['product_db_id'] = product_db_id

            allure.attach(
                f"productId: {product_id}\n数据库id: {product_db_id}",
                "选中的商品信息",
                attachment_type=allure.attachment_type.TEXT
            )

    @pytest.mark.order(5)
    @allure.title("下架闲鱼商品-执行下架操作")
    def test_step5_offline_product(self, merchant_api_client, db):
        """步骤5：下架闲鱼商品"""
        with allure.step("执行下架操作"):
            # 加载测试数据
            case = get_test_data(_XIANYU_OPS_YAML, "xianyu_offline_product_test")[0]

            # 替换占位符
            case_copy = copy.deepcopy(case)
            if 'json' in case_copy:
                case_copy['json'] = replace_placeholders(case_copy['json'], self.test_vars)

            allure.attach(
                json.dumps(case_copy['json'], indent=2, ensure_ascii=False),
                "下架请求体",
                attachment_type=allure.attachment_type.JSON
            )

            # 发送请求
            response = merchant_api_client.post(case_copy['endpoint'], json=case_copy['json'])

            # 验证HTTP状态码
            assert response.status_code == case_copy.get('expected_status', 200), \
                f"HTTP状态码不符合预期！期望: {case_copy.get('expected_status', 200)}, 实际: {response.status_code}"

            # 记录响应到日志和Allure报告
            result = self.log_response(response, "下架商品")

            # 执行动态断言
            for validate_item in case_copy.get('validate_data', []):
                path = validate_item['path']
                operator = validate_item['operator']
                expected_value = validate_item.get('value')

                # 提取实际值
                if path.startswith("$."):
                    key = path[2:]
                    actual_value = result.get(key)
                else:
                    actual_value = result.get(path)

                validate(actual_value, operator, expected_value, path)

            allure.attach("闲鱼商品下架成功", "下架阶段结果", attachment_type=allure.attachment_type.TEXT)

    @pytest.mark.order(6)
    @allure.title("下架闲鱼商品-运营端审核通过")
    def test_step6_audit_offline_product(self, admin_api_client, db):
        """步骤6：运营端审核下架商品"""
        with allure.step("运营端审核下架商品（审核通过）"):
            # 加载测试数据
            case = get_test_data(_XIANYU_OPS_YAML, "xianyu_audit_offline_product_test")[0]

            # 替换占位符
            case_copy = copy.deepcopy(case)
            if 'json' in case_copy:
                case_copy['json'] = replace_placeholders(case_copy['json'], self.test_vars)

            allure.attach(
                json.dumps(case_copy['json'], indent=2, ensure_ascii=False),
                "审核请求体",
                attachment_type=allure.attachment_type.JSON
            )

            # 发送请求（使用运营端客户端）
            response = admin_api_client.post(case_copy['endpoint'], json=case_copy['json'])

            # 验证HTTP状态码
            assert response.status_code == case_copy.get('expected_status', 200), \
                f"HTTP状态码不符合预期！期望: {case_copy.get('expected_status', 200)}, 实际: {response.status_code}"

            # 记录响应到日志和Allure报告
            result = self.log_response(response, "审核下架商品")

            # 执行动态断言
            for validate_item in case_copy.get('validate_data', []):
                path = validate_item['path']
                operator = validate_item['operator']
                expected_value = validate_item.get('value')

                # 提取实际值
                if path.startswith("$."):
                    key = path[2:]
                    actual_value = result.get(key)
                else:
                    actual_value = result.get(path)

                validate(actual_value, operator, expected_value, path)

            # 验证数据库中的审核状态
            product_db_id = self.test_vars.get('product_db_id')
            if product_db_id:
                db_result = db.fetch_one(
                    "SELECT audit_state FROM llxz_product.ct_product WHERE id = %s",
                    (product_db_id,)
                )
                assert db_result is not None, f"未找到商品记录，id={product_db_id}"
                actual_audit_state = db_result.get('audit_state')
                assert actual_audit_state == 2, \
                    f"商品审核状态不符合预期！期望值: 2 实际值: {actual_audit_state} 商品ID: {product_db_id}"

                allure.attach(
                    f"商品ID: {product_db_id}\n审核状态: {actual_audit_state}",
                    "数据库审核状态",
                    attachment_type=allure.attachment_type.TEXT
                )

            allure.attach("闲鱼商品下架审核通过", "审核阶段结果", attachment_type=allure.attachment_type.TEXT)

    # ==================== 测试用例3：修改闲鱼商品 ====================
    
    @pytest.mark.order(7)
    @allure.title("修改闲鱼商品-查询商品列表")
    def test_step7_query_product_for_update(self, xianyu_api_client, db):
        """步骤7：查询闲鱼商品用于修改"""
        with allure.step("查询闲鱼商品列表"):
            # 加载测试数据
            case = get_test_data(_XIANYU_OPS_YAML, "xianyu_query_product_for_update_test")[0]
            
            # 发送请求
            response = xianyu_api_client.post(case['endpoint'], json=case['json'])
            
            # 验证HTTP状态码
            assert response.status_code == case.get('expected_status', 200), \
                f"HTTP状态码不符合预期！期望: {case.get('expected_status', 200)}, 实际: {response.status_code}"
            
            # 记录响应到日志和Allure报告（附带请求参数）
            result = self.log_response(response, "查询商品列表", request_data={'endpoint': case['endpoint'], 'json': case['json']})
            
            # 验证业务成功
            assert result.get('businessSuccess') is True, \
                f"查询业务失败：{result.get('errorMessage', '未知错误')}"
            
            # 从records中获取最后一个商品的id
            records = result.get('data', {}).get('records', [])
            assert len(records) > 0, "未查询到闲鱼商品"
            
            # 取最后一个商品（索引为9或最后一个）
            last_index = min(9, len(records) - 1)
            product_id = records[last_index].get('productId')
            product_db_id = records[last_index].get('id')
            
            assert product_id is not None, "商品productId为空"
            assert product_db_id is not None, "商品id为空"
            
            # 保存到self.test_vars供后续步骤使用
            self.test_vars['product_id'] = product_id
            self.test_vars['product_db_id'] = product_db_id
            
            allure.attach(
                f"productId: {product_id}\n数据库id: {product_db_id}",
                "选中的商品信息",
                attachment_type=allure.attachment_type.TEXT
            )

    @pytest.mark.order(8)
    @allure.title("修改闲鱼商品-获取商品详情")
    def test_step8_get_product_info(self, xianyu_api_client, db):
        """步骤8：获取闲鱼商品详情"""
        with allure.step("获取闲鱼商品详细信息"):
            # 加载测试数据
            case = get_test_data(_XIANYU_OPS_YAML, "xianyu_get_product_info_test")[0]
            
            # 替换占位符
            case_copy = copy.deepcopy(case)
            if 'params' in case_copy:
                case_copy['params'] = replace_placeholders(case_copy['params'], self.test_vars)
            allure.attach(
                json.dumps(case_copy['params'], indent=2, ensure_ascii=False),
                "查询参数",
                attachment_type=allure.attachment_type.JSON
            )
            
            # 发送GET请求
            response = xianyu_api_client.get(case_copy['endpoint'], params=case_copy['params'])
            
            # 验证HTTP状态码
            assert response.status_code == case_copy.get('expected_status', 200), \
                f"HTTP状态码不符合预期！期望: {case_copy.get('expected_status', 200)}, 实际: {response.status_code}"
            
            # 记录响应到日志和Allure报告（附带请求参数）
            result = self.log_response(response, "获取商品详情", request_data={'endpoint': case_copy['endpoint'], 'params': case_copy['params']})
            
            # 验证业务成功
            assert result.get('businessSuccess') is True, \
                f"查询业务失败：{result.get('errorMessage', '未知错误')}"
            
            # 提取商品详情数据
            product_detail = result.get('data', {})
            assert product_detail, "商品详情为空"
            
            # 保存商品详情到self.test_vars供修改时使用
            # 注意：商品名称不能超过30个字符，需要预留"_自动化测试"后缀空间（7个字符）
            raw_name = product_detail.get('name', '')
            raw_title = product_detail.get('title', '')
            
            # 截断名称，确保添加后缀后不超过30个字符
            max_name_length = 30 - len("_自动化测试")  # 23个字符
            self.test_vars['product_name'] = raw_name[:max_name_length] if len(raw_name) > max_name_length else raw_name
            self.test_vars['product_title'] = raw_title[:max_name_length] if len(raw_title) > max_name_length else raw_title
            
            self.test_vars['product_detail_text'] = product_detail.get('detail', '')
            self.test_vars['category_id'] = product_detail.get('categoryId')
            self.test_vars['channel_cat_id'] = product_detail.get('channelCatId')
            self.test_vars['province'] = product_detail.get('province')
            self.test_vars['city'] = product_detail.get('city')
            self.test_vars['image_url'] = product_detail.get('images', [{}])[0].get('src', '') if product_detail.get('images') else ''
            
            # 提取租赁信息
            item_lease = product_detail.get('itemLeaseDTO', {})
            if item_lease:
                self.test_vars['inventory'] = item_lease.get('inventory')
                self.test_vars['market_price'] = item_lease.get('marketPrice')
                self.test_vars['deposit_price'] = item_lease.get('rentalDepositPriceInCent')
                self.test_vars['earliest_lease_days'] = item_lease.get('earliestLeaseDays')
                
                # 提取租金周期信息
                cycs = item_lease.get('cycs', [])
                if cycs:
                    cycle = cycs[0]
                    self.test_vars['cycle_days'] = cycle.get('days')
                    self.test_vars['day_or_month'] = cycle.get('dayOrMonth')
                    self.test_vars['price_cent'] = cycle.get('priceCent')
                    self.test_vars['total_rental'] = f"{cycle.get('days', 0) * cycle.get('priceCent', 0)}.00"
                    self.test_vars['cycle_id'] = cycle.get('id', '')
            
            allure.attach(
                json.dumps(self.test_vars, indent=2, ensure_ascii=False, default=str),
                "提取的商品信息变量",
                attachment_type=allure.attachment_type.JSON
            )

    @pytest.mark.order(9)
    @allure.title("修改闲鱼商品-执行修改操作")
    def test_step9_update_product(self, xianyu_api_client, db):
        """步骤9：修改闲鱼商品"""
        with allure.step("执行修改操作"):
            # 加载测试数据
            case = get_test_data(_XIANYU_OPS_YAML, "xianyu_update_product_test")[0]
            
            # 替换占位符
            case_copy = copy.deepcopy(case)
            if 'json' in case_copy:
                case_copy['json'] = replace_placeholders(case_copy['json'], self.test_vars)
            
            # 验证关键字段
            json_body = case_copy.get('json', {})
            required_fields = [
                'productId', 'id', 'name', 'title', 'categoryId', 
                'channelCatId', 'province', 'city'
            ]
            for field in required_fields:
                field_value = json_body.get(field)
                if field_value is None:
                    raise ValueError(f"关键字段 {field} 为空")
            
            # 验证商品名称长度（不能为空且不超过30个字符）
            name_value = json_body.get('name', '')
            title_value = json_body.get('title', '')
            
            # 检查是否为空
            if not name_value or name_value.strip() == '':
                raise ValueError("商品名称(name)不能为空")
            if not title_value or title_value.strip() == '':
                raise ValueError("商品标题(title)不能为空")
            
            # 检查长度
            name_length = len(name_value)
            title_length = len(title_value)
            
            if name_length > 30:
                raise ValueError(f"商品名称(name)长度不能超过30个字符，当前: {name_length}")
            if title_length > 30:
                raise ValueError(f"商品标题(title)长度不能超过30个字符，当前: {title_length}")
            
            # 附加请求体到Allure报告
            allure.attach(
                json.dumps(case_copy['json'], indent=2, ensure_ascii=False),
                "修改商品请求体（已替换变量）",
                attachment_type=allure.attachment_type.JSON
            )
            
            # 附加调试信息到Allure报告
            debug_info = (
                f"请求URL: {case_copy['endpoint']}\n"
                f"请求方法: POST\n"
                f"\n关键字段检查:\n"
                f"  productId: {json_body.get('productId')}\n"
                f"  id: {json_body.get('id')}\n"
                f"  name: {json_body.get('name')}\n"
                f"  title: {json_body.get('title')}\n"
                f"  categoryId: {json_body.get('categoryId')}\n"
                f"\n完整变量池:\n"
                f"{json.dumps(self.test_vars, indent=2, ensure_ascii=False, default=str)}"
            )
            allure.attach(debug_info, "调试信息", attachment_type=allure.attachment_type.TEXT)
            
            # 发送请求
            response = xianyu_api_client.post(case_copy['endpoint'], json=case_copy['json'])
            
            # 验证HTTP状态码
            assert response.status_code == case_copy.get('expected_status', 200), \
                f"HTTP状态码不符合预期！期望: {case_copy.get('expected_status', 200)}, 实际: {response.status_code}"
            
            # 记录响应到日志和Allure报告（附带请求参数）
            result = self.log_response(response, "修改商品", request_data={'endpoint': case_copy['endpoint'], 'json': case_copy['json']})
            
            # 执行动态断言
            with allure.step("执行断言验证"):
                for validate_item in case_copy.get('validate_data', []):
                    path = validate_item['path']
                    operator = validate_item['operator']
                    expected_value = validate_item.get('value')
                    
                    # 提取实际值
                    if path.startswith("$."):
                        key = path[2:]
                        actual_value = result.get(key)
                    else:
                        actual_value = result.get(path)
                    
                    # 记录断言到Allure
                    allure.attach(
                        f"断言路径: {path}\n操作符: {operator}\n期望值: {expected_value}\n实际值: {actual_value}",
                        f"断言: {path}",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    
                    # 执行断言
                    validate(actual_value, operator, expected_value, path)
            
            allure.attach("闲鱼商品修改成功", "修改阶段结果", attachment_type=allure.attachment_type.TEXT)

    @pytest.mark.order(10)
    @allure.title("修改闲鱼商品-运营端审核通过")
    def test_step10_audit_updated_product(self, admin_api_client, db):
        """步骤10：运营端审核修改后的商品"""
        with allure.step("运营端审核修改后的商品（审核通过）"):
            # 加载测试数据
            case = get_test_data(_XIANYU_OPS_YAML, "xianyu_audit_updated_product_test")[0]
            
            # 替换占位符
            case_copy = copy.deepcopy(case)
            if 'json' in case_copy:
                case_copy['json'] = replace_placeholders(case_copy['json'], self.test_vars)
            
            allure.attach(
                json.dumps(case_copy['json'], indent=2, ensure_ascii=False),
                "审核请求体",
                attachment_type=allure.attachment_type.JSON
            )
            
            # 发送请求（使用运营端客户端）
            response = admin_api_client.post(case_copy['endpoint'], json=case_copy['json'])
            
            # 验证HTTP状态码
            assert response.status_code == case_copy.get('expected_status', 200), \
                f"HTTP状态码不符合预期！期望: {case_copy.get('expected_status', 200)}, 实际: {response.status_code}"
            
            # 记录响应到日志和Allure报告（附带请求参数）
            result = self.log_response(response, "审核修改商品", request_data={'endpoint': case_copy['endpoint'], 'json': case_copy['json']})
            
            # 执行动态断言
            with allure.step("执行断言验证"):
                for validate_item in case_copy.get('validate_data', []):
                    path = validate_item['path']
                    operator = validate_item['operator']
                    expected_value = validate_item.get('value')
                    
                    # 提取实际值
                    if path.startswith("$."):
                        key = path[2:]
                        actual_value = result.get(key)
                    else:
                        actual_value = result.get(path)
                    
                    # 记录断言到Allure
                    allure.attach(
                        f"断言路径: {path}\n操作符: {operator}\n期望值: {expected_value}\n实际值: {actual_value}",
                        f"断言: {path}",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    
                    # 执行断言
                    validate(actual_value, operator, expected_value, path)
            
            # 验证数据库中的审核状态
            product_db_id = self.test_vars.get('product_db_id')
            if product_db_id:
                db_result = db.fetch_one(
                    "SELECT audit_state FROM llxz_product.ct_product WHERE id = %s",
                    (product_db_id,)
                )
                assert db_result is not None, f"未找到商品记录，id={product_db_id}"
                actual_audit_state = db_result.get('audit_state')
                assert actual_audit_state == 2, \
                    f"商品审核状态不符合预期！期望值: 2 实际值: {actual_audit_state} 商品ID: {product_db_id}"
                
                allure.attach(
                    f"商品ID: {product_db_id}\n审核状态: {actual_audit_state}",
                    "数据库审核状态",
                    attachment_type=allure.attachment_type.TEXT
                )
            
            allure.attach("闲鱼商品修改审核通过", "审核阶段结果", attachment_type=allure.attachment_type.TEXT)
