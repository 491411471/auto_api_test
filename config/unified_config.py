# -*- coding: utf-8 -*-
"""
统一配置管理器
整合 YAML 配置和环境变量配置，提供统一的配置访问接口
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional, List
import yaml
from dotenv import load_dotenv

from common.logger import logger


class UnifiedConfig:
    """统一配置管理器"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._yaml_config = None
        self._env_config = {}
        
        # 加载配置
        self._load_env_config()
        self._load_yaml_config()
        
        logger.info("统一配置管理器初始化完成")
    
    def _load_env_config(self):
        """加载环境变量配置"""
        # 加载 .env 文件
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logger.debug(f"已加载环境变量文件: {env_path}")
        
        # 读取环境变量
        self._env_config = {
            "database": {
                "host": os.getenv("DB_HOST"),
                "port": int(os.getenv("DB_PORT", "3306")),
                "user": os.getenv("DB_USER"),
                "password": os.getenv("DB_PASSWORD"),
                "charset": os.getenv("DB_CHARSET", "utf8mb4")
            },
            "wechat": {
                "webhook": os.getenv("WECHAT_WEBHOOK"),
                "userids": os.getenv("WECHAT_USERIDS", "").split(",") if os.getenv("WECHAT_USERIDS") else []
            },
            "report": {
                "http_base": os.getenv("HTTP_REPORT_BASE", "http://localhost/")
            },
            "test": {
                "env": os.getenv("TEST_ENV"),
                "endpoint": os.getenv("TEST_ENDPOINT")
            }
        }
        
        logger.debug("环境变量配置加载完成")
    
    def _load_yaml_config(self):
        """加载 YAML 配置文件"""
        config_path = Path(__file__).parent / "settings.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        encodings = ['utf-8-sig', 'utf-8', 'gbk']
        for enc in encodings:
            try:
                with open(config_path, 'r', encoding=enc) as f:
                    self._yaml_config = yaml.safe_load(f)
                logger.debug(f"YAML 配置加载完成: {config_path}")
                return
            except UnicodeDecodeError:
                continue
        
        raise ValueError(f"无法解析配置文件: {config_path}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值，支持点分隔路径
        
        Args:
            key_path: 配置键路径，如 "database.host" 或 "environments.test.base_url"
            default: 默认值
        
        Returns:
            配置值
        
        Example:
            >>> config.get("database.host")
            'lxztestmysqlpldb.rwlb.rds.aliyuncs.com'
            >>> config.get("environments.test.base_url")
            'https://test.llxzu.com'
        """
        keys = key_path.split('.')
        
        # 优先从环境变量配置查找
        value = self._get_nested_value(self._env_config, keys)
        if value is not None:
            return value
        
        # 从 YAML 配置查找
        value = self._get_nested_value(self._yaml_config, keys)
        if value is not None:
            return value
        
        return default
    
    def _get_nested_value(self, data: Dict, keys: List[str]) -> Any:
        """从嵌套字典中获取值"""
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
    
    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        db_config = self._env_config.get("database", {})
        
        # 验证必要配置
        if not db_config.get("password"):
            raise ValueError(
                "未配置数据库密码！\n"
                "请执行以下步骤：\n"
                "1. 复制 .env.example 为 .env\n"
                "2. 在 .env 文件中填入 DB_PASSWORD\n"
                "3. 重新运行测试"
            )
        
        return db_config
    
    def get_wechat_config(self) -> Dict[str, Any]:
        """获取企业微信配置"""
        return self._env_config.get("wechat", {})
    
    def get_environment_config(self, env_name: Optional[str] = None) -> Dict[str, Any]:
        """获取指定环境的配置"""
        # 优先使用环境变量
        if not env_name:
            env_name = self._env_config.get("test", {}).get("env")
        
        if not env_name:
            env_name = self._yaml_config.get("active", "test")
        
        env_data = self._yaml_config.get("environments", {}).get(env_name)
        if not env_data:
            raise ValueError(f"未知的环境: {env_name}")
        
        return env_data
    
    def get_endpoint_config(self, env_name: Optional[str] = None, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """获取指定环境和终端的配置"""
        env_config = self.get_environment_config(env_name)
        
        if not endpoint:
            endpoint = self._env_config.get("test", {}).get("endpoint")
        
        if not endpoint:
            endpoint = self._yaml_config.get("active_endpoint", "merchant")
        
        endpoint_data = env_config.get(endpoint)
        if not endpoint_data:
            raise ValueError(f"环境 {env_config} 下未找到终端类型: {endpoint}")
        
        return endpoint_data
    
    def validate(self) -> bool:
        """验证配置完整性"""
        missing = []
        
        # 检查数据库配置
        if not self._env_config.get("database", {}).get("password"):
            missing.append("DB_PASSWORD")
        
        if missing:
            logger.error(f"配置验证失败，缺少: {', '.join(missing)}")
            return False
        
        logger.info("配置验证通过")
        return True
    
    def reload(self):
        """重新加载配置（用于热更新）"""
        self._initialized = False
        self.__init__()
        logger.info("配置已重新加载")


# 全局单例
config = UnifiedConfig()
