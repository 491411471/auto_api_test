"""
验证码 OCR 识别工具
基于 ddddocr（带带弟弟OCR），支持数字/英文/中文验证码
安装: pip install ddddocr
"""
import logging
import time
from typing import Optional

import allure

logger = logging.getLogger(__name__)

# 单例模式，避免重复初始化（ddddocr 首次加载模型有耗时）
_OCR_INSTANCE = None


def _get_ocr():
    """获取 OCR 单例"""
    global _OCR_INSTANCE
    if _OCR_INSTANCE is None:
        import ddddocr
        _OCR_INSTANCE = ddddocr.DdddOcr(show_ad=False)
        logger.info("ddddocr 验证码识别模型已加载")
    return _OCR_INSTANCE


def recognize_captcha(
    session,
    captcha_url: str,
    referer: str = "",
    max_retries: int = 3
) -> Optional[str]:
    """
    请求验证码图片并 OCR 识别

    Args:
        session: requests.Session（需保持与主接口同一个 session，验证码通常与 session 绑定）
        captcha_url: 验证码图片接口地址
        referer: Referer 头（部分后端会校验，从浏览器 Network 面板获取）
        max_retries: 最大重试次数（偶尔 OCR 识别错误可重试）

    Returns:
        识别出的验证码文本，失败返回 None
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    if referer:
        headers["Referer"] = referer

    for attempt in range(1, max_retries + 1):
        try:
            # 1. 请求验证码图片
            resp = session.get(captcha_url, headers=headers, timeout=10)
            resp.raise_for_status()

            # 2. OCR 识别
            ocr = _get_ocr()
            code = ocr.classification(resp.content)

            # 3. 过滤无效结果
            if not code or len(code) < 1:
                logger.warning(f"第{attempt}次 OCR 结果为空，重试...")
                time.sleep(0.5)
                continue

            logger.info(f"验证码 OCR 识别成功: {code}")
            allure.attach(
                resp.content,
                name=f"验证码-{code}",
                attachment_type=allure.attachment_type.PNG
            )
            return code

        except Exception as e:
            logger.warning(f"第{attempt}次获取验证码失败: {e}")
            if attempt < max_retries:
                time.sleep(1)
            else:
                logger.error(f"验证码获取失败，已达最大重试次数 {max_retries}")
                return None

    return None
