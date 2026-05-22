# -*- coding: utf-8 -*-
# [NEW] 新增独立配置文件，用于存放数据库、企业微信等敏感或独立配置
import os

# 基础路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------- 数据库配置（test）----------
DB_CONFIG = {
    "host": "lxztestmysqlpldb.rwlb.rds.aliyuncs.com",
    "port": 3306,
    "user": "my_user1",
    "password": "z1bUsedSsad!iyY+&ddsfgC!2",
    # "database": "test_db",
    "charset": "utf8mb4"
}

# ---------- 企业微信机器人配置 ----------
WECHAT_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=df5e6b07-7c67-4620-be02-440214e332d3"

# 发送企业微信userid对象
WECHAT_USERID = ["liuaiqiang-1035825", "wangchao-1018135"]

# 报告外部访问地址（用于企业微信链接，需自行配置）
HTTP_REPORT_BASE = "http://192.168.20.111/"

