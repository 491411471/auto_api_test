import allure
import pytest
import random
import time
from common.logger import logger
from utils.variable_utils import get_value_by_path, validate
from common.test_helpers import replace_placeholders,execute_test_case
from utils.data_loader import get_test_data, get_global_variables

# 预先加载所有用例数据（只加载一次）
_ALL_CASES = get_test_data("repair_order_api.yaml", "repair_order_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 repair_order_api.yaml")

def get_case_by_id(case_id: str):
    for case in _ALL_CASES:
        if case['case_id'] == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")

@allure.epic("商家端")
@allure.feature("商家端--补订单")
@allure.story("补订单接口测试")
class TestRepairOrder:
    _global_vars = None
    _repair_order_id = None
    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("repair_order_api.yaml")
        return cls._global_vars.copy()

    @pytest.fixture(autouse=True)
    def setup(self):
        """加载测试数据（复用模块级已加载的 YAML，避免重复解析）"""
        self.config = get_test_data("data/merchant/api/order/repair_order_api.yaml")
        yield

    @allure.title("补订单接口-正常流程测试")
    def test_repair_order_normal(self, merchant_api_client, db, global_vars):
        """正常提交补订单测试（含自动重试机制）"""
        # 准备测试数据
        base_vars = global_vars.copy()
        shop_id = base_vars.get('shop_id', '71008738021cd3393bacbac182bd6a86af0b5c87')

        # 获取重试配置
        retry_cfg = self.config.get('retry_config', {})
        max_attempts = retry_cfg.get('max_attempts', 3)
        error_keywords = retry_cfg.get('error_keywords', [])

        # 记录已尝试的订单ID，避免重复
        tried_order_ids = set()

        for attempt in range(1, max_attempts + 1):
            logger.info(f"========== 第 {attempt} 次尝试执行补订单流程 ==========")

            # 创建当前尝试的子步骤容器
            with allure.step(f"========== 第 {attempt}/{max_attempts} 次尝试 =========="):
                # 1. 查询可补订单（排除已尝试的订单）
                with allure.step(f"步骤1: 查询可补订单"):
                    sql_template = self.config['merchant']['query_order_sql']
                    sql = sql_template.replace('${shop_id}', shop_id)

                    # 如果有已尝试的订单，排除它们
                    if tried_order_ids:
                        order_ids_str = ','.join([f"'{oid}'" for oid in tried_order_ids])
                        # 在 ORDER BY 之前插入 NOT IN 条件
                        upper_sql = sql.upper()
                        order_by_pos = upper_sql.find('ORDER BY')
                        if order_by_pos != -1:
                            not_in_clause = f" AND order_id NOT IN ({order_ids_str})"
                            sql = sql[:order_by_pos] + not_in_clause + "\n" + sql[order_by_pos:]
                        elif 'WHERE' in upper_sql:
                            sql += f" AND order_id NOT IN ({order_ids_str})"
                        else:
                            sql += f" WHERE order_id NOT IN ({order_ids_str})"
                        allure.attach(f"排除已尝试订单: {', '.join(tried_order_ids)}",
                                      name="排除订单列表",
                                      attachment_type=allure.attachment_type.TEXT)

                    logger.info(f"执行SQL: {sql}")
                    allure.attach(sql, name="查询SQL", attachment_type=allure.attachment_type.TEXT)

                    result = db.fetch_one(sql)
                    if result is None:
                        skip_msg = f"第{attempt}次尝试：未查询到可补订单"
                        allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                        logger.warning(skip_msg)
                        pytest.skip(skip_msg)

                    order_id = result['order_id']
                    product_id = result['product_id']
                    tried_order_ids.add(order_id)
                    logger.info(f"获取到订单号: {order_id}, product_id: {product_id}")
                    allure.attach(f"订单号: {order_id}\n商品ID: {product_id}",
                                  name="查询结果",
                                  attachment_type=allure.attachment_type.TEXT)

                # 2. 获取补订单用途
                with allure.step(f"步骤2: 获取补订单用途列表"):
                    get_cfg = self.config['merchant']['get_repair_order_list']
                    params = replace_placeholders(get_cfg['params_template'], {
                        'shop_id': shop_id,
                        'product_id': product_id
                    })

                    allure.attach(str(params), name="请求参数", attachment_type=allure.attachment_type.JSON)

                    resp = merchant_api_client.get(get_cfg['endpoint'], params=params)
                    assert resp.status_code == get_cfg['expected_status']
                    resp_json = resp.json()

                    allure.attach(str(resp_json), name="接口响应", attachment_type=allure.attachment_type.JSON)

                    # 检查接口是否成功
                    if resp_json.get('businessSuccess') is False or resp_json.get('data') is None:
                        error_msg = resp_json.get('errorMessage', '未知错误')
                        logger.warning(f"第{attempt}次尝试：获取用途列表失败: {error_msg}")
                        allure.attach(f"获取用途列表失败: {error_msg}",
                                      name="失败原因",
                                      attachment_type=allure.attachment_type.TEXT)

                        if attempt < max_attempts:
                            logger.info(f"等待后重新查询订单并再次尝试...")
                            continue  # 重新开始循环，查询新订单
                        else:
                            pytest.fail(f"已重试{max_attempts}次，仍无法获取用途列表: {error_msg}")

                    # 安全地获取 records
                    data = resp_json.get('data', {})
                    records = data.get('records', []) if data else []
                    assert len(records) > 0, "用途列表为空"

                    allure.attach(f"可用用途数量: {len(records)}",
                                  name="用途列表统计",
                                  attachment_type=allure.attachment_type.TEXT)

                    chosen = random.choice(records)
                    repair_id = chosen['id']
                    repair_price = chosen['price']
                    repair_settlement = chosen['settlementProportion']
                    repair_name = chosen['name']
                    logger.info(f"选择用途: id={repair_id}, name={repair_name}, price={repair_price}")
                    allure.attach(f"用途ID: {repair_id}\n用途名称: {repair_name}\n价格: {repair_price}\n结算比例: {repair_settlement}",
                                  name="选中用途详情",
                                  attachment_type=allure.attachment_type.TEXT)

                # 3. 提交补订单
                with allure.step(f"步骤3: 提交补订单"):
                    submit_cfg = self.config['merchant']['submit_repair_order']
                    body = replace_placeholders(submit_cfg['body_template'], {
                        'order_id': order_id,
                        'repair_id': repair_id,
                        'repair_price': repair_price,
                        'repair_settlement': repair_settlement,
                        'remark': '自动化补押金测试'
                    })

                    allure.attach(str(body), name="请求体", attachment_type=allure.attachment_type.JSON)

                    resp = merchant_api_client.post(submit_cfg['endpoint'], json=body)
                    assert resp.status_code == submit_cfg['expected_status']
                    resp_json = resp.json()
                    logger.info(f"提交补订单响应: {resp_json}")

                    allure.attach(str(resp_json), name="接口响应", attachment_type=allure.attachment_type.JSON)

                    # 检查是否为业务约束条件（应跳过而非失败）
                    error_msg = resp_json.get('errorMessage') or ''

                    # 业务约束关键词（这些是正常的业务限制，不是技术错误）
                    business_constraint_keywords = [
                        "补订单累计金额已超出上限",
                        "订单状态不允许补订单",
                    ]

                    is_business_constraint = any(keyword in error_msg for keyword in business_constraint_keywords)

                    # 如果是业务约束条件，跳过此用例
                    if is_business_constraint:
                        skip_reason = f"触发业务约束条件: {error_msg}"
                        logger.info(f"[业务约束] {skip_reason}")
                        allure.attach(
                            f"跳过原因: 触发业务约束条件（非技术错误）\n"
                            f"错误类型: {resp_json.get('responseType', 'N/A')}\n"
                            f"错误信息: {error_msg}\n\n"
                            f"说明: 这是正常的业务限制，不是接口故障",
                            name="用例跳过-业务约束",
                            attachment_type=allure.attachment_type.TEXT
                        )
                        pytest.skip(skip_reason)

                    # 检查是否为可重试的错误
                    # 动态替换错误关键词中的 {name} 和 {price} 占位符
                    dynamic_keywords = []
                    for kw in error_keywords:
                        try:
                            # 尝试替换所有支持的占位符
                            formatted_kw = kw.format(name=repair_name, price=repair_price)
                            dynamic_keywords.append(formatted_kw)
                        except KeyError:
                            # 如果占位符不匹配，保持原样
                            dynamic_keywords.append(kw)

                    is_retryable_error = any(keyword in error_msg for keyword in dynamic_keywords)

                    if resp_json.get('businessSuccess') is False and is_retryable_error:
                        logger.warning(f"第{attempt}次提交遇到可重试错误: {error_msg}")
                        allure.attach(f"错误类型: 可重试错误\n错误消息: {error_msg}\n匹配关键词: {dynamic_keywords}",
                                      name="错误分析",
                                      attachment_type=allure.attachment_type.TEXT)

                        if attempt < max_attempts:
                            logger.info(f"等待后重新查询订单并再次尝试...")
                            allure.attach(f"将继续重试，剩余次数: {max_attempts - attempt}",
                                          name="重试决策",
                                          attachment_type=allure.attachment_type.TEXT)
                            continue  # 重新开始循环，查询新订单
                        else:
                            # 达到最大重试次数，所有订单均无法补订单，跳过此用例
                            skip_msg = (
                                f"已重试{max_attempts}次，所有订单均无法提交补订单\n"
                                f"  最终错误: {error_msg}\n"
                                f"  已尝试订单: {', '.join(tried_order_ids) if tried_order_ids else '无'}"
                            )
                            allure.attach(skip_msg, name="最终结果-跳过用例",
                                          attachment_type=allure.attachment_type.TEXT)
                            logger.warning(skip_msg)
                            pytest.skip(skip_msg)

                    # 验证提交成功
                    with allure.step("步骤4: 验证响应数据"):
                        validation_results = []
                        for check in submit_cfg['validate']:
                            path = check['path'].lstrip('$').lstrip('.')
                            actual = get_value_by_path(resp_json, path)
                            try:
                                validate(actual, check['operator'], check['value'], path)
                                validation_results.append(f"{path}: {check['operator']} {check['value']} (实际: {actual})")
                            except AssertionError as e:
                                validation_results.append(f"{path}: {str(e)}")
                                raise

                        allure.attach("\n".join(validation_results),
                                      name="断言结果",
                                      attachment_type=allure.attachment_type.TEXT)

                logger.info("补订单提交成功")
                allure.attach("流程执行成功", name="最终结果", attachment_type=allure.attachment_type.TEXT)
                break

    @allure.title("补订单接口-缺少repairOrderConfig参数中的ID测试")
    def test_repair_order_missing_order_id(self, merchant_api_client, db):
        """缺少订单ID测试"""
        case = get_case_by_id('RO_002')
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)

    # @allure.title("补订单接口-缺少isMembership参数测试")
    # def test_repair_order_missing_is_membership(self, merchant_api_client, db):
    #     """缺少isMembership参数测试"""
    #     case = get_case_by_id('RO_003')
    #     global_vars = self._load_global_vars()
    #     allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
    #     execute_test_case(case, merchant_api_client, db, global_vars)

    # @allure.title("补订单接口-缺少repairOrderConfig测试")
    # def test_repair_order_missing_repair_config(self, merchant_api_client, db):
    #     """缺少repairOrderConfig测试"""
    #     case = get_case_by_id('RO_004')
    #     global_vars = self._load_global_vars()
    #     allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
    #     execute_test_case(case, merchant_api_client, db, global_vars)

    # @allure.title("补订单接口-repairOrderConfig缺少id测试")
    # def test_repair_order_missing_repair_id(self, merchant_api_client, db):
    #     """repairOrderConfig缺少id测试"""
    #     case = get_case_by_id('RO_005')
    #     global_vars = self._load_global_vars()
    #     allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
    #     execute_test_case(case, merchant_api_client, db, global_vars)

    # @allure.title("补订单接口-repairOrderConfig缺少price测试")
    # def test_repair_order_missing_repair_price(self, merchant_api_client, db):
    #     """repairOrderConfig缺少price测试"""
    #     case = get_case_by_id('RO_006')
    #     print("case", case)
    #     global_vars = self._load_global_vars()
    #     allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
    #     execute_test_case(case, merchant_api_client, db, global_vars, self.config.get('retry_config'))

    # @allure.title("补订单接口-repairOrderConfig缺少settlementProportion测试")
    # def test_repair_order_missing_repair_settlement(self, merchant_api_client):
    #     """repairOrderConfig缺少settlementProportion测试"""
    #     case = get_case_by_id('RO_007')
    #     global_vars = self._load_global_vars()
    #     allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
    #     execute_test_case(case, merchant_api_client, db, global_vars, self.config.get('retry_config'))

    # @allure.title("补订单接口-价格为0测试")
    # def test_repair_order_price_zero(self, merchant_api_client):
    #     """价格为0测试"""
    #     case = self._get_case_by_id('RO_008')
    #     self._execute_test_case(merchant_api_client, case)
    #
    # @allure.title("补订单接口-价格为负数测试")
    # def test_repair_order_price_negative(self, merchant_api_client):
    #     """价格为负数测试"""
    #     case = self._get_case_by_id('RO_009')
    #     self._execute_test_case(merchant_api_client, case)
    #
    # @allure.title("补订单接口-结算比例超过100%测试")
    # def test_repair_order_settlement_over_100(self, merchant_api_client):
    #     """结算比例超过100%测试"""
    #     case = self._get_case_by_id('RO_010')
    #     self._execute_test_case(merchant_api_client, case)
    #
    # @allure.title("补订单接口-结算比例为0测试")
    # def test_repair_order_settlement_zero(self, merchant_api_client):
    #     """结算比例为0测试"""
    #     case = self._get_case_by_id('RO_011')
    #     self._execute_test_case(merchant_api_client, case)
    #
    # @allure.title("补订单接口-备注超长测试")
    # def test_repair_order_remark_too_long(self, merchant_api_client):
    #     """备注超长测试"""
    #     case = self._get_case_by_id('RO_012')
    #     self._execute_test_case(merchant_api_client, case)
    #
    # @allure.title("补订单接口-isMembership参数非法测试")
    # def test_repair_order_invalid_is_membership(self, merchant_api_client):
    #     """isMembership参数非法测试"""
    #     case = self._get_case_by_id('RO_013')
    #     self._execute_test_case(merchant_api_client, case)
    #
    # @allure.title("补订单接口-重复提交相同用途测试")
    # def test_repair_order_duplicate_submission(self, merchant_api_client, db, global_vars):
    #     """重复提交相同用途测试"""
    #     # 准备测试数据
    #     base_vars = global_vars.copy()
    #     shop_id = base_vars.get('shop_id', '71008738021cd3393bacbac182bd6a86af0b5c87')
    #
    #     # 查询可补订单
    #     sql = self.config['merchant']['query_order_sql'].replace('${shop_id}', shop_id)
    #     result = db.fetch_one(sql)
    #     assert result is not None, "未查询到可补订单"
    #
    #     order_id = result['order_id']
    #     product_id = result['product_id']
    #
    #     # 获取补订单用途
    #     get_cfg = self.config['merchant']['get_repair_order_list']
    #     params = replace_placeholders(get_cfg['params_template'], {
    #         'shop_id': shop_id,
    #         'product_id': product_id
    #     })
    #
    #     resp = merchant_api_client.get(get_cfg['endpoint'], params=params)
    #     assert resp.status_code == get_cfg['expected_status']
    #     resp_json = resp.json()
    #
    #     records = resp_json['data']['records']
    #     assert len(records) > 0, "用途列表为空"
    #
    #     chosen = random.choice(records)
    #     repair_id = chosen['id']
    #     repair_price = chosen['price']
    #     repair_settlement = chosen['settlementProportion']
    #     repair_name = chosen['name']
    #
    #     # 第一次提交
    #     submit_cfg = self.config['merchant']['submit_repair_order']
    #     body = replace_placeholders(submit_cfg['body_template'], {
    #         'order_id': order_id,
    #         'repair_id': repair_id,
    #         'repair_price': repair_price,
    #         'repair_settlement': repair_settlement,
    #         'remark': '第一次提交'
    #     })
    #
    #     resp = merchant_api_client.post(submit_cfg['endpoint'], json=body)
    #     assert resp.status_code == submit_cfg['expected_status']
    #
    #     # 第二次提交（重复提交）
    #     body['repairOrderConfig']['beizhu'] = '重复提交测试'
    #     resp = merchant_api_client.post(submit_cfg['endpoint'], json=body)
    #     assert resp.status_code == submit_cfg['expected_status']
    #     resp_json = resp.json()
    #
    #     # 验证响应
    #     case = self._get_case_by_id('RO_014')
    #     for check in case['validate_data']:
    #         path = check['path'].lstrip('$').lstrip('.')
    #         actual = get_value_by_path(resp_json, path)
    #         validate(actual, check['operator'], check['value'], path)
    #
    #     logger.info("重复提交测试通过")
    #
    # @allure.title("补订单接口-订单状态不允许补订单测试")
    # def test_repair_order_invalid_order_status(self, merchant_api_client, db, global_vars):
    #     """订单状态不允许补订单测试"""
    #     # 准备测试数据
    #     base_vars = global_vars.copy()
    #     shop_id = base_vars.get('shop_id', '71008738021cd3393bacbac182bd6a86af0b5c87')
    #
    #     # 查询已完成订单
    #     sql = """
    #     SELECT order_id
    #     FROM llxz_order.ct_user_orders
    #     WHERE status = '09'  -- 已完成状态
    #       AND shop_id = '${shop_id}'
    #     ORDER BY create_time DESC
    #     LIMIT 1
    #     """.replace('${shop_id}', shop_id)
    #
    #     result = db.fetch_one(sql)
    #     if result is None:
    #         pytest.skip("未查询到已完成订单，跳过测试")
    #
    #     completed_order_id = result['order_id']
    #
    #     # 获取补订单用途
    #     get_cfg = self.config['merchant']['get_repair_order_list']
    #     params = replace_placeholders(get_cfg['params_template'], {
    #         'shop_id': shop_id,
    #         'product_id': '1735266880919'  # 使用一个默认商品ID
    #     })
    #
    #     resp = merchant_api_client.get(get_cfg['endpoint'], params=params)
    #     assert resp.status_code == get_cfg['expected_status']
    #     resp_json = resp.json()
    #
    #     records = resp_json['data']['records']
    #     assert len(records) > 0, "用途列表为空"
    #
    #     chosen = random.choice(records)
    #     repair_id = chosen['id']
    #     repair_price = chosen['price']
    #     repair_settlement = chosen['settlementProportion']
    #     repair_name = chosen['name']
    #
    #     # 提交补订单
    #     submit_cfg = self.config['merchant']['submit_repair_order']
    #     body = replace_placeholders(submit_cfg['body_template'], {
    #         'order_id': completed_order_id,
    #         'repair_id': repair_id,
    #         'repair_price': repair_price,
    #         'repair_settlement': repair_settlement,
    #         'remark': '已完成订单补单测试'
    #     })
    #
    #     resp = merchant_api_client.post(submit_cfg['endpoint'], json=body)
    #     assert resp.status_code == submit_cfg['expected_status']
    #     resp_json = resp.json()
    #
    #     # 验证响应
    #     case = self._get_case_by_id('RO_015')
    #     for check in case['validate_data']:
    #         path = check['path'].lstrip('$').lstrip('.')
    #         actual = get_value_by_path(resp_json, path)
    #         validate(actual, check['operator'], check['value'], path)
    #
    #     logger.info("订单状态不允许补订单测试通过")
    #
    # def _get_case_by_id(self, case_id):
    #     """根据case_id获取测试用例"""
    #     for case in self.config['repair_order_tests']:
    #         if case['case_id'] == case_id:
    #             return case
    #     raise ValueError(f"未找到case_id为{case_id}的测试用例")
    #
    # def _execute_test_case(self, merchant_api_client, case):
    #     """执行单个测试用例"""
    #     # 准备请求数据
    #     endpoint = case['endpoint']
    #     method = case['method']
    #     body = case['body']
    #
    #     # 发送请求
    #     if method.upper() == 'POST':
    #         resp = merchant_api_client.post(endpoint, json=body)
    #     else:
    #         resp = merchant_api_client.get(endpoint, params=body)
    #
    #     assert resp.status_code == case['expected_status']
    #     resp_json = resp.json()
    #
    #     # 验证响应
    #     for check in case['validate_data']:
    #         path = check['path'].lstrip('$').lstrip('.')
    #         actual = get_value_by_path(resp_json, path)
    #         validate(actual, check['operator'], check['value'], path)
    #
    #     logger.info(f"测试用例执行成功: {case['title']}")