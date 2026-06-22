# testcases/merchant/api/order/test_picc_insurance_order_api.py
"""
投保订单查询接口测试模块
接口: POST /hzsx/ope/picc/queryLogPage
用例说明:
  - PICC_001: 无条件查询，遍历所有分页，累计保费金额和投保金额并与汇总字段比对
  - PICC_002: 以订单号为查询条件
  - PICC_003~004: 以险种为查询条件（人保/天安财险）
  - PICC_005~007: 以保单状态为查询条件（投保中/已投保/已取消）
  - PICC_008~010: 以扣款状态为查询条件（扣款成功/扣款失败/已退款）
  - PICC_011: 投保状态+扣款状态+险种组合查询
"""
import math
from decimal import Decimal

import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables

# 预加载 YAML 数据
_DATA_FILE = "data/merchant/api/order/picc_insurance_order_api.yaml"
_ALL_CASES = get_test_data(_DATA_FILE, "picc_query_tests")


@allure.epic("商家端")
@allure.feature("商家端-投保订单")
@allure.story("投保订单查询")
class TestPiccInsuranceOrder:
    """投保订单查询接口测试类"""

    _global_vars = None
    _captured_order_id = None  # 由 PICC_001 捕获，供 PICC_002 使用
    _ENDPOINT = "/hzsx/ope/picc/queryLogPage"
    _PAGE_SIZE = 100

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("picc_insurance_order_api.yaml")
        return cls._global_vars.copy()

    # ==================== 用例1: 无条件查询（分页累计金额校验） ====================
    @allure.title("PICC_001 - 无条件查询-分页遍历累计保费与投保金额校验")
    def test_unconditional_query_amount_sum(self, api_client, db):
        """
        无条件查询投保订单:
        1. 第一页获取 total，计算总页数
        2. 遍历所有分页，累计每条记录的 premiunAmt 和 insuranceAmt
        3. 断言累计保费金额 == premiunAmtCount
        4. 断言累计投保金额 == insuranceAmtCount
        使用 Decimal 保证金额精度
        """
        global_vars = self._load_global_vars()

        # ---------- 第1页请求 ----------
        with allure.step("第1页: 获取 total 并计算总页数"):
            body = {"pageNumber": 1, "pageSize": self._PAGE_SIZE}
            allure.attach(str(body), name="请求参数(第1页)", attachment_type=allure.attachment_type.JSON)
            resp = api_client.post(self._ENDPOINT, json=body)
            assert resp.status_code == 200, f"HTTP 状态码异常: {resp.status_code}"

            first_page = resp.json()
            allure.attach(
                str(first_page)[:3000], name="第1页响应体", attachment_type=allure.attachment_type.JSON
            )

            assert first_page.get("businessSuccess") is True, (
                f"接口业务失败: {first_page.get('errorMessage')}"
            )

            data = first_page.get("data", {})
            expected_premium_count = data.get("premiunAmtCount", "0")
            expected_insurance_count = data.get("insuranceAmtCount", "0")
            page_data = data.get("piccInsurenceLogDtoList", {})
            total = page_data.get("total", 0)
            records = page_data.get("records", [])

            allure.attach(
                f"total={total}\npremiunAmtCount={expected_premium_count}\n"
                f"insuranceAmtCount={expected_insurance_count}",
                name="汇总统计字段",
                attachment_type=allure.attachment_type.TEXT,
            )

            if total == 0:
                pytest.skip("投保订单数据为空，跳过累计校验")

            # 捕获第一条记录的 orderId，供 PICC_002 使用
            if records:
                self.__class__._captured_order_id = records[0]["orderId"]
                allure.attach(
                    f"捕获 orderId = {self._captured_order_id}",
                    name="PICC_001 捕获的订单号(供 PICC_002 使用)",
                    attachment_type=allure.attachment_type.TEXT,
                )

            total_pages = math.ceil(total / self._PAGE_SIZE)

        # ---------- 累计第1页金额 ----------
        sum_premium = Decimal("0")
        sum_insurance = Decimal("0")

        with allure.step(f"第1页: 累计 {len(records)} 条记录的保费和投保金额"):
            for r in records:
                sum_premium += Decimal(str(r.get("premiunAmt", 0)))
                sum_insurance += Decimal(str(r.get("insuranceAmt", 0)))

        # ---------- 遍历后续分页 ----------
        for page in range(2, total_pages + 1):
            with allure.step(f"第{page}/{total_pages}页: 请求并累计金额"):
                body = {"pageNumber": page, "pageSize": self._PAGE_SIZE}
                resp = api_client.post(self._ENDPOINT, json=body)
                assert resp.status_code == 200, f"第{page}页 HTTP 状态码异常: {resp.status_code}"

                page_json = resp.json()
                page_records = (
                    page_json.get("data", {})
                    .get("piccInsurenceLogDtoList", {})
                    .get("records", [])
                )

                allure.attach(
                    f"第{page}页记录数: {len(page_records)}",
                    name=f"第{page}页统计",
                    attachment_type=allure.attachment_type.TEXT,
                )

                for r in page_records:
                    sum_premium += Decimal(str(r.get("premiunAmt", 0)))
                    sum_insurance += Decimal(str(r.get("insuranceAmt", 0)))

        # ---------- 断言 ----------
        expected_premium = Decimal(str(expected_premium_count))
        expected_insurance = Decimal(str(expected_insurance_count))
        print(f"累计保费金额: {sum_premium}, 接口汇总保费金额: {expected_premium}")
        print(f"累计投保金额: {sum_insurance}, 接口汇总投保金额: {expected_insurance}")
        with allure.step(
            f"断言: 累计保费({sum_premium}) == 接口汇总({expected_premium})"
        ):
            allure.attach(
                f"累计保费金额: {sum_premium}\n接口 premiunAmtCount: {expected_premium}\n"
                f"差值: {abs(sum_premium - expected_premium)}",
                name="保费金额比对",
                attachment_type=allure.attachment_type.TEXT,
            )
            assert sum_premium == expected_premium, (
                f"保费金额不一致: 累计={sum_premium}, 接口汇总={expected_premium}, "
                f"差值={abs(sum_premium - expected_premium)}"
            )

        with allure.step(
            f"断言: 累计投保金额({sum_insurance}) == 接口汇总({expected_insurance})"
        ):
            allure.attach(
                f"累计投保金额: {sum_insurance}\n接口 insuranceAmtCount: {expected_insurance}\n"
                f"差值: {abs(sum_insurance - expected_insurance)}",
                name="投保金额比对",
                attachment_type=allure.attachment_type.TEXT,
            )
            assert sum_insurance == expected_insurance, (
                f"投保金额不一致: 累计={sum_insurance}, 接口汇总={expected_insurance}, "
                f"差值={abs(sum_insurance - expected_insurance)}"
            )

        logger.info(
            f"无条件查询金额校验通过: 保费={sum_premium}, 投保金额={sum_insurance}, "
            f"共遍历 {total_pages} 页, {total} 条记录"
        )

    # ==================== 用例2~11: 参数化条件查询 ====================
    @pytest.mark.parametrize("case", _ALL_CASES, ids=[c["case_id"] for c in _ALL_CASES])
    def test_picc_query_by_condition(self, api_client, db, case):
        """参数化条件查询: 订单号/险种/保单状态/扣款状态/组合条件"""
        global_vars = self._load_global_vars()
        if "variables" in case and isinstance(case["variables"], dict):
            global_vars.update(case["variables"])

        # PICC_002 特殊处理：优先使用 PICC_001 捕获的 orderId，否则自行前置查询
        if case["case_id"] == "PICC_002":
            order_id = self._captured_order_id
            if not order_id:
                with allure.step("前置: 无条件查询获取第一条记录的 orderId（PICC_001 未执行）"):
                    resp = api_client.post(self._ENDPOINT, json={"pageNumber": 1, "pageSize": 10})
                    assert resp.status_code == 200, f"前置查询 HTTP 状态码异常: {resp.status_code}"
                    resp_json = resp.json()
                    records = (
                        resp_json.get("data", {})
                        .get("piccInsurenceLogDtoList", {})
                        .get("records", [])
                    )
                    if not records:
                        pytest.skip("无条件查询无数据，无法获取 orderId")
                    order_id = records[0]["orderId"]
            global_vars["order_id"] = order_id
            allure.attach(f"order_id = {order_id}", name="PICC_002 使用的订单号", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"PICC_002 使用 orderId={order_id}")

        execute_test_case(case, api_client, db, global_vars)
        logger.info(f" [{case['case_id']}] {case['title']} —— 执行完成")
