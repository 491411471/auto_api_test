# testcases/merchant/api/order/test_overdue_order_api.py
"""
逾期订单接口测试
接口：/hzsx/ope/order/getTotalBadDebtAmount
方法：POST

测试场景：
1. 无条件查询全部逾期订单，提取关键字段并计算坏账总额
2. 按订单号查询指定逾期订单
3. 查询全部坏账金额（unconditional=true）
"""
import allure
import json
import pytest
from decimal import Decimal
from common.logger import logger
from common.test_helpers import replace_placeholders, validate_response
from utils.data_loader import get_test_data, get_global_variables


# 预先加载所有用例数据（只加载一次）
_DATA_FILE = "data/merchant/api/order/overdue_order_api.yaml"
_ALL_CASES = get_test_data(_DATA_FILE, "overdue_order_tests")
if not _ALL_CASES:
    raise RuntimeError(f"无法加载 YAML 数据，请检查文件路径 {_DATA_FILE}")


def get_case_by_id(case_id: str):
    for case in _ALL_CASES:
        if case['case_id'] == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")


@allure.epic("商家端")
@allure.feature("商家端-逾期订单")
@allure.story("逾期订单查询")
class TestOverdueOrderApi:
    """逾期订单接口测试"""
    _global_vars = None
    # 跨用例共享：坏账总额（BD_001 产出，BD_004 可选交叉验证）
    _total_bad_debt = None
    _extracted_records = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    def _fetch_overdue_order(self, merchant_api_client):
        """
        独立获取一个逾期订单（不依赖 BD_001）。
        优先复用 BD_001 已提取的数据；否则直接调用 API 获取。
        返回 (record, request_json_used) 或 (None, None)。
        """
        # 优先复用 BD_001 已提取的数据
        if TestOverdueOrderApi._extracted_records:
            return TestOverdueOrderApi._extracted_records[0]

        # 独立调用 API 获取
        req_payload = {"pageNumber": 1, "pageSize": 1, "version": 1}
        try:
            resp = merchant_api_client.post(
                "/hzsx/business/order/queryOverDueOrdersByCondition", json=req_payload
            )
            records = (resp.json().get('data') or {}).get('records') or []
            if records:
                logger.info(f"独立获取逾期订单成功: orderId={records[0].get('orderId')}")
                return records[0]
        except Exception as e:
            logger.warning(f"独立获取逾期订单失败: {e}")
        return None

    # ==================== 场景一：无条件查询全部逾期订单 ====================
    @allure.title("BD_001 - 无条件查询全部逾期订单")
    def test_bd_001_query_all_overdue_orders(self, merchant_api_client, db):
        """不传查询条件，获取全部逾期订单列表，提取关键字段并计算坏账总额"""
        case = get_case_by_id("BD_001")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])

        # 构建请求参数
        request_json = replace_placeholders(case['json'], global_vars)

        with allure.step("调用逾期订单查询接口（无条件）"):
            resp = merchant_api_client.post(case['endpoint'], json=request_json)
            assert resp.status_code == case['expected_status'], f"HTTP 状态码不符: 期望 {case['expected_status']}, 实际 {resp.status_code}"
            resp_json = resp.json()
        allure.attach(json.dumps(resp_json, indent=2, ensure_ascii=False)[:3000], name="接口响应", attachment_type=allure.attachment_type.JSON)

        # ===== 核心断言：responseType / errorMessage / data =====
        with allure.step("验证响应基础字段"):
            assert resp_json.get('responseType') == 'SUCCESS', f"responseType 应为 SUCCESS，实际: {resp_json.get('responseType')}"
            assert resp_json.get('errorMessage') is None, f"errorMessage 应为 None，实际: {resp_json.get('errorMessage')}"
            assert resp_json.get('data') is not None, "data 不应为 None"

        # ===== 提取 records =====
        records = resp_json.get('data', {}).get('records', [])
        total = resp_json.get('data', {}).get('total', 0)

        if not records:
            skip_msg = f"未查询到逾期订单记录（total={total}），跳过关键字段提取"
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            logger.warning(skip_msg)
            pytest.skip(skip_msg)

        # ===== 保存 records 供后续用例使用 =====
        TestOverdueOrderApi._extracted_records = records

        # ===== 提取关键字段 =====
        extract_fields = case.get('extract_fields', [])
        extracted_data = []
        for record in records:
            row = {}
            for field in extract_fields:
                row[field] = record.get(field)
            extracted_data.append(row)

        allure.attach(json.dumps(extracted_data, indent=2, ensure_ascii=False),
                      name="提取的关键字段", attachment_type=allure.attachment_type.JSON)

        # ===== 计算全部逾期坏账总金额 =====
        total_bad_debt = sum(float(record.get('badDebtReserves', 0) or 0) for record in records)
        TestOverdueOrderApi._total_bad_debt = total_bad_debt

        allure.attach(
            f"逾期订单总数: {total}\n"
            f"坏账总金额: {total_bad_debt}\n"
            f"提取字段: {', '.join(extract_fields)}",
            name="统计汇总", attachment_type=allure.attachment_type.TEXT
        )
        logger.info(f"逾期订单查询完成: total={total}, 坏账总额={total_bad_debt}")

    # ==================== 场景二：按订单号查询逾期订单 ====================
    @allure.title("BD_002 - 按订单号查询逾期订单")
    def test_bd_002_query_overdue_by_order_id(self, merchant_api_client, db):
        """传入orderId查询指定逾期订单，验证返回数据关键字段"""
        case = get_case_by_id("BD_002")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])

        # 独立获取逾期订单（不依赖 BD_001）
        record = self._fetch_overdue_order(merchant_api_client)
        if not record:
            skip_msg = "未获取到逾期订单，跳过按订单号查询"
            allure.attach(
                f"{skip_msg}\n\n查询参数: {{'pageNumber': 1, 'pageSize': 1, 'version': 1}}\n"
                f"接口: /hzsx/business/order/queryOverDueOrdersByCondition",
                name="跳过原因",
                attachment_type=allure.attachment_type.TEXT
            )
            pytest.skip(skip_msg)
        global_vars['test_order_id'] = record.get('orderId')
        logger.info(f"BD_002 使用 orderId: {global_vars['test_order_id']}")

        # 构建请求参数
        request_json = replace_placeholders(case['json'], global_vars)

        with allure.step(f"按订单号查询逾期订单: {request_json.get('orderId')}"):
            resp = merchant_api_client.post(case['endpoint'], json=request_json)
            assert resp.status_code == case['expected_status'], f"HTTP 状态码不符: 期望 {case['expected_status']}, 实际 {resp.status_code}"
            resp_json = resp.json()
        allure.attach(json.dumps(resp_json, indent=2, ensure_ascii=False)[:3000], name="接口响应", attachment_type=allure.attachment_type.JSON)

        # ===== 核心断言：responseType / errorMessage / data =====
        with allure.step("验证响应基础字段"):
            assert resp_json.get('responseType') == 'SUCCESS', \
                f"responseType 应为 SUCCESS，实际: {resp_json.get('responseType')}"
            assert resp_json.get('errorMessage') is None, \
                f"errorMessage 应为 None，实际: {resp_json.get('errorMessage')}"
            assert resp_json.get('data') is not None, "data 不应为 None"

        records = resp_json.get('data', {}).get('records', [])

        if not records:
            skip_msg = f"订单号 {request_json.get('orderId')} 未查询到逾期记录，跳过"
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            logger.warning(skip_msg)
            pytest.skip(skip_msg)

        # ===== 提取并验证关键字段 =====
        extract_fields = case.get('extract_fields', [])
        record = records[0]
        extracted = {field: record.get(field) for field in extract_fields}

        allure.attach(json.dumps(extracted, indent=2, ensure_ascii=False), name="提取的关键字段", attachment_type=allure.attachment_type.JSON)

        # 验证核心字段不为空
        with allure.step("验证关键字段非空"):
            assert extracted.get('orderId') is not None, f"orderId 不应为 None，实际: {extracted.get('orderId')}"
            assert extracted.get('overdueDays') is not None, f"overdueDays 不应为 None，实际: {extracted.get('overdueDays')}"
            assert extracted.get('badDebt') is not None, f"badDebt 不应为 None，实际: {extracted.get('badDebt')}"
            assert extracted.get('badDebtReserves') is not None, f"badDebtReserves 不应为 None，实际: {extracted.get('badDebtReserves')}"

        logger.info(f"按订单号查询完成: orderId={extracted.get('orderId')}, "
                     f"逾期天数={extracted.get('overdueDays')}, 坏账={extracted.get('badDebt')}")

        # ==================== 场景三：按下单人姓名查询逾期订单 ====================

    @allure.title("BD_003 - 按下单人查询逾期订单")
    def test_bd_003_query_overdue_by_user_name(self, merchant_api_client, db):
        """传入下单人查询指定逾期订单，验证返回数据关键字段"""
        case = get_case_by_id("BD_003")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])

        # 独立获取逾期订单（不依赖 BD_001）
        record = self._fetch_overdue_order(merchant_api_client)
        if not record:
            skip_msg = "未获取到逾期订单，跳过按下单人查询"
            allure.attach(
                f"{skip_msg}\n\n查询参数: {{'pageNumber': 1, 'pageSize': 1, 'version': 1}}\n"
                f"接口: /hzsx/business/order/queryOverDueOrdersByCondition",
                name="跳过原因",
                attachment_type=allure.attachment_type.TEXT
            )
            pytest.skip(skip_msg)
        global_vars['user_name'] = record.get('realName')
        logger.info(f"BD_003 使用 userName: {global_vars['user_name']}")

        # 构建请求参数
        request_json = replace_placeholders(case['json'], global_vars)
        with allure.step(f"按下单人姓名查询逾期订单: {request_json.get('userName')}"):
            resp = merchant_api_client.post(case['endpoint'], json=request_json)
            assert resp.status_code == case['expected_status'], f"HTTP 状态码不符: 期望 {case['expected_status']}, 实际 {resp.status_code}"
            resp_json = resp.json()
        allure.attach(json.dumps(resp_json, indent=2, ensure_ascii=False)[:3000], name="接口响应", attachment_type=allure.attachment_type.JSON)

        # ===== 核心断言：responseType / errorMessage / data =====
        with allure.step("验证响应基础字段"):
            assert resp_json.get('responseType') == 'SUCCESS', \
                f"responseType 应为 SUCCESS，实际: {resp_json.get('responseType')}"
            assert resp_json.get('errorMessage') is None, \
                f"errorMessage 应为 None，实际: {resp_json.get('errorMessage')}"
            assert resp_json.get('data') is not None, "data 不应为 None"

        records = resp_json.get('data', {}).get('records', [])

        if not records:
            skip_msg = f"下单人姓名 {request_json.get('userName')} 未查询到逾期记录，跳过"
            allure.attach(
                f"{skip_msg}\n\n请求参数: {json.dumps(request_json, ensure_ascii=False)}\n"
                f"接口: {case.get('endpoint')}",
                name="跳过原因",
                attachment_type=allure.attachment_type.TEXT
            )
            logger.warning(skip_msg)
            pytest.skip(skip_msg)

        # ===== 提取并验证关键字段 =====
        extract_fields = case.get('extract_fields', [])
        record = records[0]
        extracted = {field: record.get(field) for field in extract_fields}

        allure.attach(json.dumps(extracted, indent=2, ensure_ascii=False), name="提取的关键字段",
                      attachment_type=allure.attachment_type.JSON)

        # 验证核心字段不为空
        with allure.step("验证关键字段非空"):
            assert extracted.get('realName') is not None, f"realName 不应为 None，实际: {extracted.get('realName')}"
            assert extracted.get('orderId') is not None, f"orderId 不应为 None"

        logger.info(f"按下单人姓名查询完成: userName={extracted.get('userName')}, "
                    f"逾期天数={extracted.get('overdueDays')}, 坏账={extracted.get('badDebt')}")

    # ==================== 场景四：查询全部坏账金额 ====================
    @allure.title("BD_004 - 查询全部坏账金额")
    def test_bd_003_total_bad_debt_amount(self, merchant_api_client, db):
        """unconditional=true查询全部坏账总金额，data直接返回数值"""
        case = get_case_by_id("BD_004")
        global_vars = self._load_global_vars()
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])

        # 构建请求参数
        request_json = replace_placeholders(case['json'], global_vars)

        with allure.step("调用全部坏账金额接口（unconditional=true）"):
            resp = merchant_api_client.post(case['endpoint'], json=request_json)
            assert resp.status_code == case['expected_status'], f"HTTP 状态码不符: 期望 {case['expected_status']}, 实际 {resp.status_code}"
            resp_json = resp.json()
        allure.attach(json.dumps(resp_json, indent=2, ensure_ascii=False), name="接口响应", attachment_type=allure.attachment_type.JSON)

        # ===== 核心断言：responseType / errorMessage / data =====
        with allure.step("验证响应基础字段"):
            assert resp_json.get('responseType') == 'SUCCESS', f"responseType 应为 SUCCESS，实际: {resp_json.get('responseType')}"
            assert resp_json.get('errorMessage') is None, f"errorMessage 应为 None，实际: {resp_json.get('errorMessage')}"
            assert resp_json.get('data') is not None, "data（坏账总金额）不应为 None"

        # ===== 验证 data 为数值类型 =====
        bad_debt_amount = resp_json.get('data')
        with allure.step(f"验证坏账金额 data={bad_debt_amount}（数值类型）"):
            assert bad_debt_amount is not None, "坏账金额不应为 None"
            assert isinstance(bad_debt_amount, (int, float)), f"坏账金额应为数值类型，实际: {type(bad_debt_amount)}"
            assert bad_debt_amount >= 0, f"坏账金额不应为负数，实际: {bad_debt_amount}"

        # ===== 与 BD_001 的计算结果交叉验证（仅当 BD_001 已执行时）=====
        if TestOverdueOrderApi._total_bad_debt is not None:
            with allure.step(f"交叉验证：接口总额({bad_debt_amount}) vs 场景一累加({TestOverdueOrderApi._total_bad_debt})"):
                assert float(bad_debt_amount) == pytest.approx(float(TestOverdueOrderApi._total_bad_debt), abs=1e-2), \
                    f"接口返回坏账总额({bad_debt_amount})与场景一计算总额({TestOverdueOrderApi._total_bad_debt})不一致"
            allure.attach(
                f"接口返回坏账总额: {bad_debt_amount}\n"
                f"场景一计算坏账总额: {TestOverdueOrderApi._total_bad_debt}",
                name="坏账金额交叉验证", attachment_type=allure.attachment_type.TEXT
            )
        else:
            allure.attach(
                "BD_001 未执行或未产出数据，跳过交叉验证\n"
                f"本次接口返回坏账金额: {bad_debt_amount}",
                name="交叉验证说明", attachment_type=allure.attachment_type.TEXT
            )

        logger.info(f"全部逾期坏账金额查询完成: data={bad_debt_amount}")
