# testcases/admin/scenario/merchant_onboarding/test_merchant_onboarding.py
"""
运营端 - 商家入驻流程测试

完整的商家入驻注册流程，包含6个步骤：
  步骤1: 获取注册码（generateRegCdByGroupCodeNew）
  步骤2: 提交注册店铺信息（register，动态生成手机号和用户名）
  步骤3: 解析注册登录的图片验证码（OCR识别，最多重试5次）
  步骤4: 校验图片验证码（sendVerifyCodeOfSmsLogin）
  步骤5: 使用验证码登录（loginV2）
  步骤6: 进入店铺（SQL查询用户ID + changeLogin）
"""
import json
import time
import ddddocr
import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case, replace_placeholders
from utils.data_generator import generate_test_data
from utils.data_loader import get_test_data, get_global_variables

_DATA_FILE = "data/admin/scenario/merchant_onboarding/merchant_onboarding.yaml"


@allure.epic("运营端")
@allure.feature("运营端-商家入驻")
@allure.story("商家入驻流程")
class TestMerchantOnboarding:
    """
    商家入驻完整流程：
    获取注册码 → 注册店铺 → 获取图片验证码(OCR) → 校验验证码 → 登录 → 进入店铺
    """

    # ==================== 跨步骤共享变量 ====================
    _global_vars = None
    _registry_code = None
    _mobile = None
    _user_name_req = None
    _captcha_code = None
    _login_token = None
    _shop_id = None

    @classmethod
    def _load_global_vars(cls):
        """加载 YAML 全局变量（懒加载 + 缓存）"""
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    # ==================== 第一步：获取注册码 ====================
    @pytest.mark.order(1)
    @allure.title("REG_001 - 获取注册码")
    def test_step1_generate_reg_code(self, admin_api_client, db):
        """调用 generateRegCdByGroupCodeNew 接口获取注册码，提取 data 字段值"""
        case = get_test_data(_DATA_FILE, "step1_generate_reg_code")
        global_vars = self._load_global_vars()
        allure.dynamic.title(f"{case['step_id']} | {case['title']}")

        execute_test_case(case, admin_api_client, db, global_vars)

        # 提取 registry_code（execute_test_case 已通过 extract_vars 写入 global_vars）
        registry_code = global_vars.get("registry_code")
        if not registry_code:
            pytest.skip("未获取到注册码 (registry_code)，跳过后续步骤")

        self.__class__._registry_code = str(registry_code)
        allure.attach(
            f"registry_code = {self._registry_code}",
            name="提取的注册码",
            attachment_type=allure.attachment_type.TEXT,
        )
        logger.info(f"[REG_001] 获取注册码成功: {self._registry_code}")

    # ==================== 第二步：提交注册店铺信息 ====================
    @pytest.mark.order(2)
    @allure.title("REG_002 - 提交注册店铺信息")
    def test_step2_register(self, admin_api_client, db):
        """动态生成手机号和用户名，调用 register 接口注册新店铺"""
        if not self._registry_code:
            pytest.skip("步骤1未获取到注册码，跳过注册")

        case = get_test_data(_DATA_FILE, "step2_register")
        global_vars = self._load_global_vars()

        # 动态生成测试数据
        mobile = generate_test_data("cn_phone")
        user_name_req = generate_test_data("cn_name")

        self.__class__._mobile = mobile
        self.__class__._user_name_req = user_name_req

        # 注入动态变量
        global_vars["mobile"] = mobile
        global_vars["user_name_req"] = user_name_req
        global_vars["registry_code"] = self._registry_code

        allure.dynamic.title(f"{case['step_id']} | {case['title']}")
        allure.attach(
            f"mobile = {mobile}\nuserNameReq = {user_name_req}\nregistryCode = {self._registry_code}",
            name="动态生成的注册信息",
            attachment_type=allure.attachment_type.TEXT,
        )

        execute_test_case(case, admin_api_client, db, global_vars)
        logger.info(f"[REG_002] 注册成功: mobile={mobile}, userNameReq={user_name_req}")

    # ==================== 第三步：解析注册登录的图片验证码 ====================
    @pytest.mark.order(3)
    @allure.title("REG_003 - 解析注册登录的图片验证码")
    def test_step3_captcha(self, merchant_api_client, db):
        """
        获取图片验证码并使用 ddddocr 进行 OCR 识别。
        若识别失败（非图片响应/OCR异常/结果过短），重新获取并重试，最多 5 次。
        5 次全部失败则跳过本次注册。
        本步骤仅负责识别，验证码校验由步骤4独立完成。
        """
        if not self._mobile:
            pytest.skip("步骤2未获取到手机号，跳过验证码识别")

        # 加载步骤3配置（验证码获取）
        captcha_config = get_test_data(_DATA_FILE, "step3_captcha")
        global_vars = self._load_global_vars()
        global_vars["mobile"] = self._mobile

        max_retries = captcha_config.get("max_retries", 5)
        endpoint = captcha_config["endpoint"]

        # 构造请求体（替换变量）
        captcha_body = replace_placeholders(captcha_config["json"], global_vars)

        ocr = ddddocr.DdddOcr(show_ad=False)

        # 临时缩短请求间隔（验证码有效期短）
        original_interval = getattr(merchant_api_client, 'request_interval', None)
        if original_interval is not None:
            merchant_api_client.request_interval = 0.5
        code = None
        try:
            for attempt in range(1, max_retries + 1):
                with allure.step(f"验证码识别 第{attempt}/{max_retries}次"):
                    # ---- 1. 请求验证码图片（POST 返回二进制图片）----
                    try:
                        captcha_resp = merchant_api_client.post(endpoint, json=captcha_body)
                    except Exception as e:
                        logger.warning(f"第{attempt}次验证码请求异常: {e}")
                        allure.attach(
                            f"请求异常: {e}",
                            name=f"第{attempt}次-验证码请求失败",
                            attachment_type=allure.attachment_type.TEXT,
                        )
                        time.sleep(1)
                        continue

                    # 检查响应是否为图片
                    content_type = captcha_resp.headers.get('Content-Type', '').lower()
                    resp_len = len(captcha_resp.content)
                    if 'image' not in content_type and resp_len < 100:
                        logger.warning(
                            f"第{attempt}次: 非图片响应 (Content-Type={content_type}, len={resp_len})"
                        )
                        allure.attach(
                            f"Content-Type: {content_type}\n响应长度: {resp_len}",
                            name=f"第{attempt}次-非图片响应",
                            attachment_type=allure.attachment_type.TEXT,
                        )
                        time.sleep(1)
                        continue

                    # ---- 2. OCR 识别 ----
                    try:
                        raw_code = ocr.classification(captcha_resp.content)
                    except Exception as e:
                        logger.warning(f"第{attempt}次 OCR 异常: {e}")
                        allure.attach(
                            captcha_resp.content,
                            name=f"第{attempt}次-验证码原图",
                            attachment_type=allure.attachment_type.PNG,
                        )
                        time.sleep(1)
                        continue

                    if not raw_code or len(raw_code.strip()) < 4:
                        logger.warning(f"第{attempt}次 OCR 结果异常: '{raw_code}'")
                        allure.attach(
                            captcha_resp.content,
                            name=f"第{attempt}次-验证码原图",
                            attachment_type=allure.attachment_type.PNG,
                        )
                        time.sleep(1)
                        continue

                    # OCR 识别成功
                    code = raw_code.strip()
                    allure.attach(
                        captcha_resp.content,
                        name=f"第{attempt}次-验证码={code}",
                        attachment_type=allure.attachment_type.PNG,
                    )
                    logger.info(f"第{attempt}次验证码识别成功: '{code}'")
                    break
        finally:
            # 恢复原始请求间隔
            if original_interval is not None:
                merchant_api_client.request_interval = original_interval

        # 保存验证码供后续步骤使用
        self.__class__._captcha_code = code

        if not code:
            skip_msg = (
                f"验证码识别失败，已重试{max_retries}次仍未成功，跳过本次店铺注册"
            )
            allure.attach(
                skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT
            )
            logger.warning(skip_msg)
            pytest.skip(skip_msg)

        allure.attach(
            f"最终验证码: {code}",
            name="验证码识别结果",
            attachment_type=allure.attachment_type.TEXT,
        )
        logger.info(f"[REG_003] 验证码识别成功: {code}")

    # # ==================== 第四步：校验图片验证码 ====================
    # @pytest.mark.order(4)
    # @allure.title("REG_004 - 校验图片验证码")
    # def test_step4_verify_code(self, merchant_api_client, db):
    #     """使用步骤3已识别的验证码，调用 sendVerifyCodeOfSmsLogin 接口正式校验"""
    #     if not self._captcha_code:
    #         pytest.skip("步骤3未获取到验证码，跳过校验")
    #
    #     case = get_test_data(_DATA_FILE, "step4_verify_code")
    #     global_vars = self._load_global_vars()
    #
    #     global_vars["mobile"] = self._mobile
    #     global_vars["captcha_code"] = self._captcha_code
    #
    #     allure.dynamic.title(f"{case['step_id']} | {case['title']}")
    #     execute_test_case(case, merchant_api_client, db, global_vars)
    #     logger.info(f"[REG_004] 验证码校验成功: code={self._captcha_code}")

    # # ==================== 第五步：使用验证码登录 ====================
    # @pytest.mark.order(5)
    # @allure.title("REG_005 - 使用验证码登录")
    # def test_step5_login(self, merchant_api_client, db):
    #     """
    #     使用验证码登录，提取 token 和 shopId。
    #     注意：loginV2 接口 businessSuccess=False 但 data.token 有效（已知约定）。
    #     """
    #     if not self._captcha_code:
    #         pytest.skip("步骤3未获取到验证码，跳过登录")
    #
    #     case = get_test_data(_DATA_FILE, "step5_login")
    #     global_vars = self._load_global_vars()
    #
    #     global_vars["mobile"] = self._mobile
    #     global_vars["captcha_code"] = self._captcha_code
    #
    #     allure.dynamic.title(f"{case['step_id']} | {case['title']}")
    #
    #     # execute_test_case 会发送请求并验证 $.data.token is_not_none
    #     execute_test_case(case, merchant_api_client, db, global_vars)
    #
    #     # 再次发送请求提取 token 和 shopId（execute_test_case 不返回响应体）
    #     # 注意：loginV2 接口 businessSuccess=False 但 data.token 有效（已知约定）
    #     body = replace_placeholders(case["json"], global_vars)
    #     resp = merchant_api_client.post(case["endpoint"], json=body)
    #     resp_json = resp.json()
    #     data = resp_json.get("data") or {}
    #
    #     token = data.get("token")
    #     shop_id = data.get("shopId")
    #
    #     if token:
    #         self.__class__._login_token = token
    #         self.__class__._shop_id = shop_id
    #         allure.attach(
    #             f"token = {token}\nshopId = {shop_id}",
    #             name="登录凭证",
    #             attachment_type=allure.attachment_type.TEXT,
    #         )
    #         logger.info(f"[REG_005] 登录成功: token={token[:20]}..., shopId={shop_id}")
    #     else:
    #         pytest.skip("登录未获取到 token，跳过后续步骤")
    #
    # # ==================== 第六步：进入店铺 ====================
    # @pytest.mark.order(6)
    # @allure.title("REG_006 - 进入店铺")
    # def test_step6_enter_shop(self, admin_api_client, db):
    #     """
    #     通过 SQL 查询用户ID和最新shopId，调用 changeLogin 接口进入店铺。
    #     SQL1: SELECT id FROM llxz_user.ct_backstage_user WHERE name = userNameReq
    #     SQL2: SELECT shop_id FROM llxz_product.ct_shop ORDER BY create_time DESC LIMIT 1
    #     """
    #     if not self._login_token:
    #         pytest.skip("步骤5未获取到登录token，跳过进入店铺")
    #
    #     case = get_test_data(_DATA_FILE, "step6_enter_shop")
    #     global_vars = self._load_global_vars()
    #
    #     # 注入动态变量
    #     global_vars["user_name_req"] = self._user_name_req
    #
    #     # 使用登录获取的 token 更新会话认证
    #     admin_api_client.session.headers["token"] = self._login_token
    #
    #     allure.dynamic.title(f"{case['step_id']} | {case['title']}")
    #     execute_test_case(case, admin_api_client, db, global_vars)
    #     logger.info("[REG_006] 进入店铺成功")
