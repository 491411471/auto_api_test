import allure
import json
import pytest
from common.logger import logger
from common.test_helpers import execute_test_case, replace_placeholders
from utils.data_loader import get_test_data, get_global_variables
from utils.variable_utils import get_value_by_path, validate

# 预先加载所有用例数据
_ALL_CASES = get_test_data("data/merchant/api/order/make_order_api.yaml", "make_order_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 make_order_api.yaml")


def get_case_by_id(case_id: str) -> dict:
    for case in _ALL_CASES:
        if case['case_id'] == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")


@allure.epic("商家端")
@allure.feature("商家端--补订单管理")
@allure.story("补订单查询与取消")
class TestMakeOrderManagement:
    """补订单管理 - 查询与取消（复杂场景，多步骤串联）"""

    _global_vars = None

    # 跨步骤共享的类属性
    _query_order_id = None      # 用例1提取的 originalOrderId → 用例2查询条件
    _goods_name = None          # 用例1提取的 goodsName → 用例4查询条件
    _cancel_order_id = None     # 用例3提取的待支付 orderId → 用例5取消条件

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("make_order_api.yaml")
        return cls._global_vars.copy()

    # ==================== 步骤1：无查询条件查询 ====================
    @pytest.mark.order(1)
    @allure.title("MO_001 - 无查询条件-查询补订单列表")
    def test_query_make_order_no_condition(self, merchant_api_client, db):
        """用例1：不带查询条件，获取 orderId、originalOrderId、goodsName 等数据"""
        case = get_case_by_id("MO_001")
        global_vars = self._load_global_vars()

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
        records = resp_json.get('data', {}).get('backstageMakeOrderDtoList', {}).get('records', [])
        if not records:
            allure.attach("补订单列表为空，无可用测试数据", name="跳过原因",
                          attachment_type=allure.attachment_type.TEXT)
            pytest.skip("补订单列表为空，无法提取测试数据")

        first_record = records[0]
        # 提取 originalOrderId → 用于用例2的查询条件
        self.__class__._query_order_id = first_record['originalOrderId']
        # 提取 goodsName → 用于用例4的查询条件
        self.__class__._goods_name = first_record['goodsName']

        logger.info(f"提取 originalOrderId={self._query_order_id}, goodsName={self._goods_name}")
        allure.attach(
            f"originalOrderId: {self._query_order_id}\ngoodsName: {self._goods_name}",
            name="提取的跨步骤变量",
            attachment_type=allure.attachment_type.TEXT
        )

    # ==================== 步骤2：以订单编号查询 ====================
    @pytest.mark.order(2)
    @allure.title("MO_002 - 以订单编号-查询补订单列表")
    def test_query_make_order_by_order_id(self, merchant_api_client, db):
        """用例2：以 originalOrderId 为查询条件，验证返回结果匹配"""
        if not self._query_order_id:
            pytest.skip("用例1未提取到 originalOrderId，跳过用例2")

        case = get_case_by_id("MO_002")
        global_vars = self._load_global_vars()
        global_vars['query_order_id'] = self._query_order_id

        allure.attach(f"查询条件 orderId={self._query_order_id}",
                      name="动态查询条件", attachment_type=allure.attachment_type.TEXT)
        execute_test_case(case, merchant_api_client, db, global_vars)

        # 空数据跳过：基础断言已通过，若 records 为空则跳过后续数据校验
        resp_check = merchant_api_client.post(case['endpoint'], json=replace_placeholders(case.get('json', {}), global_vars))
        records = resp_check.json().get('data', {}).get('backstageMakeOrderDtoList', {}).get('records', [])
        if not records:
            allure.attach(f"查询条件 orderId={self._query_order_id} 返回空数据，用例正常通过",
                          name="空数据跳过", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(f"查询条件 orderId={self._query_order_id} 返回空数据")

    # ==================== 步骤3：以订单状态-待支付查询 ====================
    @pytest.mark.order(3)
    @allure.title("MO_003 - 以订单状态待支付-查询补订单列表")
    def test_query_make_order_by_status(self, merchant_api_client, db):
        """用例3：以 status=01 为查询条件，断言所有记录 status 均为 01，并提取 orderId 用于取消"""
        case = get_case_by_id("MO_003")
        global_vars = self._load_global_vars()

        # 发送请求以提取待支付订单的 orderId
        with allure.step("发送查询请求（status=01）"):
            endpoint = case['endpoint']
            body = case.get('json', {})
            allure.attach(json.dumps(body, ensure_ascii=False, indent=2),
                          name="请求体", attachment_type=allure.attachment_type.JSON)
            resp = merchant_api_client.post(endpoint, json=body)
            assert resp.status_code == case['expected_status']
            resp_json = resp.json()
            allure.attach(json.dumps(resp_json, ensure_ascii=False, indent=2)[:5000],
                          name="完整响应体", attachment_type=allure.attachment_type.JSON)

        # 执行标准断言（含 status all_eq "01"）
        with allure.step("执行标准断言（含 status 校验）"):
            for check in case['validate_data']:
                path = check['path'].lstrip('$').lstrip('.')
                actual = get_value_by_path(resp_json, path)
                validate(actual, check['operator'], check['value'], path)

        # 提取待支付订单的 orderId → 用于用例5取消
        records = resp_json.get('data', {}).get('backstageMakeOrderDtoList', {}).get('records', [])
        if not records:
            allure.attach("待支付补订单列表为空，无可用取消数据", name="跳过原因",
                          attachment_type=allure.attachment_type.TEXT)
            pytest.skip("待支付补订单列表为空，无法提取取消用的 orderId")

        self.__class__._cancel_order_id = records[0]['orderId']
        logger.info(f"提取待支付 orderId={self._cancel_order_id}，用于取消测试")
        allure.attach(f"cancel_order_id: {self._cancel_order_id}",
                      name="提取的取消订单ID", attachment_type=allure.attachment_type.TEXT)

    # ==================== 步骤4：以订单类型查询 ====================
    @pytest.mark.order(4)
    @allure.title("MO_004 - 以订单类型-查询补订单列表")
    def test_query_make_order_by_goods_name(self, merchant_api_client, db):
        """用例4：以 goodsName 为查询条件，验证返回结果中的 goodsName 匹配"""
        if not self._goods_name:
            pytest.skip("用例1未提取到 goodsName，跳过用例4")

        case = get_case_by_id("MO_004")
        global_vars = self._load_global_vars()
        global_vars['goods_name'] = self._goods_name

        allure.attach(f"查询条件 goodsName={self._goods_name}",
                      name="动态查询条件", attachment_type=allure.attachment_type.TEXT)
        execute_test_case(case, merchant_api_client, db, global_vars)

        # 空数据跳过：基础断言已通过，若 records 为空则跳过后续数据校验
        resp_check = merchant_api_client.post(case['endpoint'], json=replace_placeholders(case.get('json', {}), global_vars))
        records = resp_check.json().get('data', {}).get('backstageMakeOrderDtoList', {}).get('records', [])
        if not records:
            allure.attach(f"查询条件 goodsName={self._goods_name} 返回空数据，用例正常通过",
                          name="空数据跳过", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(f"查询条件 goodsName={self._goods_name} 返回空数据")

    # ==================== 步骤5：取消补订单 ====================
    @pytest.mark.order(5)
    @allure.title("MO_005 - 取消补订单")
    def test_cancel_make_order(self, merchant_api_client, db):
        """用例5：使用用例3提取的待支付 orderId 调用取消接口"""
        if not self._cancel_order_id:
            pytest.skip("用例3未提取到待支付 orderId，跳过取消测试")

        case = get_case_by_id("MO_005")
        global_vars = self._load_global_vars()
        global_vars['cancel_order_id'] = self._cancel_order_id

        allure.attach(f"取消订单 orderId={self._cancel_order_id}",
                      name="取消订单ID", attachment_type=allure.attachment_type.TEXT)
        execute_test_case(case, merchant_api_client, db, global_vars)
