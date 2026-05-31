# -*- coding: utf-8 -*-
"""
API 客户端配置管理器
基于统一配置管理器，提供 APIClient 所需的配置参数
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from common.token_provider import TokenProvider
from config.unified_config import config as unified_config
from common.logger import logger


class ConfigManager:
    """API 客户端配置管理器（兼容旧接口，基于统一配置）"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        logger.info("ConfigManager 初始化完成（基于统一配置）")

    def _get_active_env(self) -> str:
        """获取当前激活的环境"""
        # 优先使用环境变量
        env = os.environ.get("TEST_ENV")
        if env:
            return env
        
        # 从统一配置获取
        return unified_config.get("active", "test")

    def _get_active_endpoint(self) -> str:
        """获取当前激活的终端类型"""
        endpoint = os.environ.get("TEST_ENDPOINT")
        if endpoint:
            return endpoint
        
        return unified_config.get("active_endpoint", "merchant")

    def get_env_config(self, env_name: str = None) -> Dict[str, Any]:
        """获取指定环境的完整配置"""
        return unified_config.get_environment_config(env_name)

    def get_endpoint_config(self, env_name: str = None, endpoint: str = None) -> Dict[str, Any]:
        """获取指定环境和终端类型的配置"""
        return unified_config.get_endpoint_config(env_name, endpoint)

    def _resolve_token(self, env_data: Dict, endpoint: str, auth_config: Dict) -> Dict:
        """动态解析 token"""
        if not env_data.get("auto_login", False):
            return auth_config

        try:
            endpoint_data = self.get_endpoint_config(env_name=None, endpoint=endpoint)
        except ValueError:
            return auth_config

        login_config = endpoint_data.get("login")
        if not login_config:
            return auth_config

        base_url = env_data.get("base_url")
        if not base_url:
            return auth_config

        user_type_map = {"merchant": "SHOP", "admin": "OPE"}
        user_type = user_type_map.get(endpoint)
        if not user_type:
            return auth_config

        try:
            dynamic_token = TokenProvider.get_token(base_url, user_type, login_config)
            auth_config = dict(auth_config)
            auth_config["value"] = dynamic_token
        except Exception as e:
            logger.warning(
                f"动态获取 {endpoint} token 失败，回退使用配置文件中的硬编码 token: {e}"
            )

        return auth_config

    def get_api_client_config(self, env_name: str = None, endpoint: str = None) -> Dict[str, Any]:
        """返回构建 APIClient 所需的参数字典"""
        endpoint_data = self.get_endpoint_config(env_name, endpoint)
        env_data = self.get_env_config(env_name)
        
        # 从统一配置获取默认值
        defaults = {
            "timeout": unified_config.get("defaults.timeout", 60),
            "max_retries": unified_config.get("defaults.max_retries", 3),
            "request_interval": unified_config.get("defaults.request_interval", 1.0)
        }

        # 动态解析 token
        auth_config = endpoint_data.get("auth_config") or {}
        auth_config = self._resolve_token(env_data, endpoint or self._get_active_endpoint(), auth_config)

        return {
            "base_url": env_data.get("base_url"),
            "auth_type": endpoint_data.get("auth_type"),
            "auth_config": auth_config,
            "timeout": endpoint_data.get("timeout", defaults["timeout"]),
            "max_retries": endpoint_data.get("max_retries", defaults["max_retries"]),
            "request_interval": endpoint_data.get("request_interval", defaults["request_interval"]),
        }

    def get_xianyu_api_client_config(self, env_name: str = None) -> Dict[str, Any]:
        """返回构建闲鱼 APIClient 所需的参数字典"""
        merchant_cfg = self.get_api_client_config(env_name, endpoint='merchant')
        xianyu_token = merchant_cfg.get('auth_config', {}).get('xianyu_token')
        return {
            "base_url": merchant_cfg['base_url'],
            "auth_type": 'api_token',
            "auth_config": {'token': xianyu_token},
            "timeout": merchant_cfg.get('timeout', 60),
            "max_retries": merchant_cfg.get('max_retries', 3),
            "request_interval": merchant_cfg.get('request_interval', 1.0),
        }

    @property
    def current_env(self) -> str:
        return self._get_active_env()

    @property
    def current_endpoint(self) -> str:
        return self._get_active_endpoint()


# 全局单例
config_manager = ConfigManager()