# -*- coding: utf-8 -*-
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from common.token_provider import TokenProvider


class ConfigManager:
    """统一配置管理器，支持动态切换环境与终端类型"""
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
        self._config = None
        self._load_config()

    def _load_config(self):
        config_path = Path(__file__).parent.parent / "config" / "settings.yaml"
        encodings = ['utf-8-sig', 'utf-8', 'gbk']
        for enc in encodings:
            try:
                with open(config_path, 'r', encoding=enc) as f:
                    self._config = yaml.safe_load(f)
                    return
            except UnicodeDecodeError:
                continue
        raise ValueError(f"无法解析配置文件: {config_path}")

    def _get_active_env(self) -> str:
        """获取当前激活的环境（优先使用环境变量 TEST_ENV）"""
        env = os.environ.get("TEST_ENV")
        if env:
            return env
        return self._config.get("active", "test")

    def _get_active_endpoint(self) -> str:
        """获取当前激活的终端类型（优先使用环境变量 TEST_ENDPOINT）"""
        endpoint = os.environ.get("TEST_ENDPOINT")
        if endpoint:
            return endpoint
        return self._config.get("active_endpoint", "merchant")

    def get_env_config(self, env_name: str = None) -> Dict[str, Any]:
        """获取指定环境的完整配置，若未指定则使用 active 环境"""
        env = env_name or self._get_active_env()
        env_data = self._config.get("environments", {}).get(env)
        if not env_data:
            raise ValueError(f"未知的环境: {env}")
        return env_data

    def get_endpoint_config(self, env_name: str = None, endpoint: str = None) -> Dict[str, Any]:
        """获取指定环境和终端类型的配置"""
        env = env_name or self._get_active_env()
        endpoint_type = endpoint or self._get_active_endpoint()
        env_data = self.get_env_config(env)
        endpoint_data = env_data.get(endpoint_type)
        if not endpoint_data:
            raise ValueError(f"环境 {env} 下未找到终端类型: {endpoint_type}")
        return endpoint_data

    def _resolve_token(self, env_data: Dict, endpoint: str, auth_config: Dict) -> Dict:
        """
        动态解析 token：若 auto_login=true 且端级 login 配置存在，
        则调用登录接口获取最新 token，覆盖硬编码 value。
        """
        if not env_data.get("auto_login", False):
            return auth_config

        # 从端级配置获取 login 参数（merchant.login 或 admin.login）
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

        # endpoint -> userType 映射
        user_type_map = {"merchant": "SHOP", "admin": "OPE"}
        user_type = user_type_map.get(endpoint)
        if not user_type:
            return auth_config

        try:
            dynamic_token = TokenProvider.get_token(base_url, user_type, login_config)
            # 复制一份避免污染原始配置
            auth_config = dict(auth_config)
            auth_config["value"] = dynamic_token
        except Exception as e:
            from common.logger import logger
            logger.warning(
                f"动态获取 {endpoint} token 失败，回退使用配置文件中的硬编码 token: {e}"
            )

        return auth_config

    def get_api_client_config(self, env_name: str = None, endpoint: str = None) -> Dict[str, Any]:
        """返回构建 APIClient 所需的参数字典（支持动态 token）"""
        endpoint_data = self.get_endpoint_config(env_name, endpoint)
        env_data = self.get_env_config(env_name)
        defaults = self._config.get("defaults", {})

        # 动态解析 token（auto_login=true 时自动登录获取）
        auth_config = endpoint_data.get("auth_config") or {}
        auth_config = self._resolve_token(env_data, endpoint or self._get_active_endpoint(), auth_config)

        return {
            "base_url": env_data.get("base_url"),
            "auth_type": endpoint_data.get("auth_type"),
            "auth_config": auth_config,
            "timeout": endpoint_data.get("timeout", defaults.get("timeout", 15)),
            "max_retries": endpoint_data.get("max_retries", defaults.get("max_retries", 3)),
            "request_interval": endpoint_data.get("request_interval", defaults.get("request_interval", 1.0)),
        }

    def get_xianyu_api_client_config(self, env_name: str = None) -> Dict[str, Any]:
        """返回构建闲鱼 APIClient 所需的参数字典（使用 xianyu_token）"""
        merchant_cfg = self.get_api_client_config(env_name, endpoint='merchant')
        xianyu_token = merchant_cfg.get('auth_config', {}).get('xianyu_token')
        return {
            "base_url": merchant_cfg['base_url'],
            "auth_type": 'api_token',
            "auth_config": {'token': xianyu_token},
            "timeout": merchant_cfg.get('timeout', 15),
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