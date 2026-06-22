# common/token_provider.py
"""
动态 Token 获取器
通过调用登录接口 /hzsx/user/loginV2 获取最新 token，session 级别缓存。
"""
import allure
import requests

from common.logger import logger


class TokenProvider:
    """通过登录接口动态获取 token，按 userType 缓存"""
    _cache = {}  # {user_type: token_string}

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
        if cache_key in cls._cache:
            logger.info(f"[Token] 使用缓存 token ({cache_key}): {cls._cache[cache_key][:10]}...")
            return cls._cache[cache_key]

        url = f"{base_url.rstrip('/')}/hzsx/user/loginV2"
        body = {
            "userType": user_type,
            "mobile": login_config.get("mobile", "13811680671"),
            "smsLoginVerifyCode": login_config.get("smsLoginVerifyCode", "1"),
            "loginTimestamp": login_config.get("loginTimestamp"),
            "useVersion": login_config.get("useVersion", 2),
        }
        # source 仅商家端（SHOP）需要，运营端（OPE）不传
        if login_config.get("source"):
            body["source"] = login_config["source"]

        with allure.step(f"动态获取 {cache_key} Token"):
            logger.info(f"[Token] 调用登录接口获取 {cache_key} token: {url}")
            allure.attach(
                f"POST {url}\nuserType={user_type}\nmobile={body['mobile']}",
                name="登录请求",
                attachment_type=allure.attachment_type.TEXT
            )

            try:
                resp = requests.post(url, json=body, timeout=120)
            except Exception as e:
                raise RuntimeError(f"[Token] 登录请求异常 ({cache_key}): {e}")

            resp_json = resp.json()
            allure.attach(
                str(resp_json),
                name=f"登录响应 ({cache_key})",
                attachment_type=allure.attachment_type.JSON
            )

            if resp.status_code != 200:
                raise RuntimeError(
                    f"[Token] 登录接口 HTTP 异常 ({cache_key}): status={resp.status_code}"
                )

            # 特殊处理：登录接口可能 businessSuccess=False 但 data 中仍有有效 token
            # 优先尝试提取 token，提取成功即视为登录成功
            data = resp_json.get("data")
            token = None
            if data:
                if isinstance(data, str):
                    token = data
                elif isinstance(data, dict):
                    token = data.get("token") or data.get("accessToken") or data.get("access_token")

            if token:
                cls._cache[cache_key] = token
                logger.info(f"[Token] {cache_key} token 获取成功: {token[:16]}...")
                allure.attach(
                    f"{cache_key} token: {token[:16]}...",
                    name="Token 获取成功",
                    attachment_type=allure.attachment_type.TEXT
                )
                return token

            # token 无效，抛出异常
            error_msg = resp_json.get("errorMessage") or "未知错误"
            raise RuntimeError(
                f"[Token] 登录失败 ({cache_key}): businessSuccess={resp_json.get('businessSuccess')}, "
                f"errorMessage={error_msg}, data={'exists' if data else 'null'}"
            )

    @classmethod
    def clear_cache(cls):
        """清空 token 缓存（用于环境切换或 token 过期场景）"""
        cls._cache.clear()
        logger.info("[Token] token 缓存已清空")
