# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path for IDE/direct python imports and pytest runs
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from common.api_client import APIClient
from common.config_manager import config_manager
from common.database import DatabaseManager
from common.logger import logger
from config.config import DW_DB_CONFIG


def pytest_addoption(parser):
    """添加命令行选项，允许临时覆盖环境和终端类型"""
    parser.addoption("--env", action="store", default=None,
                     help="临时指定测试环境（如 test, prod），覆盖配置文件中的 active")
    parser.addoption("--endpoint", action="store", default=None,
                     help="临时指定终端类型（如 merchant, admin），覆盖配置文件中的 active_endpoint")


@pytest.fixture(scope="session", autouse=True)
def apply_cli_overrides(request):
    """在测试会话开始时，将命令行参数写入环境变量，使 config_manager 能够感知"""
    env = request.config.getoption("--env")
    endpoint = request.config.getoption("--endpoint")
    if env:
        os.environ["TEST_ENV"] = env
    if endpoint:
        os.environ["TEST_ENDPOINT"] = endpoint
    # 刷新配置重新读取环境变量
    # 由于 config_manager 是单例且已初始化，这里强制重新加载环境变量即可，
    # 无需重新读取文件。直接调用其内部方法即可。
    # 注意：不会在此处修改 _initialized，只是下次调用 get_* 时会使用新的环境变量。
    logger.info(f"当前测试环境: {config_manager.current_env}, 终端: {config_manager.current_endpoint}")

    # 也可以打印最终使用的配置供调试
    api_cfg = config_manager.get_api_client_config()
    logger.info(f"API 基础地址: {api_cfg['base_url']}")


@pytest.fixture(scope="session")
def api_client():
    """全局 API 客户端，根据当前环境/终端配置动态创建"""
    cfg = config_manager.get_api_client_config()
    # 将 endpoint 注入到 cfg，以便 APIClient 能在检测到登录失效时自动刷新 token
    cfg['endpoint'] = config_manager.current_endpoint
    client = APIClient(**cfg)
    logger.info(f"API客户端初始化完成，环境: {config_manager.current_env}")
    yield client
    logger.info("API客户端关闭")

# ==================== 新增的 fixture ====================

@pytest.fixture(scope="session")
def merchant_api_client():
    """商家端 API 客户端（固定使用 merchant 终端配置）"""
    cfg = config_manager.get_api_client_config(endpoint='merchant')
    cfg['endpoint'] = 'merchant'  # 传入 endpoint 以支持 token 自动刷新
    client = APIClient(**cfg)
    logger.info("商家端 API 客户端初始化完成")
    yield client
    logger.info("商家端 API 客户端关闭")


@pytest.fixture(scope="session")
def admin_api_client():
    """运营端 API 客户端（固定使用 admin 终端配置）"""
    cfg = config_manager.get_api_client_config(endpoint='admin')
    cfg['endpoint'] = 'admin'  # 传入 endpoint 以支持 token 自动刷新
    client = APIClient(**cfg)
    logger.info("运营端 API 客户端初始化完成")
    yield client
    logger.info("运营端 API 客户端关闭")


@pytest.fixture(scope="session")
def xianyu_api_client():
    """闲鱼店铺 API 客户端（使用 merchant 配置中的 xianyu_token）"""
    cfg = config_manager.get_xianyu_api_client_config()
    # xianyu 使用 merchant 端的 token 语义，显式注入 endpoint
    cfg['endpoint'] = 'merchant'
    client = APIClient(**cfg)
    logger.info(f"闲鱼店铺 API 客户端初始化完成 (token: {cfg['auth_config']['token'][:10]}...)")
    yield client
    logger.info("闲鱼店铺 API 客户端关闭")


@pytest.fixture(scope="session")
def global_vars():
    """全局测试变量，如 shop_id 等（从当前环境配置中读取）"""
    env_config = config_manager.get_env_config()
    return {
        "shop_id": env_config.get("shop_id"),
        "base_url": env_config.get("base_url"),
    }


@pytest.fixture
def db():
    """每个测试函数独立获取一个新的数据库连接"""
    with DatabaseManager() as db_manager:
        yield db_manager


@pytest.fixture
def dw_db():
    """
    数仓数据库连接，每个测试函数独立获取。
    连接信息从环境变量 DW_HOST/DW_PORT/DW_USER/DW_PASSWORD 读取。
    用法与 db fixture 一致，支持 context manager 自动释放。
    """
    logger.info(f"数仓数据库连接: {DW_DB_CONFIG['user']}@{DW_DB_CONFIG['host']}:{DW_DB_CONFIG['port']}")
    with DatabaseManager(db_config=DW_DB_CONFIG) as db_manager:
        yield db_manager

