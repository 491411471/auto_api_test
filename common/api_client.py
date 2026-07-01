
import json
import time
from typing import Any, Dict, Optional

import allure
import requests
from requests.auth import HTTPBasicAuth

from common.logger import logger


class APIClient:
    """
    通用 API 客户端
    支持：
      - API Key (headers)
      - Bearer Token
      - Basic Auth
      - 重试策略
      - Allure 步骤记录
      - 详细日志
      - 请求间隔控制（防止连续点击错误）
      - 可配置的响应错误重试模式（retry_patterns）
      - LOGIN_INVALID 自动检测 + token 刷新重试
    """

    # 默认的业务错误重试模式：匹配 errorMessage 中的关键词
    # 扩展时只需在此列表中添加新的模式字符串即可
    DEFAULT_RETRY_PATTERNS = [
        '请不要连续点击',
        '操作频繁',
        '请勿重复点击',
        '正在提交中',
    ]

    # 登录失效检测模式（匹配 code 或 errorMessage/errorMsg）
    LOGIN_INVALID_PATTERNS = [
        'LOGIN_INVALID',
        '重新登录',
        '登录已过期',
        'token已过期',
        'token无效',
        '该账号在别处登录',
        '别处登录',
        '账号被踢下线',
        '登录失效',
        '请重新登录',
    ]

    def __init__(
        self, 
        base_url: str, 
        auth_type: Optional[str] = None, 
        auth_config: Optional[Dict[str, Any]] = None, 
        timeout: int = 60, 
        max_retries: int = 3, 
        request_interval: float = 1.0,
        retry_patterns: Optional[list] = None,
        endpoint: Optional[str] = None,
    ) -> None:
        logger.info("实际值和期望值输出....")
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.request_interval = request_interval  # 请求间隔时间（秒）
        self.retry_patterns = retry_patterns or self.DEFAULT_RETRY_PATTERNS
        self.session = requests.Session()
        self._last_request_time = 0.0  # 上次请求时间戳
        self._endpoint = endpoint  # 终端类型（admin/merchant/xianyu），用于 token 精准刷新
        self._auth_type = auth_type
        self._auth_config = auth_config or {}
        self._token_refresh_count = 0  # token 刷新次数（允许最多 3 次，防止死循环）
        self._max_token_refresh = 3

        # 配置认证
        self._apply_auth(auth_type, auth_config)

    def _apply_auth(self, auth_type, auth_config):
        """应用认证信息到 session headers"""
        if auth_type == 'api_token' and auth_config:
            # 兼容两种配置格式：
            # 1. {'key': 'Token', 'value': 'xxx'}
            # 2. {'token': 'xxx'}
            if 'token' in auth_config:
                header_key = auth_config.get('key', 'token')
                self.session.headers.update({header_key: auth_config['token']})
            else:
                self.session.headers.update({auth_config.get('key', 'Token'): auth_config['value']})
        elif auth_type == 'bearer' and auth_config:
            self.session.headers.update({'Authorization': f"Bearer {auth_config['token']}"})
        elif auth_type == 'basic' and auth_config:
            self.session.auth = HTTPBasicAuth(auth_config['username'], auth_config['password'])

        logger.info(f"API客户端初始化 | base_url={self.base_url} | auth_type={auth_type} | endpoint={self._endpoint} | timeout={self.timeout} | headers={self.session.headers}")

    def _refresh_token(self):
        """
        精准刷新当前 endpoint 的 token：仅失效当前端的缓存 → 重新登录 → 更新 session headers。
        不影响其他端（merchant/admin/xianyu）的有效 token。
        仅当 endpoint 已配置时才能刷新。返回 True 表示刷新成功。
        """
        if not self._endpoint:
            logger.warning("[Token刷新] 未配置 endpoint，无法刷新 token")
            return False

        try:
            from common.token_provider import TokenProvider
            from common.config_manager import config_manager

            # 1. 精准失效当前 endpoint 对应的 token 缓存（不影响其他端）
            cache_key_map = TokenProvider.ENDPOINT_CACHE_KEY_MAP
            cache_key = cache_key_map.get(self._endpoint, self._endpoint)
            TokenProvider.invalidate_token(cache_key)
            logger.info(f"[Token刷新] 已精准失效 {self._endpoint}({cache_key}) 的 token 缓存")

            # 2. 从 config_manager 获取新配置（会触发仅当前端的重新登录）
            if self._endpoint == 'xianyu':
                new_cfg = config_manager.get_xianyu_api_client_config()
            else:
                new_cfg = config_manager.get_api_client_config(endpoint=self._endpoint)
            new_auth_config = new_cfg.get('auth_config', {})

            # 3. 更新 session headers
            self._auth_config = new_auth_config
            self._apply_auth(new_cfg.get('auth_type'), new_auth_config)

            new_token = new_auth_config.get('value') or new_auth_config.get('token', '')
            logger.info(f"[Token刷新] {self._endpoint} token 刷新成功: {new_token[:16]}..." if new_token else f"[Token刷新] {self._endpoint} token 刷新完成")
            allure.attach(
                f"endpoint={self._endpoint}\nnew_token={new_token[:16]}...",
                name="Token 自动刷新",
                attachment_type=allure.attachment_type.TEXT,
            )
            return True
        except Exception as e:
            logger.error(f"[Token刷新] {self._endpoint} token 刷新失败: {e}")
            return False

    def _is_login_invalid(self, response_json: dict) -> bool:
        """检测响应是否为登录失效"""
        # 检查 code 字段（如 {"code": "LOGIN_INVALID"}）
        code = str(response_json.get('code', '') or '')
        # 检查 errorMessage / errorMsg 字段
        error_msg = str(
            response_json.get('errorMessage', '') or
            response_json.get('errorMsg', '') or ''
        )
        combined = f"{code} {error_msg}"
        return any(p in combined for p in self.LOGIN_INVALID_PATTERNS)

    def _log_request(self, method, url, **kwargs):
        logger.debug(f"--> {method} {url}")
        if 'params' in kwargs and kwargs['params']:
            logger.debug(f"    Params: {kwargs['params']}")
        if 'json' in kwargs and kwargs['json']:
            logger.debug(f"    JSON: {json.dumps(kwargs['json'], ensure_ascii=False)[:500]}")
        if 'data' in kwargs and kwargs['data']:
            logger.debug(f"    Data: {kwargs['data']}")

    def _log_response(self, response):
        logger.debug(f"<-- {response.status_code} {response.reason} ({response.elapsed.total_seconds():.3f}s)")
        try:
            body = response.json()
            logger.debug(f"    Body: {json.dumps(body, ensure_ascii=False)[:500]}")
        except:
            logger.debug(f"    Body: {response.text[:500]}")

    def _request_with_retry(self, method, url, **kwargs):
        # 控制请求间隔，防止触发"连续点击"限制
        if self.request_interval > 0:
            current_time = time.time()
            time_since_last_request = current_time - self._last_request_time
            if time_since_last_request < self.request_interval:
                sleep_time = self.request_interval - time_since_last_request
                logger.debug(f"等待 {sleep_time:.2f} 秒以满足请求间隔要求")
                time.sleep(sleep_time)
            self._last_request_time = time.time()

        last_exception = None
        for attempt in range(self.max_retries):
            try:
                self._log_request(method, url, **kwargs)
                # 格式化输出请求参数为标准JSON格式
                try:
                    logger.info(f"请求参数：\n{json.dumps(kwargs, indent=2, ensure_ascii=False, default=str)}")
                except Exception:
                    logger.info(f"请求参数：{kwargs}")
                logger.info(f"请求方法：{method}")
                logger.info(f"请求URL：{url}")
                logger.info(f"请求超时设置: {self.timeout}秒 (尝试 {attempt+1}/{self.max_retries})")
                
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
                self._log_response(resp)
                resp.raise_for_status()
                
                # 记录接口返回结果（限制600字符）
                try:
                    response_body = resp.text
                    if len(response_body) > 600:
                        logger.info(f"接口返回结果：{response_body[:1000]}")
                    else:
                        logger.info(f"接口返回结果：{response_body}")
                except Exception as e:
                    logger.debug(f"记录响应日志时出错: {e}")
                
                # 检查响应是否包含可重试的业务错误
                try:
                    response_json = resp.json()
                    error_message = str(response_json.get('errorMessage', '') or '')

                    # —— 优先检测登录失效 ——
                    if self._is_login_invalid(response_json) and self._token_refresh_count < self._max_token_refresh:
                        error_detail = response_json.get('code', '') or response_json.get('errorMsg', '')
                        logger.warning(f"[Token刷新] 检测到登录失效: {error_detail}，尝试精准刷新 {self._endpoint} token (第{self._token_refresh_count+1}次)")
                        if self._refresh_token():
                            self._token_refresh_count += 1
                            self._last_request_time = time.time() - self.request_interval
                            continue  # 用新 token 重试
                        else:
                            logger.error("[Token刷新] token 刷新失败，返回原始响应")
                            return resp

                    # —— 常规业务错误重试（限流等）——
                    matched_pattern = next(
                        (p for p in self.retry_patterns if p in error_message), None
                    )
                    if matched_pattern:
                        logger.warning(f"检测到业务错误: '{error_message}' (匹配模式: '{matched_pattern}')")
                        if attempt < self.max_retries - 1:
                            wait_time = 3 * (attempt + 1)  # 递增等待：3s, 6s, 9s
                            logger.warning(f"等待 {wait_time} 秒后重试 (尝试 {attempt+1}/{self.max_retries})")
                            time.sleep(wait_time)
                            self._last_request_time = time.time() - self.request_interval
                            continue
                        else:
                            logger.error(f"重试{self.max_retries}次后仍然收到业务错误: '{error_message}'")
                            return resp
                except (ValueError, AttributeError):
                    pass
                
                return resp
            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.error(f"请求超时 (尝试 {attempt+1}/{self.max_retries}): {method} {url}, 超时设置: {self.timeout}秒, 错误: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = 5 * (attempt + 1)  # 超时后等待更长时间：5秒、10秒、15秒
                    logger.warning(f"超时后等待 {wait_time} 秒后重试")
                    time.sleep(wait_time)
                else:
                    logger.error(f"请求最终超时，已重试{self.max_retries}次: {method} {url}")
                    raise
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                logger.error(f"连接错误 (尝试 {attempt+1}/{self.max_retries}): {method} {url}, 错误: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = 3 * (attempt + 1)
                    logger.warning(f"等待 {wait_time} 秒后重试")
                    time.sleep(wait_time)
                else:
                    logger.error(f"连接错误，已重试{self.max_retries}次: {method} {url}")
                    raise
            except Exception as e:
                last_exception = e
                if attempt == self.max_retries - 1:
                    logger.error(f"请求最终失败: {method} {url}, 错误: {e}")
                    raise
                wait = 2 ** attempt
                logger.warning(f"请求失败，{wait}秒后重试 (尝试 {attempt+1}/{self.max_retries})")
                time.sleep(wait)

    # 公开方法
    def get(self, path: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> requests.Response:
        """
        发送 GET 请求
        
        Args:
            path: 请求路径
            params: URL 查询参数
            **kwargs: 其他请求参数
            
        Returns:
            响应对象
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        """
        在报告中生成一个可折叠的步骤块，标题为 "GET http://xxx"，点击可展开查看该步骤内部的详细内容（如请求参数、响应、断言等）
        附加附件：可以在步骤内使用 allure.attach() 添加请求体、响应体、截图等，这些附件会挂在该步骤下
        失败定位：如果步骤内的断言失败，Allure 报告会明确标记是哪个步骤出错，方便快速定位问题。
        """
        with allure.step(f"GET {url}"):
            return self._request_with_retry('GET', url, params=params, **kwargs)

    def post(self, path: str, json: Optional[Dict[str, Any]] = None, data: Optional[Any] = None, **kwargs: Any) -> requests.Response:
        """发送 POST 请求"""
        url = f"{self.base_url}/{path.lstrip('/')}"
        with allure.step(f"POST {url}"):
            return self._request_with_retry('POST', url, json=json, data=data, **kwargs)

    def put(self, path: str, json: Optional[Dict[str, Any]] = None, data: Optional[Any] = None, **kwargs: Any) -> requests.Response:
        """发送 PUT 请求"""
        url = f"{self.base_url}/{path.lstrip('/')}"
        with allure.step(f"PUT {url}"):
            return self._request_with_retry('PUT', url, json=json, data=data, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        """发送 DELETE 请求"""
        url = f"{self.base_url}/{path.lstrip('/')}"
        with allure.step(f"DELETE {url}"):
            return self._request_with_retry('DELETE', url, **kwargs)