# -*- coding: utf-8 -*-
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


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

    def get_api_client_config(self, env_name: str = None, endpoint: str = None) -> Dict[str, Any]:
        """返回构建 APIClient 所需的参数字典"""
        endpoint_data = self.get_endpoint_config(env_name, endpoint)
        env_data = self.get_env_config(env_name)
        defaults = self._config.get("defaults", {})
        return {
            "base_url": env_data.get("base_url"),
            "auth_type": endpoint_data.get("auth_type"),
            "auth_config": endpoint_data.get("auth_config"),
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