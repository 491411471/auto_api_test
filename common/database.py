# -*- coding: utf-8 -*-
# [OPTIMIZED] 优化数据库连接管理，增加异常处理和日志
import pymysql
from pymysql.cursors import DictCursor

from common.logger import logger
from config.config import DB_CONFIG


class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.cursor = None

    def __enter__(self):
        try:
            self.connection = pymysql.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG.get('port', 3306),
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                charset=DB_CONFIG.get('charset', 'utf8mb4'),
                cursorclass=DictCursor
            )
            self.cursor = self.connection.cursor()
            logger.debug("数据库连接成功")
            return self
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.connection.commit()
            logger.debug("事务提交")
        else:
            self.connection.rollback()
            logger.error(f"事务回滚，异常: {exc_val}")
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
            logger.debug("数据库连接关闭")

    def fetch_all(self, sql: str, params=None):
        self.cursor.execute(sql, params or ())
        return self.cursor.fetchall()

    def fetch_one(self, sql: str, params=None):
        self.cursor.execute(sql, params or ())
        return self.cursor.fetchone()

    def execute_update(self, sql: str, params=None):
        rows = self.cursor.execute(sql, params or ())
        return rows