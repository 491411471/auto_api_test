import allure
import pytest
import random
import string
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables

# 预先加载所有用例数据（只加载一次）
_DATA_FILE = "data/merchant/api/order/order_operator_api.yaml"
_ALL_CASES = get_test_data(_DATA_FILE, "order_operator_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 order_operator_api.yaml")

def get_case_by_id(case_id: str):
    for case in _ALL_CASES:
        if case['case_id'] == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")
@allure.epic("商家端")
@allure.feature("商家端-订单模块")
@allure.story("订单其他操作")
class TestOrderOperatorApi:
    _global_vars = None
    # 用于跨用例共享的数据
    shared_order_id = None
    shared_remark = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("order_operator_api.yaml")
        return cls._global_vars.copy()

    def test_bh_001(self, api_client, db):
        case = get_case_by_id("BH_001")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_bh_002(self, api_client, db):
        case = get_case_by_id("BH_002")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)

    def test_bh_003(self, api_client, db):
        case = get_case_by_id("BH_003")
        global_vars = self._load_global_vars()
        random_remark = ''.join(random.choices(string.ascii_letters + string.digits, k=15))
        global_vars['random_remark'] = random_remark
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, api_client, db, global_vars)
        # execute_test_case 执行后，global_vars 中已经有 order_id（从 SQL 查询得到）
        TestOrderOperatorApi.shared_order_id = global_vars.get('order_id')
        TestOrderOperatorApi.shared_remark = global_vars.get('random_remark')
        allure.attach(f"保存的 order_id: {TestOrderOperatorApi.shared_order_id}",
                      name="跨用例传递", attachment_type=allure.attachment_type.TEXT)

    # def test_bh_004(self, api_client, db):
    #     # 如果 BH_003 失败或未执行，跳过验证
    #     if TestOrderOperatorApi.shared_order_id is None:
    #         pytest.skip("BH_003 未执行或失败，跳过验证")
    #     # 手动构造查询请求，这里简单直接调用查询接口，不依赖 YAML
    #     response = api_client.post("/hzsx/business/order/queryOrderByCondition", json={
    #                                 "businessType": 1,
    #                                 "guangGaoId": "",
    #                                 "isQueryHistory": False,
    #                                 "orderId": TestOrderOperatorApi.shared_order_id,
    #                                 "pageNumber": 1,
    #                                 "pageSize": 10,
    #                                 "queryType": "queryPageList",
    #                                 "requestSource": "businessNewOfListHeaderStatus",
    #                                 "status": "06"
    #                             })
    #     data = response.json()
    #     import json
    #     print("验证修改的备注信息：",json.dumps(data, indent=4,ensure_ascii=False))
    #     # 断言备注已被修改
    #     assert data.get("businessSuccess") is True, "查询接口成功"
    #     actual_remark = data.get("data", {}).get("records")[0].get("remarkNew")
    #     expected_remark = TestOrderOperatorApi.shared_remark
    #     assert actual_remark == expected_remark, f"备注不一致：期望 {expected_remark}，实际 {actual_remark}"
    #     allure.attach(f"订单 {TestOrderOperatorApi.shared_order_id} 备注为 {actual_remark}",
    #                   name="验证结果", attachment_type=allure.attachment_type.TEXT)

if __name__ == '__main__':
    pytest.main()