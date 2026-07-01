# testcases/Ali_app/api/test_face_sign_order_real.py
"""
支付宝-小程序 真实创单 + Mock第三方 + 真实回调 接口自动化测试

设计：
  ┌───────────────────────────────────────────────────────────────────────┐
  │  步骤1：真实创单（公司自研接口，被测范围）                                  │
  │    merchant_api_client → /llxz-api-web/hzsx/api/order/userSubmitOrder │
  │    产出：orderId（真实数据，写入数据库）                                  │
  ├───────────────────────────────────────────────────────────────────────┤
  │  步骤2：Mock人脸识别（第三方服务，不可控）                                 │
  │    requests → mock_server:/mock/face/verify                           │
  │    产出：faceToken（Mock生成，携带orderId）                              │
  ├───────────────────────────────────────────────────────────────────────┤
  │  步骤3：Mock支付宝签约（第三方服务，不可控）                               │
  │    requests → mock_server:/mock/alipay/agreement/sign                 │
  │    产出：agreementNo（Mock生成，携带orderId+faceToken）                  │
  ├───────────────────────────────────────────────────────────────────────┤
  │  步骤4：签约成功回调（支付宝网关回调接口，被测范围）                         │
  │    requests → /llxz-components-center/alipay/gateWay (multipart/form-data) │
  │    模拟：支付宝 dispatch.notify 异步通知，完成订单状态流转               │
  └───────────────────────────────────────────────────────────────────────┘

关键设计决策：
  1. 创单和回调网关属于公司自研接口 → 使用真实API
  2. 人脸识别和支付宝签约属于第三方 → 使用本地Mock模拟
  3. 签约回调网关接口 /llxz-components-center/alipay/gateWay 属于被测范围 → 不可Mock
  4. 回调使用 multipart/form-data 格式（模拟支付宝异步通知），rent_dispatch_id 关联真实订单

前置依赖：
  - 真实创单接口 /llxz-api-web/hzsx/api/order/userSubmitOrder 需在测试环境可用
  - 真实回调网关接口 /llxz-components-center/alipay/gateWay 需在测试环境可用
  - Mock服务自动启动（mock_server fixture）
  - merchant_api_client 已认证（session scope，自动登录）

测试用例：
  测试用例1: 真实创单+Mock人脸+Mock签约+签约成功回调全流程
  测试用例2: 创单后-人脸核验失败场景
  测试用例3: 创单后-签约失败场景
  测试用例4: 创单后-回调失败场景（异常处理）
  测试用例5: 金额一致性校验（参数化）
"""
import copy
import json
import random
import time
import uuid
from datetime import datetime, timedelta

import allure
import pytest
import requests

from common.logger import logger
from utils.data_loader import get_test_data, get_global_variables
from testcases.Ali_app.api.mock_server import MockServerManager

_DATA_FILE = "data/Ali_app/api/ali_app_face_sign_order.yaml"


# ==================== 模块级 Mock 服务夹具 ====================
@pytest.fixture(scope="module")
def mock_server():
    """
    模块级 Mock 服务夹具。
    模拟第三方服务（人脸识别、支付宝签约），不影响公司自研接口。

    返回 MockServerManager 实例，提供：
      - base_url: Mock 服务的 base URL
      - last_requests: 最近各接口的请求数据，用于断言验证
      - clear_requests(): 清空请求记录
    """
    manager = MockServerManager()
    manager.start()
    logger.info(f"[Mock] 第三方Mock服务已启动: {manager.base_url}")
    allure.attach(
        f"第三方Mock服务地址: {manager.base_url}\n"
        f"模拟接口: face/verify, alipay/agreement/sign\n"
        f"注意: 创单和回调为公司自研接口，不使用Mock",
        name="Mock服务信息",
        attachment_type=allure.attachment_type.TEXT
    )
    yield manager
    manager.stop()
    logger.info("[Mock] 第三方Mock服务已关闭")


# ==================== 模块级：请求头初始化 ====================
@pytest.fixture(scope="module", autouse=True)
def _setup_channel_header_module(merchant_api_client):
    """模块级别 fixture：初始化支付宝小程序请求头"""
    merchant_api_client.session.headers["channelid"] = "008"
    merchant_api_client.session.headers["Content-Type"] = "application/json"
    logger.info("[Header] 已添加支付宝小程序请求头: channelid=008")


# ==================== 辅助函数 ====================
def _resolve_endpoint(case: dict, mock_base_url: str) -> str:
    """将 YAML 中的 ${mock_base_url} 占位符替换为实际 Mock 服务地址"""
    endpoint = case.get("endpoint", "")
    return endpoint.replace("${mock_base_url}", mock_base_url)


def _resolve_json(json_data: dict, variables: dict) -> dict:
    """递归替换 JSON 数据中的 ${key} 占位符"""
    if isinstance(json_data, str):
        if json_data.startswith("${") and json_data.endswith("}"):
            key = json_data[2:-1]
            return variables.get(key, json_data)
        return json_data
    elif isinstance(json_data, dict):
        return {k: _resolve_json(v, variables) for k, v in json_data.items()}
    elif isinstance(json_data, list):
        return [_resolve_json(item, variables) for item in json_data]
    return json_data


