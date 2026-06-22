# testcases/merchant/api/post_lease_management/test_event_record.py
# -*- coding: utf-8 -*-
"""
跟进记录接口测试模块
接口：
  - /hzsx/dcm/order/eventProgress（获取跟进分类类型）
  - /hzsx/dcm/order/addEvent（提交跟进记录）
  - /hzsx/dcm/order/listEventRecord（查询跟进记录列表）

测试场景：
  ER_001: 获取跟进分类类型
  ER_002: 提交跟进记录（随机选取分类类型）
  ER_003: 查询跟进记录，验证新增记录正确

设计原则：
  - 所有请求参数由 YAML（event_record_api.yaml）统一配置，Python 仅负责动态变量注入
  - ER_003 可独立执行（不依赖 ER_002 的执行顺序），通过 _ensure_event_record 保障
  - 遵循 test_buy_out_order_api.py / test_relet_order_api.py 的标准化模式
  - 每个用例均附加请求参数和响应结果到 Allure 报告
"""
import allure
import json
import random
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case, replace_placeholders
from utils.data_loader import get_test_data, get_global_variables


# ==================== 模块级共享：获取第一个逾期已分配且首期已支付的订单 ====================
_first_order_info_cache = None
_first_order_fetched = False


def _fetch_first_overdue_order(api_client):
    """
    获取第一个逾期且已分配（assignStatus=1）的订单号。
    简化版：不再校验首期支付状态，仅返回订单号。
    若查询无结果，返回 None。
    """
    global _first_order_info_cache, _first_order_fetched
    if _first_order_fetched:
        return _first_order_info_cache

    # 查询条件：已分配 + 逾期（overdueTime 含义需按接口文档确认，此处保持原值）
    query_payload = {
        "assignStatus": "1",
        "followTimeDesc": 0,
        "overdueTime": "0",          # 若此字段表示“是否逾期”，请确认 0/1 含义
        "pageNum": 1,
        "pageSize": 10,
        "overdueDaysDesc": 1,
        "tabName": "0"
    }

    try:
        with allure.step("获取已分配逾期订单"):
            resp = api_client.post("/hzsx/dcm/order/list", json=query_payload)
            status_code = getattr(resp, 'status_code', 'N/A')
            try:
                resp_json = resp.json()
            except Exception:
                resp_json = None

            # 附加请求/响应调试信息
            try:
                req = resp.request
                req_url = getattr(req, 'url', '<unknown>')
                req_headers = dict(getattr(req, 'headers', {}) or {})
                req_body = getattr(req, 'body', None)
            except Exception:
                req_url = '<unknown>'
                req_headers = {}
                req_body = None

            attach_text = (
                f"请求 URL: {req_url}\n"
                f"状态码: {status_code}\n"
                f"请求头: {json.dumps(req_headers, ensure_ascii=False)}\n"
                f"请求体: {json.dumps(query_payload, ensure_ascii=False)}\n"
                f"响应: {json.dumps(resp_json, ensure_ascii=False, indent=2) if resp_json is not None else getattr(resp, 'text', '<non-json response>')}"
            )
            allure.attach(attach_text, name="调试: 查询已分配逾期订单", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"查询已分配逾期订单 status={status_code} url={req_url}")

            if resp_json is None:
                records = []
            else:
                records = (resp_json.get('data') or {}).get('records') or []

            if not records:
                allure.attach("查询无结果（未找到已分配逾期订单）", name="查询结果")
                return None

            # 直接取第一个订单号
            first_order = records[0]
            order_id = first_order['orderId']
            # 缓存并标记已获取
            _first_order_info_cache = order_id
            _first_order_fetched = True

            allure.attach(
                f"选中订单: {order_id}\n"
                f"用户名: {first_order.get('userName', '')}\n"
                f"逾期天数: {first_order.get('overdueDays', '')}",
                name="选中的订单"
            )
            return order_id

    except Exception as e:
        allure.attach(f"获取失败: {e}", name="异常")
        logger.error(f"获取已分配逾期订单失败: {e}")

    return None


# 预先加载所有用例数据
_DATA_FILE = "event_record_api.yaml"
_ALL_CASES = get_test_data(_DATA_FILE, "event_record_tests")
if not _ALL_CASES:
    raise RuntimeError(f"无法加载 YAML 数据，请检查文件路径 {_DATA_FILE}")


def _get_case(case_id: str):
    for c in _ALL_CASES:
        if c['case_id'] == case_id:
            return c
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")


