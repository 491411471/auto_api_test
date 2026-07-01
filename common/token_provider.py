# common/token_provider.py
"""
动态 Token 获取器
通过调用登录接口 /hzsx/user/loginV2 获取最新 token，session 级别缓存。
"""
import threading
import time

import allure
import requests

from common.logger import logger


class TokenProvider:
    """通过登录接口动态获取 token，按 cache_key 缓存"""
    _cache = {}  # {cache_key: token_string}
    _lock = threading.RLock()  # 保护 _cache 的读写操作，防止并发竞态

    # endpoint 到 cache_key 的映射（供 APIClient._refresh_token 精准失效使用）
    ENDPOINT_CACHE_KEY_MAP = {
        "merchant": "SHOP",
        "admin": "OPE",
        "xianyu": "XIANYU",
    }

    @classmethod
    def get_token(cls, base_url: str, user_type: str, login_config: dict) -> str:
        """调用登录接口获取 token（兼容旧接口，缓存 key 默认使用 user_type）"""
        return cls.get_token_with_key(base_url, user_type, login_config, cache_key=user_type)

    @classmethod
    def get_token_with_key(cls, base_url: str, user_type: str, login_config: dict, cache_key: str = None) -> str:
        """
        调用登录接口获取 token（支持自定义缓存 key，避免不同登录参数冲突）

        Args:
            base_url: 环境基础 URL，如 "https://test.llxzu.com"
            user_type: 用户类型，"SHOP"（商家端）或 "OPE"（运营端）
            login_config: 端级登录配置字典，包含：
                - mobile: 登录手机号
                - smsLoginVerifyCode: 短信验证码
                - loginTimestamp: 登录时间戳（商家端和运营端不同）
                - source: 可选，商家端传 "SHOP"，运营端不传
                - useVersion: 可选，默认 2
            cache_key: 缓存 key，默认使用 user_type

        Returns:
            token 字符串

        Raises:
            RuntimeError: 登录失败或返回数据异常时抛出
        """
        cache_key = cache_key or user_type

        with cls._lock:
            if cache_key in cls._cache:
                logger.info(f"[Token] 使用缓存 token ({cache_key}): {cls._cache[cache_key][:10]}...")
                return cls._cache[cache_key]

        # 登录操作在锁外执行（避免长时间持锁），但通过双重检查保证线程安全
        token = cls._do_login(base_url, user_type, login_config, cache_key)
        return token

    @classmethod
    def _do_login(cls, base_url: str, user_type: str, login_config: dict, cache_key: str) -> str:
        """执行登录请求并缓存 token（带重试机制）"""
        url = f"{base_url.rstrip('/')}/hzsx/user/loginV2"
        body = {
            "userType": user_type,
            "mobile": login_config.get("mobile", "13811680671"),
            "smsLoginVerifyCode": login_config.get("smsLoginVerifyCode", "1"),
            "loginTimestamp": login_config.get("loginTimestamp"),
            "useVersion": login_config.get("useVersion", 2),
        }
        if login_config.get("source"):
            body["source"] = login_config["source"]

        last_error = None
        max_login_retries = 3
        for login_attempt in range(max_login_retries):
            with allure.step(f"动态获取 {cache_key} Token (尝试 {login_attempt + 1}/{max_login_retries})"):
                logger.info(f"[Token] 调用登录接口获取 {cache_key} token: {url}")
                allure.attach(
                    f"POST {url}\nuserType={user_type}\nmobile={body['mobile']}",
                    name="登录请求",
                    attachment_type=allure.attachment_type.TEXT
                )

                try:
                    resp = requests.post(url, json=body, timeout=120)
                except Exception as e:
                    last_error = RuntimeError(f"[Token] 登录请求异常 ({cache_key}): {e}")
                    if login_attempt < max_login_retries - 1:
                        wait = 2 ** login_attempt
                        logger.warning(f"[Token] 登录请求异常，{wait}s 后重试: {e}")
                        time.sleep(wait)
                        continue
                    raise last_error

                resp_json = resp.json()
                allure.attach(
                    str(resp_json),
                    name=f"登录响应 ({cache_key})",
                    attachment_type=allure.attachment_type.JSON
                )

                if resp.status_code != 200:
                    last_error = RuntimeError(
                        f"[Token] 登录接口 HTTP 异常 ({cache_key}): status={resp.status_code}"
                    )
                    if login_attempt < max_login_retries - 1:
                        wait = 2 ** login_attempt
                        logger.warning(f"[Token] HTTP {resp.status_code}，{wait}s 后重试")
                        time.sleep(wait)
                        continue
                    raise last_error

                data = resp_json.get("data")
                token = None
                if data:
                    if isinstance(data, str):
                        token = data
                    elif isinstance(data, dict):
                        token = data.get("token") or data.get("accessToken") or data.get("access_token")

                if token:
                    with cls._lock:
                        cls._cache[cache_key] = token
                    logger.info(f"[Token] {cache_key} token 获取成功: {token[:16]}...")
                    allure.attach(
                        f"{cache_key} token: {token[:16]}...",
                        name="Token 获取成功",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    return token

                # token 提取失败
                error_msg = resp_json.get("errorMessage") or "未知错误"
                last_error = RuntimeError(
                    f"[Token] 登录失败 ({cache_key}): businessSuccess={resp_json.get('businessSuccess')}, "
                    f"errorMessage={error_msg}, data={'exists' if data else 'null'}"
                )
                if login_attempt < max_login_retries - 1:
                    wait = 2 ** login_attempt
                    logger.warning(f"[Token] 登录响应无有效 token，{wait}s 后重试")
                    time.sleep(wait)
                    continue
                raise last_error

        raise last_error

    @classmethod
    def invalidate_token(cls, cache_key: str):
        """
        精准失效指定 cache_key 的 token 缓存（不影响其他端）。
        供 APIClient._refresh_token 在检测到登录失效时调用。
        """
        with cls._lock:
            if cache_key in cls._cache:
                del cls._cache[cache_key]
                logger.info(f"[Token] 已精准失效缓存 ({cache_key})")
            else:
                logger.info(f"[Token] 缓存中无 ({cache_key})，无需清除")

    @classmethod
    def clear_cache(cls, cache_key: str = None):
        """
        清空 token 缓存。
        - 不传 cache_key：清空全部缓存（用于环境切换）
        - 传入 cache_key：精准清除指定 key（等效于 invalidate_token，兼容旧调用）
        """
        with cls._lock:
            if cache_key:
                if cache_key in cls._cache:
                    del cls._cache[cache_key]
                    logger.info(f"[Token] 已清除缓存 ({cache_key})")
            else:
                cls._cache.clear()
                logger.info("[Token] token 缓存已全部清空")