def _generate_biz_no():
    """
    生成业务流水号: 008OI + yyyyMMdd + 24位随机数 + T
    示例: 008OI202607012072147520554405888T
    """
    prefix = "008OI"
    date_str = datetime.now().strftime("%Y%m%d")
    random_digits = ''.join(str(random.randint(0, 9)) for _ in range(24))
    suffix = "T"
    return f"{prefix}{date_str}{random_digits}{suffix}"


def _generate_order_dynamic_vars():
    """
    生成创单接口所需的动态参数：
      - biz_no: 业务流水号
      - start_date / end_date: 当前日期 yyyy-MM-dd
      - estimate_start / estimate_end: 当前日期+3天 yyyy-MM-dd
    """
    now = datetime.now()
    future = now + timedelta(days=3)
    return {
        "biz_no": _generate_biz_no(),
        "start_date": now.strftime("%Y-%m-%d"),
        "end_date": now.strftime("%Y-%m-%d"),
        "estimate_start": future.strftime("%Y-%m-%d"),
        "estimate_end": future.strftime("%Y-%m-%d"),
    }


# ==================== 测试用例1：真实创单+Mock人脸+Mock签约+真实回调全流程 ====================
@allure.epic("支付宝-小程序")
@allure.feature("支付宝-小程序真实创单+Mock第三方+真实回调")
@allure.story("真实创单+Mock人脸+Mock签约+真实回调全流程")
class TestRealOrderFaceSignFlow:
    """测试用例1：真实创单 → Mock人脸 → Mock签约 → 真实回调 → 数据库验证"""

    _global_vars = None
    _order_id = None        # 步骤1（真实创单）产出
    _face_token = None      # 步骤2（Mock人脸）产出
    _agreement_no = None    # 步骤3（Mock签约）产出
    _order_amount = 19.80   # 测试金额

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    # ==================== 步骤1：真实创单（公司自研接口，被测范围） ====================
    @pytest.mark.order(1)
    @allure.title("ALI_REAL_FACE_001 - 真实创单-调用公司创单接口创建订单")
    def test_step1_real_create_order(self, merchant_api_client, global_vars):
        """
        步骤1：调用公司自研创单接口创建真实订单。

        注意：
          - 此步骤使用 merchant_api_client（已认证的商家端客户端），走真实网络请求
          - 创单接口地址 /llxz-api-web/hzsx/api/order/createOrder 需确认
          - 创单请求中携带 notify_url 指向公司自研回调接收端点
          - 产生的 orderId 为真实订单号，写入数据库，后续步骤复用
        """
        case = get_test_data(_DATA_FILE, "step1_create_order")
        gv = self._load_global_vars()
        # 注入创单接口所需的动态参数（biz_no, start_date, end_date, estimate_start, estimate_end）
        gv.update(_generate_order_dynamic_vars())
        gv["order_amount"] = self._order_amount
        gv["callback_base_url"] = global_vars.get("base_url", "")
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        endpoint = case["endpoint"]
        body = _resolve_json(copy.deepcopy(case["json"]), gv)

        with allure.step("调用真实创单接口（公司自研，被测范围）"):
            allure.attach(
                json.dumps(body, ensure_ascii=False, indent=2),
                name="创单请求体（真实接口）",
                attachment_type=allure.attachment_type.JSON
            )
            logger.info(f"[创单] 请求地址: {merchant_api_client.base_url}{endpoint}")
            logger.info(f"[创单] 请求体: {json.dumps(body, ensure_ascii=False)}")

            resp = merchant_api_client.post(endpoint, json=body)
            assert resp.status_code == case["expected_status"], \
                f"创单接口HTTP状态码异常: {resp.status_code}"

            resp_data = resp.json()
            allure.attach(
                json.dumps(resp_data, ensure_ascii=False, indent=2),
                name="创单响应（真实接口）",
                attachment_type=allure.attachment_type.JSON
            )
            logger.info(f"[创单] 响应: {json.dumps(resp_data, ensure_ascii=False)}")

        with allure.step("断言创单成功并提取orderId"):
            # 真实接口响应格式：rpcResult=SUCCESS, businessSuccess=true
            assert resp_data.get("rpcResult") == "SUCCESS", \
                f"创单RPC失败: {resp_data.get('rpcResult')}, errorMessage={resp_data.get('errorMessage')}"
            assert resp_data.get("businessSuccess") is True, \
                f"创单业务失败: {resp_data.get('businessFail')}, errorMessage={resp_data.get('errorMessage')}"
            assert resp_data.get("errorCode") is None, \
                f"创单返回错误码: {resp_data.get('errorCode')}, errorMessage={resp_data.get('errorMessage')}"

            order_id = resp_data.get("data", {}).get("orderId") or resp_data.get("data", {}).get("order_id")
            assert order_id, f"创单成功但未获取到orderId: {resp_data}"
            logger.info(f"[创单] 真实创单成功，orderId: {order_id}")

        # 保存 order_id 供后续 Mock 步骤和回调步骤使用
        self.__class__._order_id = order_id
        gv["order_id"] = order_id
        allure.attach(str(order_id), name="order_id（真实）", attachment_type=allure.attachment_type.TEXT)

    # ==================== 步骤2：Mock人脸识别（模拟第三方） ====================
    @pytest.mark.order(2)
    @allure.title("ALI_REAL_FACE_001 - Mock人脸识别-获取faceToken")
    def test_step2_mock_face_verify(self, mock_server):
        """
        步骤2：Mock人脸识别（模拟第三方人脸核验服务）。
        前置条件：步骤1必须成功获取 order_id
        注意：此步骤调用本地Mock服务，不产生真实副作用
        """
        order_id = self._order_id
        if not order_id:
            skip_msg = "[Mock人脸] 未获取到步骤1的orderId，跳过人脸识别步骤"
            logger.warning(skip_msg)
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        case = get_test_data(_DATA_FILE, "step2_face_verify")
        gv = self._load_global_vars()
        gv["mock_base_url"] = mock_server.base_url
        gv["order_id"] = order_id
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        endpoint = _resolve_endpoint(case, mock_server.base_url)
        body = _resolve_json(copy.deepcopy(case["json"]), gv)

        with allure.step("调用Mock人脸识别接口（模拟第三方，携带orderId上下文）"):
            allure.attach(
                json.dumps(body, ensure_ascii=False, indent=2),
                name="Mock人脸请求体",
                attachment_type=allure.attachment_type.JSON
            )
            resp = requests.post(endpoint, json=body, timeout=10)
            assert resp.status_code == case["expected_status"], \
                f"Mock人脸接口HTTP异常: {resp.status_code}"
            resp_data = resp.json()
            allure.attach(
                json.dumps(resp_data, ensure_ascii=False, indent=2),
                name="Mock人脸响应",
                attachment_type=allure.attachment_type.JSON
            )

        with allure.step("断言Mock人脸核验成功"):
            assert resp_data["code"] == "10000", f"Mock人脸核验失败: {resp_data}"
            face_token = resp_data["faceToken"]
            assert face_token.startswith("MOCK_FACE_"), \
                f"Mock环境返回的faceToken必须带MOCK_FACE_前缀: {face_token}"
            assert resp_data.get("mock") is True, "Mock数据必须标记mock=true"
            logger.info(f"[Mock人脸] 人脸识别成功，faceToken: {face_token}")

        # 保存 face_token 供后续步骤使用
        self.__class__._face_token = face_token
        gv["face_token"] = face_token
        allure.attach(face_token, name="face_token（Mock）", attachment_type=allure.attachment_type.TEXT)

        # 验证 Mock 正确记录了本次请求（审计日志）
        last_req = mock_server.last_requests.get("face_verify", {})
        print("last_req:", last_req)
        assert last_req.get("order_id") == order_id,  f"Mock人脸请求未正确传递order_id: last_req={last_req}, expected={order_id}"

    # ==================== 步骤3：Mock支付宝签约（模拟第三方） ====================
    @pytest.mark.order(3)
    @allure.title("ALI_REAL_FACE_001 - Mock支付宝签约-获取agreementNo")
    def test_step3_mock_alipay_sign(self, mock_server):
        """
        步骤3：Mock支付宝签约（模拟第三方签约服务）。

        前置条件：步骤1 order_id + 步骤2 face_token 必须可用
        注意：此步骤调用本地Mock服务，不产生真实副作用
        """
        order_id = self._order_id
        face_token = self._face_token
        if not order_id or not face_token:
            skip_msg = f"[Mock签约] 未获取到orderId或faceToken (order_id={order_id}, face_token={face_token})，跳过签约步骤"
            logger.warning(skip_msg)
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        case = get_test_data(_DATA_FILE, "step3_alipay_sign")
        gv = self._load_global_vars()
        gv["mock_base_url"] = mock_server.base_url
        gv["order_id"] = order_id
        gv["face_token"] = face_token
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        endpoint = _resolve_endpoint(case, mock_server.base_url)
        body = _resolve_json(copy.deepcopy(case["json"]), gv)

        with allure.step("调用Mock支付宝签约接口（模拟第三方，携带orderId+faceToken）"):
            allure.attach(
                json.dumps(body, ensure_ascii=False, indent=2),
                name="Mock签约请求体",
                attachment_type=allure.attachment_type.JSON
            )
            resp = requests.post(endpoint, json=body, timeout=10)
            assert resp.status_code == case["expected_status"], \
                f"Mock签约接口HTTP异常: {resp.status_code}"
            resp_data = resp.json()
            allure.attach(
                json.dumps(resp_data, ensure_ascii=False, indent=2),
                name="Mock签约响应",
                attachment_type=allure.attachment_type.JSON
            )

        with allure.step("断言Mock签约成功"):
            assert resp_data["code"] == "10000", f"Mock签约失败: {resp_data}"
            agreement_no = resp_data["agreement_no"]
            assert agreement_no.startswith("MOCK_AGREEMENT_"), f"Mock环境返回的agreement_no必须带MOCK_AGREEMENT_前缀: {agreement_no}"
            assert resp_data.get("mock") is True, "Mock数据必须标记mock=true"
            logger.info(f"[Mock签约] 签约成功，agreementNo: {agreement_no}")

        # 保存 agreement_no 供回调步骤使用
        self.__class__._agreement_no = agreement_no
        gv["agreement_no"] = agreement_no
        allure.attach(agreement_no, name="agreement_no（Mock）", attachment_type=allure.attachment_type.TEXT)

        # 验证 Mock 正确记录了本次请求
        last_req = mock_server.last_requests.get("alipay_sign", {})
        assert last_req.get("face_token") == face_token, f"Mock签约请求未正确传递face_token: last_req={last_req}"
        assert last_req.get("order_id") == order_id, f"Mock签约请求未正确传递order_id: last_req={last_req}"

    # ==================== 步骤4：签约成功回调（支付宝dispatch.notify网关回调） ====================
    @pytest.mark.order(4)
    @allure.title("ALI_REAL_FACE_001 - 签约成功回调-支付宝dispatch.notify通知")
    def test_step4_real_callback(self, merchant_api_client, global_vars):
        """
        步骤4：向支付宝回调网关发送签约成功通知（dispatch.notify），完成订单状态流转。

        前置条件：步骤1 order_id 必须可用

        关键设计：
          - 此步骤使用 requests 直接调用支付宝回调网关接口（multipart/form-data）
          - 模拟支付宝 dispatch.notify 异步通知，包含 biz_content（JSON业务数据）、签名等核心字段
          - rent_dispatch_id 引用步骤1产出的 order_id，关联真实订单
          - 回调接口负责解析通知、更新订单 dispatch 状态
        """
        order_id = self._order_id
        if not order_id:
            skip_msg = "[签约回调] 未获取到步骤1的orderId，跳过签约回调步骤"
            logger.warning(skip_msg)
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        case = get_test_data(_DATA_FILE, "step4_payment_callback")
        gv = self._load_global_vars()
        # 注入动态参数
        gv["order_id"] = order_id
        gv["source_uid"] = "2088902644935707"  # 创单时使用的 sourceUid/zfbUserId
        gv["start_date"] = datetime.now().strftime("%Y-%m-%d")
        gv["utc_timestamp"] = str(int(time.time() * 1000))
        gv["notify_id"] = f"{datetime.now().strftime('%Y%m%d')}{str(int(time.time()*1000))[:10]}{random.randint(1000000000, 9999999999)}"
        gv["sign"] = "XWZFMc84K75hlA7BXLo+p6eNN8zr4LgA0vcMCpHaVHm7s0YzBcIfYBoz0dkzvmefJ1CdbHHATo9NUxBj4dhDHKORDLj2FQWkfPddndHd/Cwr3Rzy0uyi6vrWQcgJJgkcTy+i1DTfXgbQuVkPEhPAH7TpVlORaVfA4k9SCt//mLEwg9wBVHGyLJB2dXDSyg02uJpzkbe3/PjGMAqGzZTMX0Hfgif7/zgiOzVvMMKiGmdQtrk0pUTwDwfNXqmnhrH2IySX0hgwScM+gSDc45lAEBVbE/otGpIaK1YOvHJwdjKI/sUnFzXB9HsE9XxZRkHlRvmHUj+uKJN0zHa7lqSsTA=="
        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        # 构建完整 URL
        base_url = global_vars.get("base_url", "https://test.llxzu.com")
        endpoint = case["endpoint"]
        full_url = f"{base_url}{endpoint}"

        # 解析 form_data 中的占位符（支持字符串内嵌 ${var} 替换）
        def _replace_vars(text: str, variables: dict) -> str:
            """替换字符串中所有 ${key} 占位符"""
            import re
            def _replacer(match):
                key = match.group(1)
                return str(variables.get(key, match.group(0)))
            return re.sub(r'\$\{(\w+)\}', _replacer, text)

        form_data_template = copy.deepcopy(case["form_data"])
        form_data = {}
        for key, value in form_data_template.items():
            if isinstance(value, str):
                form_data[key] = _replace_vars(value, gv)
            else:
                form_data[key] = value

        # 解析 headers
        headers = copy.deepcopy(case.get("headers", {}))
        # 设置 Cookie（从 cURL 中提取）
        headers["Cookie"] = "acw_tc=0a05830e17772547719204691e32b1c52f7ed806c538c6d1d79c768b618a57"

        # ---- 步骤4a：调用签约成功回调接口 ----
        with allure.step("调用支付宝回调网关接口（multipart/form-data，模拟dispatch.notify通知）"):
            allure.attach(json.dumps({"url": full_url,
                "headers": {k: v for k, v in headers.items() if k != "Cookie"},
                "form_data": {k: (v[:200] + "..." if len(v) > 200 else v) for k, v in form_data.items()}}, ensure_ascii=False, indent=2),
                name="回调请求信息（真实网关）", attachment_type=allure.attachment_type.JSON)
            logger.info(f"[签约回调] 请求地址: {full_url}")
            logger.info(f"[签约回调] 请求头: {json.dumps(headers, ensure_ascii=False)}")
            logger.info(f"[签约回调] form_data keys: {list(form_data.keys())}")

            # 使用 requests 发送 multipart/form-data 请求  files 参数用于 multipart/form-data 编码
            resp = requests.post(full_url, headers=headers, files={k: (None, v) for k, v in form_data.items()},timeout=30 )
            assert resp.status_code == case["expected_status"], f"签约回调接口HTTP状态码异常: {resp.status_code}"
            # 网关接口返回纯文本 "success"，非 JSON 格式
            resp_text = resp.text.strip()
            allure.attach(resp_text, name="回调响应（真实网关）", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"[签约回调] 响应: {resp_text}")

        with allure.step("断言签约回调接口返回成功"):
            assert resp_text == "success", f"签约回调失败: 期望返回'success'，实际返回'{resp_text}'"
            logger.info("[签约回调] 签约成功回调接口调用成功，dispatch.notify通知处理完成")
