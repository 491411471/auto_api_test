# -*- coding: utf-8 -*-
"""
测试基类
提供通用的测试方法，减少重复代码
"""
import copy
from typing import Any, Dict, List, Optional

import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables


class VariableManager:
    """变量管理器：安全地管理测试变量的复制、更新和清理"""
    
    def __init__(self, initial_vars: Optional[Dict[str, Any]] = None):
        self._variables: Dict[str, Any] = initial_vars.copy() if initial_vars else {}
        self._snapshot: Dict[str, Any] = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取变量值"""
        return self._variables.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """设置变量值"""
        self._variables[key] = value
    
    def update(self, other: Dict[str, Any]) -> None:
        """批量更新变量"""
        self._variables.update(other)
    
    def snapshot(self) -> None:
        """创建当前变量状态的快照"""
        self._snapshot = copy.deepcopy(self._variables)
    
    def restore(self) -> None:
        """恢复到快照状态"""
        if self._snapshot:
            self._variables = copy.deepcopy(self._snapshot)
        else:
            logger.warning("没有可用的变量快照")
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有变量的副本"""
        return copy.deepcopy(self._variables)
    
    def clear(self) -> None:
        """清空所有变量"""
        self._variables.clear()
    
    def __contains__(self, key: str) -> bool:
        return key in self._variables
    
    def __getitem__(self, key: str) -> Any:
        return self._variables[key]
    
    def __setitem__(self, key: str, value: Any) -> None:
        self._variables[key] = value
    
    def __repr__(self) -> str:
        return f"VariableManager({self._variables})"


class BaseAPITest:
    """
    API 测试基类
    
    使用示例:
        class TestOrderQuery(BaseAPITest):
            yaml_file = "query_order_api.yaml"
            data_key = "order_query_tests"
            
            @pytest.mark.smoke
            @pytest.mark.parametrize("case", BaseAPITest.load_test_cases("query_order_api.yaml", "order_query_tests"),
                                    ids=BaseAPTest.load_case_ids("query_order_api.yaml", "order_query_tests"))
            def test_order_query(self, api_client, db, case):
                allure.dynamic.title(f"{case['case_id']} - {case['title']}")
                self.run_case(case, api_client, db)
    """
    
    # 子类需要覆盖的属性
    yaml_file: Optional[str] = None
    data_key: Optional[str] = None
    
    @classmethod
    def load_test_cases(cls, yaml_file: Optional[str] = None, data_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        加载测试用例数据
        
        Args:
            yaml_file: YAML 文件名（如果为 None，使用类的 yaml_file 属性）
            data_key: YAML 中的数据键（如果为 None，使用类的 data_key 属性）
            
        Returns:
            测试用例列表
        """
        file = yaml_file or cls.yaml_file
        key = data_key or cls.data_key
        
        if not file or not key:
            raise ValueError("必须指定 yaml_file 和 data_key")
        
        return get_test_data(file, key)
    
    @classmethod
    def load_case_ids(cls, yaml_file: Optional[str] = None, data_key: Optional[str] = None) -> List[str]:
        """
        加载用例 ID 列表
        
        Returns:
            用例 ID 列表
        """
        cases = cls.load_test_cases(yaml_file, data_key)
        return [case.get('case_id', f'case_{i}') for i, case in enumerate(cases)]
    
    @classmethod
    def load_global_variables(cls, yaml_file: Optional[str] = None) -> Dict[str, Any]:
        """
        加载全局变量
        
        Args:
            yaml_file: YAML 文件名
            
        Returns:
            全局变量字典
        """
        file = yaml_file or cls.yaml_file
        if not file:
            return {}
        
        return get_global_variables(file)
    
    def setup_method(self, method) -> None:
        """每个测试方法执行前的钩子"""
        # 初始化变量管理器
        self.var_manager = VariableManager(self.load_global_variables())
        logger.debug(f"测试方法 {method.__name__} 开始执行")
    
    def teardown_method(self, method) -> None:
        """每个测试方法执行后的钩子"""
        logger.debug(f"测试方法 {method.__name__} 执行完成")
    
    def run_case(
        self, 
        case: Dict[str, Any], 
        api_client, 
        db, 
        extra_vars: Optional[Dict[str, Any]] = None,
        retry_config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        执行测试用例
        
        Args:
            case: 测试用例数据
            api_client: API 客户端
            db: 数据库管理器
            extra_vars: 额外的变量（会合并到全局变量中）
            retry_config: 重试配置
        """
        # 创建变量快照，以便重试时恢复
        self.var_manager.snapshot()
        
        # 合并额外变量
        if extra_vars:
            self.var_manager.update(extra_vars)
        
        # 合并用例私有变量
        if 'variables' in case and isinstance(case['variables'], dict):
            self.var_manager.update(case['variables'])
            logger.debug(f"合并用例私有变量: {case['variables']}")
        
        # 获取最终变量
        variables = self.var_manager.get_all()
        
        # 执行测试用例
        execute_test_case(case, api_client, db, variables, retry_config)
    
    def add_dynamic_vars(self, vars_dict: Dict[str, Any]) -> None:
        """
        添加动态变量（在测试方法中调用）
        
        Args:
            vars_dict: 动态变量字典
            
        Example:
            def test_order_query(self, api_client, db, case):
                # 添加动态日期变量
                from datetime import datetime, timedelta
                today = datetime.now()
                self.add_dynamic_vars({
                    "start_date": (today - timedelta(days=30)).strftime("%Y-%m-%d"),
                    "end_date": today.strftime("%Y-%m-%d")
                })
                self.run_case(case, api_client, db)
        """
        self.var_manager.update(vars_dict)


class BaseScenarioTest(BaseAPITest):
    """
    场景测试基类（继承自 BaseAPITest）
    
    适用于需要多个接口组合的业务流程测试
    """
    
    def __init__(self):
        self.test_data: Dict[str, Any] = {}
    
    def save_test_data(self, key: str, value: Any) -> None:
        """保存测试过程中产生的数据"""
        self.test_data[key] = value
        self.var_manager.set(key, value)
    
    def get_test_data(self, key: str, default: Any = None) -> Any:
        """获取测试过程中保存的数据"""
        return self.test_data.get(key, default)
    
    def run_step(
        self, 
        step_name: str, 
        case: Dict[str, Any], 
        api_client, 
        db,
        extra_vars: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        执行场景测试中的一个步骤
        
        Args:
            step_name: 步骤名称（用于 Allure 报告）
            case: 测试用例数据
            api_client: API 客户端
            db: 数据库管理器
            extra_vars: 额外变量
        """
        with allure.step(f"场景步骤: {step_name}"):
            self.run_case(case, api_client, db, extra_vars)
