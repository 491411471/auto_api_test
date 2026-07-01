# testcases/scenario/contract-lifecycle/test_contract_management.py
"""
合同管理流程测试模块
流程：合同申请 → 运营端审核 → 验证合同状态

用例列表：
- CM_001: 仲裁合同申请 + 审核通过
- CM_002: 诉讼合同申请 + 审核拒绝
"""
import allure
import json
import pytest
import yaml
import os
from common.logger import logger
from common.test_helpers import replace_placeholders
from utils.data_loader import get_test_data, get_global_variables
from utils.variable_utils import validate, get_value_by_path


# 预先加载用例数据
_ALL_CASES = get_test_data("contract_management_api.yaml", "contract_management_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 contract_management_api.yaml")


def _load_yaml():
    """加载YAML配置文件"""
    yaml_path = os.path.join(os.path.dirname(__file__), "../../../data/scenario/contract-lifecycle/contract_management_api.yaml")
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _get_case(case_id: str):
    """根据case_id获取测试用例"""
    for c in _ALL_CASES:
        if c['case_id'] == case_id:
            return c
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")

@allure.epic("商家端")
@allure.feature("商家端-店铺管理")
@allure.story("合同管理流程")
class TestContractManagement:
    """合同管理流程测试"""
    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        """加载全局变量"""
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("contract_management_api.yaml")
        return cls._global_vars.copy()

    @staticmethod
    def _execute_contract_application(admin_api_client, apply_cfg: dict, shop_id: str) -> None:
        """
        执行合同申请
        
        Args:
            admin_api_client: 运营端API客户端
            apply_cfg: 申请配置
            shop_id: 店铺ID
        """
        body = apply_cfg['body_template'].copy()
        body['shopId'] = shop_id
        
        # 记录请求参数
        allure.attach(
            json.dumps(body, indent=2, ensure_ascii=False),
            name="合同申请-请求参数",
            attachment_type=allure.attachment_type.JSON
        )
        logger.info(f"合同申请请求参数: {json.dumps(body, ensure_ascii=False)}")
        
        # 发送POST请求
        resp = admin_api_client.post(apply_cfg['endpoint'], json=body)
        
        # 验证HTTP状态码
        assert resp.status_code == apply_cfg['expected_status'], (
            f"HTTP状态码不符合预期\n"
            f"  期望值: {apply_cfg['expected_status']}\n"
            f"  实际值: {resp.status_code}"
        )
        
        # 解析响应
        resp_json = resp.json()
        
        # 记录响应
        allure.attach(
            json.dumps(resp_json, indent=2, ensure_ascii=False),
            name="合同申请-接口响应",
            attachment_type=allure.attachment_type.JSON
        )
        logger.info(f"合同申请响应: {json.dumps(resp_json, ensure_ascii=False)}")
        
        # 执行业务断言
        for check in apply_cfg['validate']:
            path = check['path'].lstrip('$').lstrip('.')
            actual = get_value_by_path(resp_json, path)
            validate(actual, check['operator'], check['value'], path)
        
        logger.info("合同申请成功")

    @staticmethod
    def _query_log_id(db, sql_template: str, shop_id: str) -> int:
        """
        查询合同申请记录ID
        
        Args:
            db: 数据库连接
            sql_template: SQL模板
            shop_id: 店铺ID
            
        Returns:
            记录ID
        """
        query_sql = replace_placeholders(sql_template, {"shop_id": shop_id})
        
        # 记录SQL
        allure.attach(
            query_sql,
            name="查询ID-SQL语句",
            attachment_type=allure.attachment_type.TEXT
        )
        logger.info(f"执行SQL: {query_sql}")
        
        try:
            # 执行查询
            result = db.fetch_one(query_sql)
            
            # 验证查询结果
            if result is None:
                skip_msg = (
                    f"未查询到合同申请记录，跳过此用例\n"
                    f"  shop_id: {shop_id}\n"
                    f"  SQL: {query_sql}"
                )
                allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                logger.warning(skip_msg)
                pytest.skip(skip_msg)
            
            log_id = result.get('id')
            assert log_id is not None, f"查询结果中缺少 id 字段: {result}"
            
            logger.info(f"查询到申请记录ID: {log_id}")
            
            # 记录查询结果
            allure.attach(
                f"申请记录ID: {log_id}",
                name="查询结果",
                attachment_type=allure.attachment_type.TEXT
            )
            
            return log_id
        except Exception as e:
            error_msg = (
                f"数据库查询失败: {e}\n"
                f"  shop_id: {shop_id}\n"
                f"  SQL: {query_sql}"
            )
            allure.attach(error_msg, name="错误信息", attachment_type=allure.attachment_type.TEXT)
            logger.error(error_msg)
            pytest.skip(error_msg)

    @staticmethod
    def _execute_audit(admin_api_client, audit_cfg: dict, log_id: int, status: int, audit_type: str) -> None:
        """
        执行运营端审核
        
        Args:
            admin_api_client: 运营端API客户端
            audit_cfg: 审核配置
            log_id: 记录ID
            status: 审核状态（0拒绝，1通过）
            audit_type: 审核类型（用于日志）
        """
        body = audit_cfg['body_template'].copy()
        body['id'] = log_id
        body['status'] = status
        
        # 记录请求参数
        allure.attach(
            json.dumps(body, indent=2, ensure_ascii=False),
            name=f"{audit_type}-请求参数",
            attachment_type=allure.attachment_type.JSON
        )
        logger.info(f"{audit_type}请求参数: {json.dumps(body, ensure_ascii=False)}")
        
        # 发送POST请求
        resp = admin_api_client.post(audit_cfg['endpoint'], json=body)
        
        # 验证HTTP状态码
        assert resp.status_code == audit_cfg['expected_status'], (
            f"HTTP状态码不符合预期\n"
            f"  期望值: {audit_cfg['expected_status']}\n"
            f"  实际值: {resp.status_code}"
        )
        
        # 解析响应
        resp_json = resp.json()
        
        # 记录响应
        allure.attach(
            json.dumps(resp_json, indent=2, ensure_ascii=False),
            name=f"{audit_type}-接口响应",
            attachment_type=allure.attachment_type.JSON
        )
        logger.info(f"{audit_type}响应: {json.dumps(resp_json, ensure_ascii=False)}")
        
        # 执行业务断言
        for check in audit_cfg['validate']:
            path = check['path'].lstrip('$').lstrip('.')
            actual = get_value_by_path(resp_json, path)
            validate(actual, check['operator'], check['value'], path)
        
        logger.info(f"{audit_type}成功，记录ID: {log_id}")

    @staticmethod
    def _verify_contract_status(db, sql_template: str, log_id: int, expected_status: int, status_desc: str) -> int:
        """
        验证合同状态
        
        Args:
            db: 数据库连接
            sql_template: SQL模板
            log_id: 记录ID
            expected_status: 期望状态
            status_desc: 状态描述（用于日志）
            
        Returns:
            实际状态值
        """
        verify_sql = replace_placeholders(sql_template, {"log_id": log_id})
        
        # 记录SQL
        allure.attach(
            verify_sql,
            name="验证状态-SQL语句",
            attachment_type=allure.attachment_type.TEXT
        )
        logger.info(f"执行SQL: {verify_sql}")
        
        try:
            # 执行查询
            result = db.fetch_one(verify_sql)
            
            # 验证查询结果
            if result is None:
                error_msg = f"未查询到合同记录，验证失败 | ID: {log_id}"
                allure.attach(error_msg, name="错误信息", attachment_type=allure.attachment_type.TEXT)
                logger.error(error_msg)
                assert False, error_msg
            
            actual_status = result.get('status')
            
            # 记录验证结果
            allure.attach(
                f"合同记录ID: {log_id}\n"
                f"期望状态: {expected_status} ({status_desc})\n"
                f"实际状态: {actual_status}",
                name="状态验证",
                attachment_type=allure.attachment_type.TEXT
            )
            logger.info(f"合同状态验证 - ID: {log_id}, 期望: {expected_status}, 实际: {actual_status}")
            
            # 断言验证
            assert actual_status == expected_status, (
                f"合同状态不符合预期\n"
                f"  记录ID: {log_id}\n"
                f"  期望状态: {expected_status} ({status_desc})\n"
                f"  实际状态: {actual_status}"
            )
            
            logger.info(f"合同状态验证通过 - ID: {log_id}, 状态: {actual_status}")
            return actual_status
        except Exception as e:
            error_msg = f"数据库查询失败: {e}"
            allure.attach(error_msg, name="错误信息", attachment_type=allure.attachment_type.TEXT)
            logger.error(error_msg)
            raise

    def test_cm_001_arbitration_contract_approval(self, admin_api_client, db):
        """
        CM_001: 合同申请-仲裁-中国海事-审核通过
        
        流程：
        1. 发起仲裁合同申请
        2. 查询最新申请记录ID
        3. 运营端审核通过
        4. 验证合同状态为已通过
        """
        case_config = _get_case("CM_001")
        global_vars = self._load_global_vars()
        shop_id = global_vars.get('shop_id')
        
        # 步骤1：合同申请（仲裁--中国海事）
        with allure.step("步骤1：发起仲裁合同申请"):
            self._execute_contract_application(
                admin_api_client,
                case_config['step1_apply'],
                shop_id
            )
        
        # 步骤2：获取最新申请记录ID
        with allure.step("步骤2：查询最新申请记录ID"):
            log_id = self._query_log_id(
                db,
                case_config['step2_query_id_sql'],
                shop_id
            )
        
        # 步骤3：运营端审核通过
        with allure.step("步骤3：运营端审核通过"):
            self._execute_audit(
                admin_api_client,
                case_config['step3_audit_pass'],
                log_id,
                status=1,
                audit_type="审核通过"
            )
        
        # 步骤4：验证合同状态
        with allure.step("步骤4：验证合同状态为已通过"):
            actual_status = self._verify_contract_status(
                db,
                case_config['step4_verify_status_sql'],
                log_id,
                expected_status=1,
                status_desc="审核通过"
            )
        
        # 测试总结
        allure.attach(
            f"测试用例: CM_001\n"
            f"合同类型: 仲裁-中国海事\n"
            f"申请记录ID: {log_id}\n"
            f"审核状态: {actual_status} (审核通过)\n\n"
            f"验证结果: ✓ 全部通过",
            name="测试总结",
            attachment_type=allure.attachment_type.TEXT
        )
        logger.info("合同管理测试CM_001全部通过")

    def test_cm_002_litigation_contract_rejection(self, admin_api_client, db):
        """
        CM_002: 合同申请-诉讼-甲方乙方-审核拒绝
        
        流程：
        1. 发起诉讼合同申请
        2. 查询最新申请记录ID
        3. 运营端审核拒绝
        4. 验证合同状态为已拒绝
        """
        case_config = _get_case("CM_002")
        global_vars = self._load_global_vars()
        shop_id = global_vars.get('shop_id')
        
        # 步骤1：合同申请（诉讼--甲方乙方）
        with allure.step("步骤1：发起诉讼合同申请"):
            self._execute_contract_application(
                admin_api_client,
                case_config['step1_apply'],
                shop_id
            )
        
        # 步骤2：获取最新申请记录ID
        with allure.step("步骤2：查询最新申请记录ID"):
            log_id = self._query_log_id(
                db,
                case_config['step2_query_id_sql'],
                shop_id
            )
        
        # 步骤3：运营端审核拒绝
        with allure.step("步骤3：运营端审核拒绝"):
            self._execute_audit(
                admin_api_client,
                case_config['step3_audit_reject'],
                log_id,
                status=0,
                audit_type="审核拒绝"
            )
        
        # 步骤4：验证合同状态
        with allure.step("步骤4：验证合同状态为已拒绝"):
            actual_status = self._verify_contract_status(
                db,
                case_config['step4_verify_status_sql'],
                log_id,
                expected_status=0,
                status_desc="审核拒绝"
            )
        
        # 测试总结
        allure.attach(
            f"测试用例: CM_002\n"
            f"合同类型: 诉讼-甲方乙方\n"
            f"申请记录ID: {log_id}\n"
            f"审核状态: {actual_status} (审核拒绝)\n\n"
            f"验证结果: ✓ 全部通过",
            name="测试总结",
            attachment_type=allure.attachment_type.TEXT
        )
        logger.info("合同管理测试CM_002全部通过")
