# utils/captcha_repayment_helper.py
"""
验证码 + 业务提交 通用助手

适用场景：需要先获取短信验证码（OCR 识别图片验证码后触发），
再携带验证码提交业务请求，若验证码过期则整体重试的流程。

典型用例：部分还款（销账）、需要验证码的其他操作类接口。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import allure
import yaml

from common.logger import logger


# ==================== 结果数据类 ====================

@dataclass
class CaptchaSubmitResult:
    """验证码提交结果"""
    success: bool                          # 业务是否成功（businessSuccess == True）
    response_json: Optional[Dict] = None   # 业务接口响应体
    code: Optional[str] = None             # 最终使用的验证码
    attempt: int = 0                       # 第几次尝试成功（从1开始，0表示全部失败）
    logs: List[str] = field(default_factory=list)  # 各次尝试的日志摘要

    @property
    def error_message(self) -> str:
        if self.response_json:
            return self.response_json.get('errorMessage') or ''
        return ''


# ==================== 核心公共函数 ====================

def submit_with_captcha(
    api_client,
    captcha_endpoint: str,
    captcha_body: Dict[str, Any],
    repay_endpoint: str,
    repay_body: Dict[str, Any],
    max_retries: int = 3,
    request_interval: float = 0.5,
    step_label: str = "验证码+提交",
) -> CaptchaSubmitResult:
    """
    获取验证码(OCR识别) + 提交业务请求（验证码过期自动整体重试）

    流程：
      1. POST 请求验证码图片接口
      2. ddddocr 识别图片验证码
      3. 将验证码注入 repay_body['verifyCode'] 并立即提交
      4. 若响应含"验证码无效/已过期"，重新从步骤1开始重试
      5. 非验证码类业务失败则不重试，直接返回

    Args:
        api_client:       API客户端（需有 post 方法和 request_interval 属性）
        captcha_endpoint: 验证码图片接口路径，如 "/hzsx/user/getVerificationCodeWithMobile"
        captcha_body:     验证码请求体，如 {"mobile": "...", "clientType": "SHOP"}
        repay_endpoint:   业务接口路径，如 "/hzsx/ope/order/partialRepaymentV3"
        repay_body:       业务请求体（verifyCode 字段会自动填充，无需预填）
        max_retries:      最大重试次数（默认3次）
        request_interval: 临时请求间隔秒数（验证码有效期短，需缩短间隔，默认0.5s）
        step_label:       allure step 标题前缀，便于区分不同场景

    Returns:
        CaptchaSubmitResult 对象，包含 success、response_json、code、attempt、logs

    Raises:
        ImportError: ddddocr 未安装时由调用方处理（建议在调用前预检）
    """
    import ddddocr
    ocr = ddddocr.DdddOcr(show_ad=False)

    # 保存并临时缩短请求间隔（验证码有效期短，需快速提交）
    original_interval = getattr(api_client, 'request_interval', None)
    if original_interval is not None:
        api_client.request_interval = request_interval

    result = CaptchaSubmitResult(success=False)

    try:
        for attempt in range(1, max_retries + 1):
            with allure.step(f"{step_label} 第{attempt}/{max_retries}次"):

                # ---- 1. 请求验证码图片 ----
                try:
                    captcha_resp = api_client.post(captcha_endpoint, json=captcha_body)
                except Exception as e:
                    result.logs.append(f"第{attempt}次: 验证码请求异常 - {e}")
                    allure.attach(f"请求异常: {e}",
                                  name=f"第{attempt}次-验证码请求失败",
                                  attachment_type=allure.attachment_type.TEXT)
                    continue

                if captcha_resp.status_code != 200:
                    result.logs.append(f"第{attempt}次: 验证码HTTP={captcha_resp.status_code}")
                    allure.attach(
                        f"HTTP状态码: {captcha_resp.status_code}\n响应体: {captcha_resp.text[:500]}",
                        name=f"第{attempt}次-验证码响应异常",
                        attachment_type=allure.attachment_type.TEXT)
                    continue

                content_type = captcha_resp.headers.get('Content-Type', '').lower()
                resp_len = len(captcha_resp.content)
                if 'image' not in content_type and resp_len < 100:
                    result.logs.append(f"第{attempt}次: 非图片响应 (Content-Type={content_type})")
                    allure.attach(
                        f"Content-Type: {content_type}\n响应体: {captcha_resp.text[:500]}",
                        name=f"第{attempt}次-非图片响应",
                        attachment_type=allure.attachment_type.TEXT)
                    continue

                # ---- 2. OCR 识别验证码 ----
                try:
                    raw_code = ocr.classification(captcha_resp.content)
                except Exception as e:
                    result.logs.append(f"第{attempt}次: OCR异常 - {type(e).__name__}: {e}")
                    allure.attach(captcha_resp.content,
                                  name=f"第{attempt}次-验证码原图",
                                  attachment_type=allure.attachment_type.PNG)
                    allure.attach(f"OCR异常: {type(e).__name__}: {e}",
                                  name=f"第{attempt}次-OCR失败",
                                  attachment_type=allure.attachment_type.TEXT)
                    continue

                if not raw_code or len(raw_code.strip()) < 4:
                    result.logs.append(f"第{attempt}次: OCR结果异常 '{raw_code}'")
                    allure.attach(captcha_resp.content,
                                  name=f"第{attempt}次-验证码原图",
                                  attachment_type=allure.attachment_type.PNG)
                    allure.attach(f"OCR返回: '{raw_code}' (不足4位)",
                                  name=f"第{attempt}次-OCR结果异常",
                                  attachment_type=allure.attachment_type.TEXT)
                    continue

                code = raw_code.strip()
                allure.attach(captcha_resp.content,
                              name=f"第{attempt}次-验证码={code}",
                              attachment_type=allure.attachment_type.PNG)
                logger.info(f"第{attempt}次验证码识别成功: '{code}'")

                # ---- 3. 立即提交业务请求（无间隔延迟） ----
                current_body = repay_body.copy()
                current_body['verifyCode'] = code
                allure.attach(
                    f"POST {repay_endpoint}\n\n"
                    f"{yaml.dump(current_body, allow_unicode=True, default_flow_style=False)}",
                    name=f"第{attempt}次-请求参数",
                    attachment_type=allure.attachment_type.TEXT)

                resp = api_client.post(repay_endpoint, json=current_body)
                resp_json = resp.json()
                print(f"第{attempt}次业务响应: {resp_json}")
                logger.info(f"第{attempt}次业务响应: {resp_json}")
                allure.attach(str(resp_json), name=f"第{attempt}次-业务响应", attachment_type=allure.attachment_type.JSON)
                error_msg = resp_json.get('errorMessage') or ''

                # 验证码过期/无效 → 整体重试
                if '验证码无效' in error_msg or '验证码已过期' in error_msg:
                    result.logs.append(f"第{attempt}次: 验证码过期 (code={code}, error={error_msg})")
                    allure.attach(
                        f"验证码: '{code}'\n错误信息: {error_msg}\n→ 将重新获取验证码并重试",
                        name=f"第{attempt}次-验证码过期，准备重试",
                        attachment_type=allure.attachment_type.TEXT)
                    logger.warning(f"第{attempt}次验证码过期: {error_msg}")
                    continue

                # 其他业务失败 → 不重试，直接返回
                if resp_json.get('businessSuccess') is not True:
                    result.logs.append(f"第{attempt}次: 业务失败 ({error_msg})")
                    result.response_json = resp_json
                    result.code = code
                    result.attempt = attempt
                    result.success = False
                    break

                # 业务成功
                allure.attach(
                    f"验证码: '{code}'\nbusinessSuccess: True",
                    name=f"第{attempt}次-提交成功",
                    attachment_type=allure.attachment_type.TEXT)
                logger.info(f"第{attempt}次提交成功: code='{code}'")
                result.response_json = resp_json
                result.code = code
                result.attempt = attempt
                result.success = True
                break

    finally:
        # 恢复原始请求间隔
        if original_interval is not None:
            api_client.request_interval = original_interval

    return result


def require_ddddocr():
    """
    预检 ddddocr 是否已安装。
    未安装时调用 pytest.skip，已安装则返回 OCR 实例。
    供测试文件在流程开始前调用，避免在重试循环中反复 ImportError。
    """
    import pytest
    try:
        import ddddocr  # noqa: F401
    except ImportError:
        skip_msg = ("ddddocr 未安装，无法识别验证码\n"
                    "请执行: pip install ddddocr>=1.4.0"
        )
        allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
        logger.warning(skip_msg)
        pytest.skip(skip_msg)
