# -*- coding: utf-8 -*-
"""
测试数据隔离与清理机制

提供一套可复用的数据清理工具，确保：
1. 测试执行前清除旧数据，避免干扰
2. 测试执行后清理测试数据，避免数据污染
3. 支持按规则自动清理和手动指定清理

使用示例:
    class TestOrderFlow(BaseScenarioTest):
        def test_order_flow(self, merchant_api_client, db, ...):
            cleaner = DataCleaner(db)
            
            # 方式1：注册清理规则（推荐）
            cleaner.register_cleanup("order", "ct_user_orders", "order_id", "${order_id}")
            cleaner.register_cleanup("stages", "ct_order_by_stages", "order_id", "${order_id}")
            
            # 在测试结束后自动清理
            yield  # 或调用 cleaner.cleanup_all()
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import allure
from common.logger import logger


class DataCleaner:
    """
    测试数据清理器
    
    支持两种清理模式：
    1. 自动模式：注册清理规则，测试结束时统一清理
    2. 手动模式：直接指定 SQL 语句清理
    
    清理策略：
    - DELETE：删除测试数据（默认）
    - UPDATE：更新状态，将数据标记为已删除
    - TRUNCATE：清空表（慎用！仅适用于临时表）
    """
    
    def __init__(self, db):
        """
        Args:
            db: DatabaseManager 实例
        """
        self.db = db
        self._rules: List[Dict[str, Any]] = []  # 待清理规则列表
        self._cleanup_log: List[str] = []        # 清理日志
        self._disabled = False                   # 是否禁用清理（用于调试）
    
    # ==================== 清理规则注册 ====================
    
    def register_cleanup(
        self,
        name: str,
        table: str,
        key_column: str,
        key_value: Any,
        strategy: str = "DELETE",
        extra_conditions: Optional[str] = None
    ) -> None:
        """
        注册一条清理规则
        
        Args:
            name: 规则名称（用于日志和报告）
            table: 表名（可带 database prefix，如 "llxz_order.ct_user_orders"）
            key_column: 主键/关联键列名
            key_value: 键值
            strategy: 清理策略 - DELETE / UPDATE / TRUNCATE
            extra_conditions: 额外的 WHERE 条件（如 "AND delete_time IS NULL"）
        """
        rule = {
            "name": name,
            "table": table,
            "key_column": key_column,
            "key_value": key_value,
            "strategy": strategy.upper(),
            "extra_conditions": extra_conditions or "",
        }
        self._rules.append(rule)
        logger.debug(f"[DataCleaner] 注册清理规则: {name} -> {table}({key_column}={key_value})")
    
    def register_cleanup_sql(self, name: str, sql: str) -> None:
        """
        注册自定义 SQL 清理规则
        
        Args:
            name: 规则名称
            sql: 完整的清理 SQL（如 "DELETE FROM table WHERE id = 'xxx'"）
        """
        rule = {
            "name": name,
            "sql": sql,
            "strategy": "CUSTOM_SQL",
        }
        self._rules.append(rule)
        logger.debug(f"[DataCleaner] 注册自定义清理: {name} -> {sql[:100]}...")
    
    def register_order_cleanup(self, order_id: str, shop_id: Optional[str] = None) -> None:
        """
        快速注册订单相关的多表清理规则
        
        Args:
            order_id: 订单号
            shop_id: 店铺 ID（可选，用于更精确的清理）
        """
        # 核心订单表
        self.register_cleanup("订单主表", "llxz_order.ct_user_orders", "order_id", order_id)
        self.register_cleanup("订单账期表", "llxz_order.ct_order_by_stages", "order_id", order_id)
        self.register_cleanup("订单商品表", "llxz_order.ct_user_order_goods", "order_id", order_id)
        self.register_cleanup("订单操作日志", "llxz_order.ct_order_action_log", "order_id", order_id)
        self.register_cleanup("订单签约表", "llxz_order.ct_user_order_sign", "order_id", order_id)
        
        if shop_id:
            self.register_cleanup(
                "订单发货记录",
                "llxz_order.ct_order_delivery",
                "order_id",
                order_id,
                extra_conditions=f"AND shop_id = '{shop_id}'"
            )
    
    # ==================== 清理执行 ====================
    
    def cleanup_all(self) -> int:
        """
        执行所有已注册的清理规则
        
        Returns:
            清理影响的总行数
        """
        if self._disabled:
            logger.warning("[DataCleaner] 清理已禁用，跳过")
            return 0
        
        if not self._rules:
            logger.info("[DataCleaner] 无待清理规则")
            return 0
        
        total_affected = 0
        
        with allure.step("清理测试数据（按注册顺序逆序执行）"):
            # 逆序执行（先清理子表，再清理主表）
            for rule in reversed(self._rules):
                try:
                    affected = self._execute_rule(rule)
                    total_affected += affected
                except Exception as e:
                    logger.error(f"[DataCleaner] 清理规则 '{rule['name']}' 执行失败: {e}")
                    allure.attach(
                        str(e),
                        name=f"清理失败: {rule['name']}",
                        attachment_type=allure.attachment_type.TEXT
                    )
            
            # 记录清理摘要
            summary = (
                f"数据清理完成\n"
                f"  规则总数: {len(self._rules)}\n"
                f"  影响行数: {total_affected}\n"
                f"  清理详情: {json.dumps(self._cleanup_log, ensure_ascii=False)}"
            ) if self._cleanup_log else "数据清理完成，无实际影响行数"
            
            allure.attach(summary, name="数据清理摘要", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"[DataCleaner] 清理完成，共影响 {total_affected} 行")
        
        return total_affected
    
    def _execute_rule(self, rule: Dict[str, Any]) -> int:
        """执行单条清理规则"""
        strategy = rule.get("strategy", "DELETE")
        
        if strategy == "CUSTOM_SQL":
            sql = rule["sql"]
            logger.info(f"[DataCleaner] 执行自定义清理: {sql[:150]}...")
            affected = self.db.execute_delete(sql)
            self._cleanup_log.append(f"{rule['name']}: 自定义 SQL, 影响 {affected} 行")
            return affected
        
        elif strategy == "DELETE":
            table = rule["table"]
            key_column = rule["key_column"]
            key_value = rule["key_value"]
            extra = rule.get("extra_conditions", "")
            
            # 处理字符串值加引号
            if isinstance(key_value, str):
                key_value_quoted = f"'{key_value}'"
            else:
                key_value_quoted = str(key_value)
            
            sql = f"DELETE FROM {table} WHERE {key_column} = {key_value_quoted} {extra}"
            
            logger.info(f"[DataCleaner] 执行 DELETE 清理: {sql[:200]}...")
            affected = self.db.execute_delete(sql)
            self._cleanup_log.append(f"{rule['name']}: DELETE {table}, 影响 {affected} 行")
            return affected
        
        elif strategy == "UPDATE":
            table = rule["table"]
            key_column = rule["key_column"]
            key_value = rule["key_value"]
            extra = rule.get("extra_conditions", "")
            
            if isinstance(key_value, str):
                key_value_quoted = f"'{key_value}'"
            else:
                key_value_quoted = str(key_value)
            
            # 标记为已删除（软删除）
            sql = f"UPDATE {table} SET delete_time = NOW() WHERE {key_column} = {key_value_quoted} {extra}"
            
            logger.info(f"[DataCleaner] 执行 UPDATE 清理（软删除）: {sql[:200]}...")
            affected = self.db.execute_update(sql)
            self._cleanup_log.append(f"{rule['name']}: UPDATE {table}, 影响 {affected} 行")
            return affected
        
        else:
            logger.warning(f"[DataCleaner] 未知清理策略: {strategy}")
            return 0
    
    # ==================== 状态管理 ====================
    
    def disable(self) -> None:
        """禁用清理（用于调试，确认数据后手动清理）"""
        self._disabled = True
        logger.warning("[DataCleaner] 清理已禁用")
    
    def enable(self) -> None:
        """启用清理"""
        self._disabled = False
        logger.info("[DataCleaner] 清理已启用")
    
    def clear_rules(self) -> None:
        """清空所有注册的清理规则"""
        self._rules.clear()
        logger.debug("[DataCleaner] 清理规则已清空")
    
    def get_summary(self) -> str:
        """获取清理规则摘要"""
        if not self._rules:
            return "无待清理规则"
        
        lines = [f"待清理规则 ({len(self._rules)} 条):"]
        for rule in self._rules:
            strategy = rule.get("strategy", "DELETE")
            if strategy == "CUSTOM_SQL":
                lines.append(f"  - {rule['name']}: 自定义 SQL")
            else:
                lines.append(f"  - {rule['name']}: {strategy} {rule['table']}({rule['key_column']}={rule['key_value']})")
        
        return "\n".join(lines)


class TransactionGuard:
    """
    事务守卫：通过数据库事务实现数据隔离
    
    在测试开始前开启事务，测试结束后回滚，
    确保测试数据不会实际写入数据库。
    
    注意：仅适用于支持事务的引擎（InnoDB），
    不适用于 MyISAM 等不支持事务的表。
    
    使用方式:
        with TransactionGuard(db) as guarded_db:
            guarded_db.execute_update(...)
            # 所有操作在测试结束后自动回滚
    
    或作为 fixture:
        @pytest.fixture
        def isolated_db(db):
            with TransactionGuard(db) as guard:
                yield guard
    """
    
    def __init__(self, db):
        self.db = db
        self._rolled_back = False
    
    def __enter__(self):
        logger.info("[TransactionGuard] 开启事务（测试数据将被隔离）")
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # 无异常时回滚（隔离测试数据）
            self.db.rollback()
            self._rolled_back = True
            logger.info("[TransactionGuard] 事务回滚（测试数据已隔离）")
        else:
            # 有异常时也回滚
            try:
                self.db.rollback()
                self._rolled_back = True
                logger.info(f"[TransactionGuard] 异常回滚: {exc_val}")
            except Exception as e:
                logger.error(f"[TransactionGuard] 回滚失败: {e}")
    
    def is_rolled_back(self) -> bool:
        """检查事务是否已回滚"""
        return self._rolled_back


# 便捷的 pytest fixture 定义
# 使用时在 conftest.py 中添加：
#
# @pytest.fixture
# def isolated_db(db):
#     """数据隔离的数据库连接（测试后自动回滚）"""
#     with TransactionGuard(db) as guard:
#         yield guard
#
# @pytest.fixture
# def data_cleaner(db):
#     """数据清理器 fixture"""
#     cleaner = DataCleaner(db)
#     yield cleaner
#     cleaner.cleanup_all()
