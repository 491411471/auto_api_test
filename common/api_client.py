
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
    """

    def __init__(
        self, 
        base_url: str, 
        auth_type: Optional[str] = None, 
        auth_config: Optional[Dict[str, Any]] = None, 
        timeout: int = 60, 
        max_retries: int = 3, 
        request_interval: float = 1.0
    ) -> None:
        logger.info("实际值和期望值输出....")
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.request_interval = request_interval  # 请求间隔时间（秒）
        self.session = requests.Session()
        self._last_request_time = 0.0  # 上次请求时间戳

        # 配置认证
        if auth_type == 'api_token' and auth_config:
            # 兼容两种配置格式：
            # 1. {'key': 'Token', 'value': 'xxx'}
            # 2. {'token': 'xxx'}
            if 'token' in auth_config:
                # 格式2: {'token': 'xxx'}，默认使用 'Token' 作为 header key
                header_key = auth_config.get('key', 'token')
                self.session.headers.update({header_key: auth_config['token']})
            else:
                # 格式1: {'key': 'Token', 'value': 'xxx'}
                self.session.headers.update({auth_config.get('key', 'Token'): auth_config['value']})
        elif auth_type == 'bearer' and auth_config:
            self.session.headers.update({'Authorization': f"Bearer {auth_config['token']}"})
        elif auth_type == 'basic' and auth_config:
            self.session.auth = HTTPBasicAuth(auth_config['username'], auth_config['password'])

        logger.info(f"API客户端初始化 | base_url={self.base_url} | auth_type={auth_type} | timeout={timeout} | headers={self.session.headers}")

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
                logger.info(f"请求参数：{kwargs}")
                logger.info(f"请求方法：{method}")
                logger.info(f"请求URL：{url}")
                logger.info(f"请求超时设置: {self.timeout}秒 (尝试 {attempt+1}/{self.max_retries})")
                
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
                self._log_response(resp)
                resp.raise_for_status()
                
                # 检查响应是否包含"连续点击"错误
                try:
                    response_json = resp.json()
                    error_message = response_json.get('errorMessage', '')
                    if '请不要连续点击' in str(error_message):
                        logger.warning(f"检测到'连续点击'错误")
                        if attempt < self.max_retries - 1:
                            wait_time = 3 * (attempt + 1)  # 递增等待时间：3秒、6秒、9秒
                            logger.warning(f"等待 {wait_time} 秒后重试 (尝试 {attempt+1}/{self.max_retries})")
                            time.sleep(wait_time)
                            # 更新最后请求时间，确保下次请求有足够的间隔
                            self._last_request_time = time.time() - self.request_interval
                            continue  # 继续重试
                        else:
                            logger.error(f"重试{self.max_retries}次后仍然收到'连续点击'错误")
                            # 返回响应，让测试断言失败
                            return resp
                except:
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