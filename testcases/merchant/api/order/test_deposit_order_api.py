import allure
import json
import pytest
from common.logger import logger
from utils.data_loader import get_test_data, get_global_variables
from utils.variable_utils import get_value_by_path, validate
from common.test_helpers import replace_placeholders

# 预先加载所有用例数据
_ALL_CASES = get_test_data("data/merchant/api/order/deposit_order_api.yaml", "deposit_order_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 deposit_order_api.yaml")


def get_case_by_id(case_id: str) -> dict:
    for case in _ALL_CASES:
        if case['case_id'] == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")


@allure.epic("商家端")
@allure.feature("商家端--补押金管理")
@allure.story("补押金查询与取消")
class TestDepositOrderManagement:
    """补押金管理 - 查询与取消（复杂场景，多步骤串联）"""

    _global_vars = None

    # 跨步骤共享的类属性
    _query_original_order_id = None   # 用例1提取的 originalOrderId → 用例2查询条件
    _cancel_deposit_order_id = None   # 用例3提取的待支付 orderId → 用例4取消条件

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("deposit_order_api.yaml")
        return cls._global_vars.copy()

    # ==================== 步骤1：无查询条件查询 ====================
    @pytest.mark.order(1)
    @allure.title("DO_001 - 无查询条件-查询补押金列表")
    def test_query_deposit_order_no_condition(self, merchant_api_client, db):
        """用例1：不带查询条件，获取 originalOrderId 等数据"""
        case = get_case_by_id("DO_001")
        global_vars = self._load_global_vars()
        case = replace_placeholders(case, global_vars)
        # 发送请求
        with allure.step("发送查询请求"):
            endpoint = case['endpoint']
            body = case.get('json', {})
            allure.attach(json.dumps(body, ensure_ascii=False, indent=2),
                          name="请求体", attachment_type=allure.attachment_type.JSON)
            resp = merchant_api_client.post(endpoint, json=body)
            assert resp.status_code == case['expected_status']
            resp_json = resp.json()
            allure.attach(json.dumps(resp_json, ensure_ascii=False, indent=2)[:5000],
                          name="完整响应体", attachment_type=allure.attachment_type.JSON)

        # 执行标准断言
        with allure.step("执行标准断言"):
            for check in case['validate_data']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                validate(actual, check['operator'], check['value'], path)

        # 提取跨步骤共享数据
        records = resp_json.get('data', {}).get('records', [])
        assert len(records) > 0, "补押金列表为空，无法提取测试数据"

        first_record = records[0]
        self.__class__._query_original_order_id = first_record['originalOrderId']

        logger.info(f"提取 originalOrderId={self._query_original_order_id}")
        allure.attach(
            f"originalOrderId: {self._query_original_order_id}",
            name="提取的跨步骤变量",
            attachment_type=allure.attachment_type.TEXT
        )

    # ==================== 步骤2：以订单编号查询 ====================
    @pytest.mark.order(2)
    @allure.title("DO_002 - 以订单编号-查询补押金列表")
    def test_query_deposit_order_by_order_id(self, merchant_api_client, db):
        """用例2：以 originalOrderId 为查询条件，验证返回结果匹配"""
        if not self._query_original_order_id:
            pytest.skip("用例1未提取到 originalOrderId，跳过用例2")

        case = get_case_by_id("DO_002")
        global_vars = self._load_global_vars()
        global_vars['query_original_order_id'] = self._query_original_order_id

        allure.attach(f"查询条件 orderId={self._query_original_order_id}",
                      name="动态查询条件", attachment_type=allure.attachment_type.TEXT)

        # 手动替换并发送请求（因为 execute_test_case 会两次替换，这里用例逻辑简单直接处理）
        from common.test_helpers import replace_placeholders
        case_replaced = replace_placeholders(case, global_vars)

        with allure.step("发送查询请求"):
            endpoint = case_replaced['endpoint']
            body = case_replaced.get('json', {})
            allure.attach(json.dumps(body, ensure_ascii=False, indent=2),
                          name="请求体", attachment_type=allure.attachment_type.JSON)
            resp = merchant_api_client.post(endpoint, json=body)
            assert resp.status_code == case_replaced['expected_status']
            resp_json = resp.json()
            allure.attach(json.dumps(resp_json, ensure_ascii=False, indent=2)[:5000],
                          name="完整响应体", attachment_type=allure.attachment_type.JSON)

        with allure.step("执行标准断言"):
            for check in case_replaced['validate_data']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                # 替换断言值中的变量
                from common.test_helpers import replace_placeholders
                expected_val = replace_placeholders(check['value'], global_vars)
                validate(actual, check['operator'], expected_val, path)

    # ==================== 步骤3：以订单状态-待支付查询 ====================
    @pytest.mark.order(3)
    @allure.title("DO_003 - 以订单状态待支付-查询补押金列表")
    def test_query_deposit_order_by_status(self, merchant_api_client, db):
        """用例3：以 orderStatus=01 为查询条件，断言所有记录 orderStatus 均为 01，并提取 orderId 用于取消"""
        case = get_case_by_id("DO_003")
        global_vars = self._load_global_vars()
        case = replace_placeholders(case, global_vars)
        with allure.step("发送查询请求（orderStatus=01）"):
            endpoint = case['endpoint']
            body = case.get('json', {})
            allure.attach(json.dumps(body, ensure_ascii=False, indent=2),
                          name="请求体", attachment_type=allure.attachment_type.JSON)
            resp = merchant_api_client.post(endpoint, json=body)
            assert resp.status_code == case['expected_status']
            resp_json = resp.json()
            print("用例3--resp_json", resp_json)
            allure.attach(json.dumps(resp_json, ensure_ascii=False, indent=2)[:5000],
                          name="完整响应体", attachment_type=allure.attachment_type.JSON)

        # 执行标准断言（含 orderStatus all_eq "01"）
        with allure.step("执行标准断言（含 orderStatus 校验）"):
            for check in case['validate_data']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                validate(actual, check['operator'], check['value'], path)

        # 提取待支付订单的 orderId → 用于用例4取消
        records = resp_json.get('data', {}).get('records', [])
        # 用例3查询可能返回空列表（如文档所示），如果返回有数据则提取
        if len(records) > 0:
            self.__class__._cancel_deposit_order_id = records[0]['orderId']
            logger.info(f"提取待支付 orderId={self._cancel_deposit_order_id}，用于取消测试")
            allure.attach(f"cancel_deposit_order_id: {self._cancel_deposit_order_id}",
                          name="提取的取消订单ID", attachment_type=allure.attachment_type.TEXT)
        else:
            logger.warning("待支付补押金列表为空，无法提取取消用的 orderId，用例4将被跳过")
            allure.attach("待支付列表为空", name="提取取消订单ID失败",
                          attachment_type=allure.attachment_type.TEXT)

    # ==================== 步骤4：取消补押金 ====================
    @pytest.mark.order(4)
    @allure.title("DO_004 - 取消补押金")
    def test_cancel_deposit_order(self, merchant_api_client, db):
        """用例4：使用用例3提取的待支付 orderId 调用取消接口"""
        if not self._cancel_deposit_order_id:
            pytest.skip("用例3未提取到待支付 orderId，跳过取消测试")

        case = get_case_by_id("DO_004")
        global_vars = self._load_global_vars()
        global_vars['cancel_deposit_order_id'] = self._cancel_deposit_order_id

        from common.test_helpers import replace_placeholders
        case_replaced = replace_placeholders(case, global_vars)

        allure.attach(f"取消订单 orderId={self._cancel_deposit_order_id}",
                      name="取消订单ID", attachment_type=allure.attachment_type.TEXT)

        with allure.step("发送取消请求"):
            endpoint = case_replaced['endpoint']
            params = case_replaced.get('params', {})
            allure.attach(f"GET {endpoint}?orderId={params.get('orderId', '')}",
                          name="请求 URL", attachment_type=allure.attachment_type.TEXT)
            resp = merchant_api_client.get(endpoint, params=params)
            assert resp.status_code == case_replaced['expected_status']
            resp_json = resp.json()
            allure.attach(json.dumps(resp_json, ensure_ascii=False, indent=2)[:5000],
                          name="完整响应体", attachment_type=allure.attachment_type.JSON)

        with allure.step("执行标准断言"):
            for check in case_replaced['validate_data']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                from common.test_helpers import replace_placeholders
                expected_val = replace_placeholders(check['value'], global_vars)
                validate(actual, check['operator'], expected_val, path)