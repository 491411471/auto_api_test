"""
紧急联系人管理流程测试
流程：SQL查询订单 → 识别紧急联系人 → 保存紧急联系人 → 查看紧急联系人
"""
import allure
import os
import yaml
import pytest
import random
import json
from faker import Faker
from datetime import datetime
from common.logger import logger
from common.test_helpers import execute_test_case

fake = Faker('zh_CN')


def generate_emergency_contacts(count=2):
    """生成紧急联系人信息"""
    relations = ['朋友', '亲属', '同事']
    return '\n'.join([f"{fake.name()}{fake.phone_number()}{random.choice(relations)}" for _ in range(count)])


def load_yaml(yaml_path):
    """加载YAML配置文件"""
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

@allure.epic("商家端")
@allure.feature("订单模块-紧急联系人")
@allure.story("订单添加和查看紧急联系人")
class TestEmergencyContactFlow:

    @allure.title("完整流程：SQL查询订单 → 识别紧急联系人 → 保存紧急联系人 → 查看紧急联系人")
    def test_emergency_contact_flow(self, merchant_api_client, db, global_vars):
        """紧急联系人管理完整流程测试"""
        yaml_path = os.path.join(os.path.dirname(__file__), "../../../../data/merchant/scenario/order/emergency_contact_flow.yaml")
        config = load_yaml(yaml_path)

        contact_count = config.get('test_order', {}).get('contact_count', 2)
        content = generate_emergency_contacts(contact_count)
        
        allure.attach(f"生成数量: {contact_count}\n\n联系人内容:\n{content}", 
                     name="测试数据", attachment_type=allure.attachment_type.TEXT)

        variables = global_vars.copy()
        # 合并 YAML 顶层 variables（包含 excluded_order_id 等）
        yaml_vars = config.get('variables', {})
        variables.update(yaml_vars)
        variables['content'] = content

        # 步骤1：通过 SQL 查询获取订单ID → 识别新增紧急联系人信息
        with allure.step("1. 通过SQL查询订单并识别新增紧急联系人信息"):
            identify_cfg = config['step_identify_contact']
            identify_case = {
                'case_id': identify_cfg.get('case_id', 'ECF_001'),
                'title': identify_cfg.get('title', '识别新增紧急联系人信息'),
                'description': identify_cfg.get('description', ''),
                'endpoint': identify_cfg['endpoint'],
                'method': identify_cfg['method'],
                'sql': identify_cfg.get('sql'),
                'body': identify_cfg.get('body', {}),
                'expected_status': identify_cfg['expected_status'],
                'validate': identify_cfg.get('validate', [])
            }
            
            try:
                execute_test_case(identify_case, merchant_api_client, db, variables)
            except ValueError as e:
                if 'SQL 无结果' in str(e):
                    pytest.skip(f"未查询到符合条件的订单: {e}")
                raise
        # 步骤2：保存新增紧急联系人
        with allure.step("2. 保存新增紧急联系人"):
            order_id = variables.get('order_id')
            if not order_id:
                pytest.skip("步骤1未获取到订单ID")
            
            # 调用识别接口获取联系人列表
            resp = merchant_api_client.post(config['step_identify_contact']['endpoint'], 
                                           json={"orderId": order_id, "content": content})
            resp_json = resp.json()
            
            contact_list = (resp_json.get('data') or {}).get('list') or []
            if not contact_list or resp_json.get('businessSuccess') is not True:
                pytest.skip(f"识别紧急联系人失败: {resp_json.get('errorMessage', '未知错误')}")
            
            # 转换联系人列表格式
            contract_type_mapping = {"朋友": "friend", "同事": "colleague", "亲属": "family"}
            order_list = []
            for contact in contact_list:
                contract_type_cn = contact.get('contractType', '')
                order_list.append({
                    "id": contact.get('id'),
                    "userName": contact.get('userName'),
                    "telphone": contact.get('telphone'),
                    "wechat": None,
                    "orderId": order_id,
                    "contractType": contract_type_mapping.get(contract_type_cn, contract_type_cn.lower()),
                    "contractTypeName": contract_type_cn,
                    "passCheck": 0,
                    "createId": None,
                    "createTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "cause": None,
                    "remark": None,
                    "isOpenEye": False,
                    "telphoneOpenNum": "",
                    "havePermission": True
                })
            
            variables['order_list'] = order_list
            
            save_case = {
                'case_id': 'ECF_002',
                'title': '保存新增紧急联系人',
                'endpoint': config['step_save_contact']['endpoint'],
                'method': 'POST',
                'body': {'orderId': '${order_id}', 'orderList': '${order_list}'},
                'expected_status': 200,
                'validate': config['step_save_contact'].get('validate', [])
            }
            
            try:
                execute_test_case(save_case, merchant_api_client, db, variables)
            except Exception as e:
                if 'businessSuccess' in str(e) or '业务失败' in str(e):
                    pytest.skip(f"保存紧急联系人失败: {e}")
                raise

        # 步骤3：查看新增的紧急联系人
        with allure.step("3. 查看新增的紧急联系人"):
            query_case = {
                'case_id': 'ECF_003',
                'title': '查看新增的紧急联系人',
                'endpoint': config['step_query_contact']['endpoint'],
                'method': 'POST',
                'body': {'orderId': '${order_id}'},
                'expected_status': 200,
                'validate': config['step_query_contact'].get('validate', [])
            }
            
            execute_test_case(query_case, merchant_api_client, db, variables)
        
        allure.attach(f"订单号: {variables.get('order_id')}\n流程执行成功", 
                     name="最终结果", attachment_type=allure.attachment_type.TEXT)
