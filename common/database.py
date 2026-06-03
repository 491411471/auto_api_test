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

    def execute_delete(self, sql: str, params=None, autocommit: bool = True) -> int:
        """
        执行 DELETE 语句，返回受影响行数。
        仅允许 DELETE 语句，防止误用导致数据安全事故。
        autocommit=True 时执行后立即提交，确保变更对其他数据库连接立即可见。
        """
        stripped = sql.strip().upper()
        if not stripped.startswith("DELETE"):
            raise ValueError(f"execute_delete 仅接受 DELETE 语句，收到: {sql[:80]}")
        affected_rows = self.cursor.execute(sql, params or ())
        if autocommit:
            self.connection.commit()
        logger.info(f"execute_delete 执行完成，影响行数: {affected_rows}，autocommit={autocommit}，SQL: {sql[:120]}")
        return affected_rows

    def commit(self):
        """显式提交当前事务"""
        if self.connection:
            self.connection.commit()
            logger.debug("显式事务提交")

    def rollback(self):
        """显式回滚当前事务"""
        if self.connection:
            self.connection.rollback()
            logger.debug("显式事务回滚")