#
#
# # ==================== 测试用例2：创单后-人脸核验失败场景 ====================
# @allure.epic("支付宝-小程序")
# @allure.feature("支付宝-小程序真实创单+Mock第三方+真实回调")
# @allure.story("异常场景：人脸核验失败")
# class TestFaceVerifyFailReal:
#     """测试用例2：真实创单成功 → Mock人脸失败 → 验证订单状态未被污染"""
#
#     _global_vars = None
#     _order_id = None
#
#     @classmethod
#     def _load_global_vars(cls):
#         if cls._global_vars is None:
#             cls._global_vars = get_global_variables(_DATA_FILE)
#         return cls._global_vars.copy()
#
#     @pytest.mark.order(5)
#     @allure.title("ALI_REAL_FACE_002 - 创单后-人脸核验失败场景")
#     def test_face_verify_fail(self, merchant_api_client, mock_server, db, global_vars):
#         """测试用例2：真实创单成功后，Mock人脸核验失败，验证订单状态不受影响。"""
#         gv = self._load_global_vars()
#         gv["callback_base_url"] = global_vars.get("base_url", "")
#
#         # ---- 步骤1：真实创单 ----
#         order_case = get_test_data(_DATA_FILE, "fail_face_step1_order")
#         gv["order_amount"] = 19.80
#
#         with allure.step("步骤1：真实创单"):
#             order_endpoint = order_case["endpoint"]
#             order_body = _resolve_json(copy.deepcopy(order_case["json"]), gv)
#             logger.info(f"[人脸失败-创单] 请求: {json.dumps(order_body, ensure_ascii=False)}")
#             resp = merchant_api_client.post(order_endpoint, json=order_body)
#             assert resp.status_code == 200, f"创单HTTP异常: {resp.status_code}"
#             order_data = resp.json()
#             assert order_data.get("businessSuccess") is True, \
#                 f"创单失败: errorMessage={order_data.get('errorMessage')}"
#
#             order_id = order_data.get("data", {}).get("orderId") or order_data.get("data", {}).get("order_id")
#             assert order_id, f"未获取到orderId: {order_data}"
#             logger.info(f"[人脸失败-创单] 创单成功，orderId: {order_id}")
#             self.__class__._order_id = order_id
#             gv["order_id"] = order_id
#             allure.attach(order_id, name="orderId", attachment_type=allure.attachment_type.TEXT)
#
#         # ---- 步骤2：Mock人脸识别失败 ----
#         face_case = get_test_data(_DATA_FILE, "fail_face_step2_verify")
#         gv["mock_base_url"] = mock_server.base_url
#         allure.dynamic.title(f"{face_case['case_id']} | {face_case['title']}")
#
#         with allure.step("步骤2：Mock人脸核验失败（fail_mode=true，携带orderId）"):
#             face_endpoint = _resolve_endpoint(face_case, mock_server.base_url)
#             face_body = _resolve_json(copy.deepcopy(face_case["json"]), gv)
#             allure.attach(
#                 json.dumps(face_body, ensure_ascii=False, indent=2),
#                 name="Mock人脸请求（失败场景）",
#                 attachment_type=allure.attachment_type.JSON
#             )
#             face_resp = requests.post(face_endpoint, json=face_body, timeout=10)
#             face_data = face_resp.json()
#             allure.attach(
#                 json.dumps(face_data, ensure_ascii=False, indent=2),
#                 name="Mock人脸响应（失败场景）",
#                 attachment_type=allure.attachment_type.JSON
#             )
#
#         with allure.step("断言人脸核验返回失败"):
#             assert face_data["code"] == "20000", \
#                 f"期望失败码20000，实际: {face_data.get('code')}"
#             assert face_data["verifyStatus"] == "FAIL", \
#                 f"期望verifyStatus=FAIL，实际: {face_data.get('verifyStatus')}"
#             assert face_data["faceToken"] is None, \
#                 "失败场景faceToken应为null（后续步骤无有效凭证）"
#             logger.info("[人脸失败] Mock人脸核验失败场景验证通过：无有效faceToken")
#
#         # ---- 步骤3：数据库验证订单状态未被污染 ----
#         with allure.step("步骤3：数据库验证订单状态"):
#             verify_sql = (
#                 f"SELECT order_id, status, face_auth_status "
#                 f"FROM llxz_order.ct_user_orders "
#                 f"WHERE order_id = '{order_id}'"
#             )
#             allure.attach(verify_sql, name="验证SQL", attachment_type=allure.attachment_type.TEXT)
#             order_record = db.fetch_one(verify_sql)
#             if order_record:
#                 actual_face_auth = order_record.get("face_auth_status", "")
#                 allure.attach(
#                     f"status={order_record.get('status')}, face_auth_status={actual_face_auth}",
#                     name="订单状态",
#                     attachment_type=allure.attachment_type.TEXT
#                 )
#                 if actual_face_auth:
#                     assert actual_face_auth != "03", \
#                         f"人脸失败后face_auth_status不应为03（通过）: {actual_face_auth}"
#                 logger.info(f"[人脸失败-验证] 订单状态未被污染: status={order_record.get('status')}")
#
#         # 验证 Mock 记录了 fail_mode 请求
#         last_req = mock_server.last_requests.get("face_verify", {})
#         assert last_req.get("fail_mode") is True, \
#             f"Mock未正确记录fail_mode参数: {last_req}"
#         assert last_req.get("order_id") == order_id, \
#             f"Mock人脸请求未正确传递order_id: {last_req}"
#
#
# # ==================== 测试用例3：创单后-签约失败场景 ====================
# @allure.epic("支付宝-小程序")
# @allure.feature("支付宝-小程序真实创单+Mock第三方+真实回调")
# @allure.story("异常场景：签约失败")
# class TestSignFailReal:
#     """测试用例3：真实创单 → Mock人脸成功 → Mock签约失败（无效faceToken）"""
#
#     _global_vars = None
#
#     @classmethod
#     def _load_global_vars(cls):
#         if cls._global_vars is None:
#             cls._global_vars = get_global_variables(_DATA_FILE)
#         return cls._global_vars.copy()
#
#     @pytest.mark.order(6)
#     @allure.title("ALI_REAL_FACE_003 - 创单后-签约失败场景")
#     def test_agreement_sign_fail(self, merchant_api_client, mock_server, db, global_vars):
#         """测试用例3：真实创单+Mock人脸成功后，使用无效faceToken导致Mock签约失败。"""
#         gv = self._load_global_vars()
#         gv["callback_base_url"] = global_vars.get("base_url", "")
#
#         # ---- 步骤1：真实创单 ----
#         order_case = get_test_data(_DATA_FILE, "fail_sign_step1_order")
#         with allure.step("步骤1：真实创单"):
#             order_body = _resolve_json(copy.deepcopy(order_case["json"]), gv)
#             resp = merchant_api_client.post(order_case["endpoint"], json=order_body)
#             order_data = resp.json()
#             assert order_data.get("businessSuccess") is True, \
#                 f"创单失败: {order_data.get('errorMessage')}"
#             order_id = order_data.get("data", {}).get("orderId") or order_data.get("data", {}).get("order_id")
#             logger.info(f"[签约失败-创单] orderId: {order_id}")
#             gv["order_id"] = order_id
#             allure.attach(order_id, name="orderId", attachment_type=allure.attachment_type.TEXT)
#
#         # ---- 步骤2：Mock人脸识别成功 ----
#         face_case = get_test_data(_DATA_FILE, "fail_sign_step2_face")
#         gv["mock_base_url"] = mock_server.base_url
#         with allure.step("步骤2：Mock人脸识别获取正常faceToken"):
#             face_body = _resolve_json(copy.deepcopy(face_case["json"]), gv)
#             face_resp = requests.post(
#                 _resolve_endpoint(face_case, mock_server.base_url),
#                 json=face_body, timeout=10
#             )
#             face_token = face_resp.json()["faceToken"]
#             logger.info(f"[签约失败-人脸] faceToken: {face_token}")
#             gv["face_token"] = face_token
#             allure.attach(face_token, name="faceToken", attachment_type=allure.attachment_type.TEXT)
#
#         # ---- 步骤3：Mock签约失败（使用无效faceToken） ----
#         sign_case = get_test_data(_DATA_FILE, "fail_sign_step3_sign")
#         allure.dynamic.title(f"{sign_case['case_id']} | {sign_case['title']}")
#         gv["face_token"] = "invalid_face_token"  # 覆盖为无效token
#
#         with allure.step("步骤3：Mock签约失败（无效faceToken，不含MOCK_前缀）"):
#             sign_body = _resolve_json(copy.deepcopy(sign_case["json"]), gv)
#             sign_endpoint = _resolve_endpoint(sign_case, mock_server.base_url)
#             allure.attach(
#                 json.dumps(sign_body, ensure_ascii=False, indent=2),
#                 name="Mock签约请求（无效faceToken）",
#                 attachment_type=allure.attachment_type.JSON
#             )
#             sign_resp = requests.post(sign_endpoint, json=sign_body, timeout=10)
#             sign_data = sign_resp.json()
#             allure.attach(
#                 json.dumps(sign_data, ensure_ascii=False, indent=2),
#                 name="Mock签约响应（失败）",
#                 attachment_type=allure.attachment_type.JSON
#             )
#
#         with allure.step("断言签约返回失败"):
#             assert sign_data["code"] == "20000", \
#                 f"期望失败码20000，实际: {sign_data.get('code')}"
#             assert sign_data["status"] == "FAIL", \
#                 f"期望status=FAIL，实际: {sign_data.get('status')}"
#             assert sign_data["agreement_no"] is None, \
#                 "失败场景agreement_no应为null（回调步骤无法执行）"
#             logger.info("[签约失败] Mock签约失败验证通过：无有效agreementNo")
#
#         # 验证 Mock 正确拒绝了无效 faceToken
#         last_req = mock_server.last_requests.get("alipay_sign", {})
#         assert last_req.get("face_token") == "invalid_face_token", \
#             f"Mock未正确记录无效face_token: {last_req}"
#         assert last_req.get("order_id") == order_id, \
#             f"Mock签约请求未正确传递order_id: {last_req}"
#
#
# # ==================== 测试用例4：回调失败场景（真实回调接口异常处理） ====================
# @allure.epic("支付宝-小程序")
# @allure.feature("支付宝-小程序真实创单+Mock第三方+真实回调")
# @allure.story("异常场景：回调接口异常处理")
# class TestCallbackFailReal:
#     """测试用例4：真实创单 → Mock人脸成功 → Mock签约成功 → 真实回调带无效参数"""
#
#     _global_vars = None
#
#     @classmethod
#     def _load_global_vars(cls):
#         if cls._global_vars is None:
#             cls._global_vars = get_global_variables(_DATA_FILE)
#         return cls._global_vars.copy()
#
#     @pytest.mark.order(7)
#     @allure.title("ALI_REAL_FACE_004 - 回调失败场景-无效orderId")
#     def test_callback_with_invalid_order(self, merchant_api_client, mock_server, db, global_vars):
#         """
#         测试用例4：回调接口异常处理验证。
#
#         关键设计：
#           - 步骤1-3：正常完成创单+人脸+签约
#           - 步骤4：向回调接口发送不存在的orderId，验证接口的错误处理（非500/崩溃）
#           - 验证被正确拒绝而非静默忽略
#         """
#         gv = self._load_global_vars()
#         gv["callback_base_url"] = global_vars.get("base_url", "")
#
#         # ---- 步骤1：真实创单 ----
#         order_case = get_test_data(_DATA_FILE, "fail_callback_step1_order")
#         with allure.step("步骤1：真实创单"):
#             order_body = _resolve_json(copy.deepcopy(order_case["json"]), gv)
#             resp = merchant_api_client.post(order_case["endpoint"], json=order_body)
#             order_data = resp.json()
#             assert order_data.get("businessSuccess") is True, \
#                 f"创单失败: {order_data.get('errorMessage')}"
#             order_id = order_data.get("data", {}).get("orderId") or order_data.get("data", {}).get("order_id")
#             gv["order_id"] = order_id
#             allure.attach(order_id, name="orderId", attachment_type=allure.attachment_type.TEXT)
#
#         # ---- 步骤2：Mock人脸 ----
#         face_case = get_test_data(_DATA_FILE, "fail_callback_step2_face")
#         gv["mock_base_url"] = mock_server.base_url
#         with allure.step("步骤2：Mock人脸识别"):
#             face_body = _resolve_json(copy.deepcopy(face_case["json"]), gv)
#             face_resp = requests.post(
#                 _resolve_endpoint(face_case, mock_server.base_url),
#                 json=face_body, timeout=10
#             )
#             gv["face_token"] = face_resp.json()["faceToken"]
#
#         # ---- 步骤3：Mock签约 ----
#         sign_case = get_test_data(_DATA_FILE, "fail_callback_step3_sign")
#         with allure.step("步骤3：Mock签约"):
#             sign_body = _resolve_json(copy.deepcopy(sign_case["json"]), gv)
#             sign_resp = requests.post(
#                 _resolve_endpoint(sign_case, mock_server.base_url),
#                 json=sign_body, timeout=10
#             )
#             gv["agreement_no"] = sign_resp.json()["agreement_no"]
#
#         # ---- 步骤4：真实回调-无效orderId ----
#         cb_case = get_test_data(_DATA_FILE, "fail_callback_step4_callback")
#         allure.dynamic.title(f"{cb_case['case_id']} | {cb_case['title']}")
#         cb_body = _resolve_json(copy.deepcopy(cb_case["json"]), gv)
#
#         with allure.step("步骤4：向真实回调接口发送不存在的orderId"):
#             allure.attach(
#                 json.dumps(cb_body, ensure_ascii=False, indent=2),
#                 name="回调请求体（无效orderId）",
#                 attachment_type=allure.attachment_type.JSON
#             )
#             logger.info(f"[回调失败] 发送无效orderId回调: {cb_body['out_trade_no']}")
#             resp = merchant_api_client.post(cb_case["endpoint"], json=cb_body)
#             resp_data = resp.json()
#             allure.attach(
#                 json.dumps(resp_data, ensure_ascii=False, indent=2),
#                 name="回调响应（无效orderId）",
#                 attachment_type=allure.attachment_type.JSON
#             )
#
#         with allure.step("断言回调接口正确处理无效orderId"):
#             # HTTP层面应正常（200），不应500崩溃
#             assert resp.status_code == 200, \
#                 f"回调接口HTTP异常（可能未正确处理无效参数）: {resp.status_code}"
#             # 业务层面应返回失败
#             assert resp_data.get("businessSuccess") is False, \
#                 f"无效orderId不应返回businessSuccess=true: {resp_data}"
#             logger.info(f"[回调失败] 回调接口正确拒绝了无效orderId: businessSuccess={resp_data.get('businessSuccess')}")
#
#
# # ==================== 测试用例5：金额一致性校验（参数化） ====================
# @allure.epic("支付宝-小程序")
# @allure.feature("支付宝-小程序真实创单+Mock第三方+真实回调")
# @allure.story("金额一致性校验（真实创单）")
# class TestAmountConsistencyReal:
#     """测试用例5：多组金额参数化，真实创单→Mock人脸→Mock签约→数据库验证金额"""
#
#     _global_vars = None
#
#     @classmethod
#     def _load_global_vars(cls):
#         if cls._global_vars is None:
#             cls._global_vars = get_global_variables(_DATA_FILE)
#         return cls._global_vars.copy()
#
#     @pytest.mark.parametrize(
#         "case",
#         get_test_data(_DATA_FILE, "amount_consistency_cases"),
#         ids=lambda c: f"{c.get('case_id', '?')} | {c.get('title', '?')}"
#     )
#     @allure.title("{case[case_id]} | {case[title]}")
#     def test_amount_consistency(self, case, merchant_api_client, mock_server, db, global_vars):
#         """测试用例5：金额一致性校验 - 真实创单 → Mock人脸 → Mock签约 → 数据库验证"""
#         gv = self._load_global_vars()
#         gv["mock_base_url"] = mock_server.base_url
#         gv["callback_base_url"] = global_vars.get("base_url", "")
#         amount = case["amount"]
#         logger.info(f"[金额校验] 测试金额: {amount}")
#
#         # ---- 步骤1：真实创单（带指定金额） ----
#         order_case = get_test_data(_DATA_FILE, "step1_create_order")
#         with allure.step(f"步骤1：真实创单（金额={amount}）"):
#             order_body = _resolve_json(copy.deepcopy(order_case["json"]), gv)
#             order_body["amount"] = amount
#             allure.attach(
#                 json.dumps(order_body, ensure_ascii=False, indent=2),
#                 name="创单请求体",
#                 attachment_type=allure.attachment_type.JSON
#             )
#             resp = merchant_api_client.post(order_case["endpoint"], json=order_body)
#             order_data = resp.json()
#             assert order_data.get("businessSuccess") is True, \
#                 f"创单失败: {order_data.get('errorMessage')}"
#
#             order_id = order_data.get("data", {}).get("orderId") or order_data.get("data", {}).get("order_id")
#             assert order_id, f"未获取到orderId: {order_data}"
#             logger.info(f"[金额校验] 创单成功，orderId: {order_id}, amount={amount}")
#             gv["order_id"] = order_id
#             allure.attach(order_id, name="orderId", attachment_type=allure.attachment_type.TEXT)
#
#         # ---- 步骤2：Mock人脸识别 ----
#         face_case = get_test_data(_DATA_FILE, "step2_face_verify")
#         with allure.step(f"步骤2：Mock人脸识别（金额={amount}，携带orderId）"):
#             face_body = _resolve_json(copy.deepcopy(face_case["json"]), gv)
#             face_resp = requests.post(
#                 _resolve_endpoint(face_case, mock_server.base_url),
#                 json=face_body, timeout=10
#             )
#             gv["face_token"] = face_resp.json()["faceToken"]
#
#         # ---- 步骤3：Mock签约 ----
#         sign_case = get_test_data(_DATA_FILE, "step3_alipay_sign")
#         with allure.step(f"步骤3：Mock签约（金额={amount}，携带orderId+faceToken）"):
#             sign_body = _resolve_json(copy.deepcopy(sign_case["json"]), gv)
#             sign_resp = requests.post(
#                 _resolve_endpoint(sign_case, mock_server.base_url),
#                 json=sign_body, timeout=10
#             )
#             gv["agreement_no"] = sign_resp.json()["agreement_no"]
#
#         # ---- 步骤4：数据库验证金额 ----
#         with allure.step(f"步骤4：数据库验证订单金额: {amount}"):
#             verify_sql = (
#                 f"SELECT order_id, total_amount, pay_amount "
#                 f"FROM llxz_order.ct_user_orders "
#                 f"WHERE order_id = '{order_id}'"
#             )
#             allure.attach(verify_sql, name="验证SQL", attachment_type=allure.attachment_type.TEXT)
#             order_record = db.fetch_one(verify_sql)
#             assert order_record is not None, f"未查询到订单 {order_id}"
#
#             db_amount = order_record.get("total_amount") or order_record.get("pay_amount")
#             if db_amount is not None:
#                 db_amount = float(db_amount)
#                 assert db_amount == amount, \
#                     f"数据库金额不一致: {db_amount} != {amount}"
#                 logger.info(f"[金额校验] 金额 {amount} 数据库验证通过")
#             else:
#                 logger.warning(f"[金额校验] 数据库金额字段为空，跳过金额比较（可能由创单接口保证）")
#
#         # 验证 Mock 正确记录了请求
#         last_req = mock_server.last_requests.get("create_order", {})
#         if not last_req:  # 真实创单不经过Mock，此检查改为确认Mock未被误用
#             logger.info("[金额校验] 确认创单未使用Mock（符合预期）")