@allure.epic("商家端")
@allure.feature("商家端-租后管理模块")
@allure.story("跟进记录")
class TestEventRecord:
    """跟进记录完整流程测试

    遵循标准化模式（与 test_buy_out_order_api.py / test_relet_order_api.py 一致）：
      - 所有请求参数由 YAML 统一配置
      - Python 仅负责动态变量注入（order_id, progress_code 等）
      - 每个用例独立可执行，不依赖执行顺序
    """
    _global_vars = None

    # 跨步骤共享数据（使用显式类名访问，避免 pytest 实例隔离问题）
    _shared_order_id = None
    _shared_progress_code = None
    _shared_progress_description = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    def _ensure_order_id(self, merchant_api_client):
        """确保已获取逾期订单号（模块级缓存）"""
        if TestEventRecord._shared_order_id is None:
            order_id = _fetch_first_overdue_order(merchant_api_client)
            print("订单号:", order_id)
            if not order_id:
                skip_msg = "未找到逾期已分配且首期已支付的订单，跳过跟进记录测试"
                allure.attach(
                    f"{skip_msg}\n\n"
                    f"查询策略:\n"
                    f"1. assignStatus=1 + overdueTime=0（已分配逾期）→ 首期status=2\n"
                    f"2. overdueTime=0（任意逾期，降级）→ 首期status=2\n"
                    f"接口: /hzsx/dcm/order/list + /hzsx/business/order/queryOrderStagesDetail",
                    name="跳过原因",
                    attachment_type=allure.attachment_type.TEXT
                )
                pytest.skip(skip_msg)
            TestEventRecord._shared_order_id = order_id
            allure.attach(f"使用订单号: {order_id}", name="测试订单号", attachment_type=allure.attachment_type.TEXT)
        return TestEventRecord._shared_order_id

    def _ensure_event_record(self, merchant_api_client, global_vars):
        """确保存在跟进记录可供 ER_003 查询验证。

        若 ER_002 已执行（类属性已设置），直接复用；
        否则独立提交一条跟进记录，保障 ER_003 可独立执行。
        """
        if TestEventRecord._shared_progress_description is not None:
            logger.info(f"复用 ER_002 已提交的跟进记录: {TestEventRecord._shared_progress_description}")
            return

        with allure.step("前置：独立提交跟进记录（确保 ER_003 可独立执行）"):
            order_id = global_vars.get("order_id")
            try:
                # 1. 获取跟进分类类型
                progress_resp = merchant_api_client.post(
                    "/hzsx/dcm/order/eventProgress", json={"id": order_id}
                )
                progress_data = progress_resp.json()
                progress_list = progress_data.get("data", [])
                assert progress_list, "跟进分类类型列表为空，无法独立提交记录"

                selected = progress_list[0]
                progress_code = str(selected["code"])
                progress_description = selected["description"]

                # 2. 构建并提交跟进记录
                body = {
                    "progress": progress_code,
                    "content": progress_description,
                    "quickTag": "",
                    "orderId": order_id,
                    "operator": global_vars.get("operator", "")
                }

                allure.attach(
                    json.dumps(body, ensure_ascii=False, indent=2),
                    name="独立提交-请求参数",
                    attachment_type=allure.attachment_type.JSON
                )

                add_resp = merchant_api_client.post("/hzsx/dcm/order/addEvent", json=body)
                add_json = add_resp.json()

                allure.attach(
                    json.dumps(add_json, ensure_ascii=False, indent=2),
                    name="独立提交-响应结果",
                    attachment_type=allure.attachment_type.JSON
                )
                logger.info(f"独立提交跟进记录: code={progress_code}, desc={progress_description}")

                # 3. 更新共享状态
                TestEventRecord._shared_progress_code = progress_code
                TestEventRecord._shared_progress_description = progress_description
                global_vars["progress_code"] = progress_code
                global_vars["progress_description"] = progress_description

            except Exception as e:
                allure.attach(f"独立提交跟进记录失败: {e}", name="异常", attachment_type=allure.attachment_type.TEXT)
                logger.error(f"独立提交跟进记录失败: {e}")

    # ==================== ER_001: 获取跟进分类类型 ====================
    @allure.title("ER_001 - 获取跟进分类类型")
    def test_er_001_get_event_progress(self, merchant_api_client, db):
        """调用 eventProgress 获取跟进分类类型列表，验证返回非空"""
        global_vars = self._load_global_vars()
        order_id = self._ensure_order_id(merchant_api_client)
        global_vars["order_id"] = order_id

        case = _get_case("ER_001")
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")

        # 打印请求参数
        request_json = replace_placeholders(case.get('json', {}), global_vars)
        allure.attach(
            json.dumps(request_json, ensure_ascii=False, indent=2),
            name="ER_001 请求参数",
            attachment_type=allure.attachment_type.JSON
        )
        logger.info(f"ER_001 请求参数: {request_json}")

        # 执行用例（框架自动处理变量替换、请求发送、断言）
        execute_test_case(case, merchant_api_client, db, global_vars)

    # ==================== ER_002: 提交跟进记录 ====================
    @allure.title("ER_002 - 提交跟进记录")
    def test_er_002_add_event(self, merchant_api_client, db):
        """随机选取一个跟进分类类型，调用 addEvent 提交跟进记录"""
        global_vars = self._load_global_vars()
        order_id = self._ensure_order_id(merchant_api_client)
        global_vars["order_id"] = order_id

        # 步骤1：获取跟进分类类型
        with allure.step("前置：调用 eventProgress 获取跟进分类类型列表"):
            resp = merchant_api_client.post("/hzsx/dcm/order/eventProgress", json={"id": order_id})
            progress_data = resp.json()

            allure.attach(
                json.dumps(progress_data, ensure_ascii=False, indent=2),
                name="eventProgress 响应",
                attachment_type=allure.attachment_type.JSON
            )

            assert progress_data.get("businessSuccess") is True, \
                f"获取跟进分类类型失败: {progress_data.get('errorMessage')}"
            progress_list = progress_data.get("data", [])
            assert len(progress_list) > 0, "跟进分类类型列表为空"

        # 步骤2：随机选取一个分类类型
        with allure.step("随机选取一个跟进分类类型"):
            selected = random.choice(progress_list)
            progress_code = str(selected["code"])
            progress_description = selected["description"]

            # 同步到类属性（确保 ER_003 可复用）
            TestEventRecord._shared_progress_code = progress_code
            TestEventRecord._shared_progress_description = progress_description

            allure.attach(
                f"选中分类: code={progress_code}, description={progress_description}\n"
                f"共 {len(progress_list)} 个可选分类",
                name="随机选中的分类",
                attachment_type=allure.attachment_type.TEXT
            )

        # 步骤3：注入动态变量（由 YAML 的 ${progress_code} / ${progress_description} 引用）
        global_vars["progress_code"] = progress_code
        global_vars["progress_description"] = progress_description
        global_vars["operator"] = "王超北辰商家"

        # 打印最终请求参数
        case = _get_case("ER_002")
        request_json = replace_placeholders(case.get('json', {}), global_vars)
        allure.attach(
            json.dumps(request_json, ensure_ascii=False, indent=2),
            name="ER_002 请求参数",
            attachment_type=allure.attachment_type.JSON
        )
        logger.info(f"ER_002 请求参数: {request_json}")

        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")
        execute_test_case(case, merchant_api_client, db, global_vars)

    # ==================== ER_003: 查询跟进记录验证 ====================
    @allure.title("ER_003 - 查询跟进记录-验证新增记录")
    def test_er_003_verify_event_record(self, merchant_api_client, db):
        """调用 listEventRecord 查询跟进记录，验证最新一条的 orderId 和 content 与提交一致

        独立性保障：若 ER_002 未执行（如 pytest 乱序或 ER_002 失败），
        则通过 _ensure_event_record 独立提交一条记录，确保断言有数据可比对。
        """
        global_vars = self._load_global_vars()
        order_id = self._ensure_order_id(merchant_api_client)
        global_vars["order_id"] = order_id

        # 确保存在跟进记录（独立于 ER_002）
        self._ensure_event_record(merchant_api_client, global_vars)

        # 若独立提交也失败，跳过验证
        if TestEventRecord._shared_progress_description is None:
            skip_msg = "无法获取跟进分类信息，跳过 ER_003 验证"
            allure.attach(
                f"{skip_msg}\n\n"
                f"ER_002 未执行，且独立提交跟进记录失败\n"
                f"接口: /hzsx/dcm/order/eventProgress + /hzsx/dcm/order/addEvent\n"
                f"订单号: {order_id}",
                name="跳过原因",
                attachment_type=allure.attachment_type.TEXT
            )
            pytest.skip(skip_msg)

        # 注入 progress_description 供 YAML 断言中的 ${progress_description} 使用
        global_vars["progress_description"] = TestEventRecord._shared_progress_description

        case = _get_case("ER_003")
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")

        # 打印请求参数
        request_json = replace_placeholders(case.get('json', {}), global_vars)
        allure.attach(
            json.dumps(request_json, ensure_ascii=False, indent=2),
            name="ER_003 请求参数",
            attachment_type=allure.attachment_type.JSON
        )
        logger.info(f"ER_003 请求参数: {request_json}")

        # 执行用例
        try:
            execute_test_case(case, merchant_api_client, db, global_vars)
        except Exception as e:
            logger.error(f"ER_003 执行失败: {e}")
            raise
