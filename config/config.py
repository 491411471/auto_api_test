# -*- coding: utf-8 -*-
"""
配置管理模块
从环境变量读取敏感信息，避免硬编码
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"已加载环境变量文件: {env_path}")
else:
    print("未找到 .env 文件，使用系统环境变量或默认值")

# 基础路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------- 数据库配置 ----------
# 从环境变量读取，避免硬编码敏感信息
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "lxztestmysqlpldb.rwlb.rds.aliyuncs.com"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "my_user1"),
    "password": os.getenv("DB_PASSWORD"),  # 必须从环境变量读取
    "charset": os.getenv("DB_CHARSET", "utf8mb4")
}

# 验证必要的配置
if not DB_CONFIG["password"]:
    raise ValueError(
        "未配置数据库密码！\n"
        "请执行以下步骤：\n"
        "1. 复制 .env.example 为 .env\n"
        "2. 在 .env 文件中填入真实的数据库密码\n"
        "3. 重新运行测试"
    )

# ---------- 数仓数据库配置 ----------
DW_DB_CONFIG = {
    "host": os.getenv("DW_HOST", "127.0.0.1"),
    "port": int(os.getenv("DW_PORT", os.getenv("DW_POR", "9030"))),
    "user": os.getenv("DW_USER", ""),
    "password": os.getenv("DW_PASSWORD", ""),
    "charset": os.getenv("DW_CHARSET", "utf8mb4"),
}

# ---------- 企业微信机器人配置 ----------
WECHAT_WEBHOOK = os.getenv("WECHAT_WEBHOOK")
WECHAT_USERID = os.getenv("WECHAT_USERIDS", "").split(",") if os.getenv("WECHAT_USERIDS") else []

# ---------- 报告配置 ----------
HTTP_REPORT_BASE = os.getenv("HTTP_REPORT_BASE", "http://localhost/")

# ---------- 配置验证 ----------
def validate_config():
    """验证配置完整性"""
    missing_configs = []
    
    if not DB_CONFIG.get("password"):
        missing_configs.append("DB_PASSWORD")
    
    if missing_configs:
        print("\n" + "="*60)
        print("配置验证失败，缺少以下必要配置：")
        for config in missing_configs:
            print(f"   - {config}")
        print("\n请参考 .env.example 创建 .env 文件并填入配置")
        print("="*60 + "\n")
        return False
    
    return True

# 启动时验证配置
if not validate_config():
    raise RuntimeError("配置验证失败，请检查环境变量配置")

