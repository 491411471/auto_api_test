import json
import allure
from pathlib import Path
import yaml

from utils.product_utils import (
    gen_product_name,
    generate_uuid,
    upload_test_image,
    replace_placeholders
)


def load_xianyu_request_template(yaml_path: str) -> dict:

    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data['xianyu_product_create_tests'][0]


def load_audit_template(yaml_path: str) -> dict:
    """
    加载审核请求模板 YAML 文件
    """
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data['xianyu_product_audit_test'][0]


def attach_error_detail(error_msg: str, context: str):
    """统一错误信息附件处理"""
    allure.attach(error_msg, context, attachment_type=allure.attachment_type.TEXT)


@allure.feature("商家端-闲鱼商品管理")
@allure.story("新建闲鱼商品")
class TestXianYuProductCreate:

    @allure.title("新建闲鱼商品-完整流程验证")
    def test_create_xianyu_product_success(self, xianyu_api_client, db, admin_api_client):
        project_root = Path(__file__).resolve().parent.parent.parent.parent

        # ========== 第一阶段：创建闲鱼商品 ==========
        with allure.step("阶段一：创建闲鱼商品"):
            product_id_db = self._create_xianyu_product(xianyu_api_client, db, project_root)

        # ========== 第二阶段：审核商品 ==========
        with allure.step("阶段二：审核闲鱼商品"):
            self._audit_xianyu_product(admin_api_client, db, project_root, product_id_db)

    def _create_xianyu_product(self, xianyu_api_client, db, project_root):
        """创建闲鱼商品并返回商品ID"""
        # 1. 准备测试数据
        product_name, variables = self._prepare_test_data(xianyu_api_client)
        
        # 2. 加载并替换模板
        template = self._load_create_template(project_root)
        create_payload = replace_placeholders(template, variables)
        
        # 3. 发送创建请求
        json_data = create_payload.get("body")
        endpoint = create_payload.get("endpoint")
        create_result = self._send_create_request(xianyu_api_client, endpoint, json_data)
        
        # 4. 验证响应
        self._assert_create_response(create_result)
        
        # 5. 查询数据库验证
        product_id_db = self._verify_product_in_db(db, product_name)
        
        allure.attach("闲鱼商品创建成功：接口调用成功 → 数据库记录正确", "创建阶段结果", attachment_type=allure.attachment_type.TEXT)
        return product_id_db

    def _prepare_test_data(self, xianyu_api_client):
        """准备测试数据"""
        product_name = gen_product_name()
        uuid_1 = generate_uuid()
        image_url = upload_test_image(xianyu_api_client, "/data/scenario/images/xianyu.jpg")
        
        variables = {
            "product_name": product_name,
            "uuid_1": uuid_1,
            "image_url": image_url,
            "category_id": 1230
        }
        allure.attach(json.dumps(variables, indent=2, ensure_ascii=False), "动态测试数据", attachment_type=allure.attachment_type.JSON)
        return product_name, variables

    def _load_create_template(self, project_root):
        """加载创建模板"""
        yaml_path = project_root / "data" / "scenario" / "product" / "xianyu_product_create.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"YAML 配置文件不存在: {yaml_path}")
        
        template = load_xianyu_request_template(str(yaml_path))
        allure.attach(json.dumps(template, indent=2), "原始模板", attachment_type=allure.attachment_type.JSON)
        return template

    def _send_create_request(self, xianyu_api_client, endpoint, json_data):
        """发送创建请求"""
        required_fields = ['categoryIds', 'name', 'title', 'itemLeaseDTO']
        for field in required_fields:
            if field not in json_data or json_data.get(field) is None:
                raise ValueError(f"必填参数 {field} 缺失或为空")
        
        response = xianyu_api_client.post(endpoint, json=json_data)
        allure.attach(str(response.status_code), "HTTP 状态码", attachment_type=allure.attachment_type.TEXT)
        
        result = response.json()
        allure.attach(json.dumps(result, indent=2, ensure_ascii=False), "闲鱼商品创建-接口响应", attachment_type=allure.attachment_type.JSON)
        
        if not result.get('businessSuccess'):
            error_detail = (
                f"闲鱼商品创建业务失败\n"
                f"  错误码: {result.get('errorCode', 'N/A')}\n"
                f"  错误类型: {result.get('responseType', 'N/A')}\n"
                f"  错误信息: {result.get('errorMessage', '未知错误')}"
            )
            attach_error_detail(error_detail, "业务错误详情")
        
        return result

    def _assert_create_response(self, result):
        """验证创建响应"""
        assert result.get('businessSuccess') is True, (
            f"闲鱼商品创建业务失败！\n"
            f"  期望值: True\n"
            f"  实际值: {result.get('businessSuccess')}\n"
            f"  错误码: {result.get('errorCode', 'N/A')}\n"
            f"  错误信息: {result.get('errorMessage', '未知错误')}"
        )
        
        assert result.get('data') is True, (
            f"商品创建 data 字段不符合预期！\n"
            f"  期望值: True\n"
            f"  实际值: {result.get('data')}"
        )
        
        assert result.get('rpcResult') == 'SUCCESS', (
            f"商品创建 rpcResult 不符合预期！\n"
            f"  期望值: SUCCESS\n"
            f"  实际值: {result.get('rpcResult')}\n"
            f"  错误码: {result.get('errorCode', 'N/A')}"
        )

    def _verify_product_in_db(self, db, product_name):
        """验证数据库中的商品信息"""
        sql = "SELECT id, name, category_id FROM llxz_product.ct_product WHERE name = %s AND product_type = 'xianyu' ORDER BY create_time DESC LIMIT 1"
        result = db.fetch_one(sql, (product_name,))
        
        assert result is not None, f"未找到闲鱼商品记录，商品名称: {product_name}"
        
        product_id = result.get('id')
        db_product_name = result.get('name')
        category_id = result.get('category_id')
        
        allure.attach(
            f"商品ID: {product_id}\n商品名称: {db_product_name}\n分类ID: {category_id}",
            "数据库商品信息",
            attachment_type=allure.attachment_type.TEXT
        )
        
        assert db_product_name == product_name, (
            f"数据库商品名称不匹配！\n"
            f"  期望值: {product_name}\n"
            f"  实际值: {db_product_name}"
        )
        
        assert category_id == 1230, (
            f"数据库分类ID不匹配！\n"
            f"  期望值: 1230\n"
            f"  实际值: {category_id}"
        )
        
        allure.attach(f"商品ID: {product_id}", "新增商品ID", attachment_type=allure.attachment_type.TEXT)
        return product_id

    def _audit_xianyu_product(self, admin_api_client, db, project_root, product_id_db):
        """审核闲鱼商品并验证"""
        # 1. 加载审核模板
        audit_body = self._load_audit_template(project_root, product_id_db)
        
        # 2. 发送审核请求
        audit_result = self._send_audit_request(admin_api_client, audit_body)
        
        # 3. 验证审核响应
        self._assert_audit_response(audit_result)
        
        # 4. 验证数据库审核状态
        self._verify_audit_status(db, product_id_db)
        
        allure.attach("完整流程验证通过：商品创建成功 → 审核接口调用成功 → 审核状态变为2", "最终结果", attachment_type=allure.attachment_type.TEXT)

    def _load_audit_template(self, project_root, product_id_db):
        """加载审核模板"""
        yaml_path = project_root / "data" / "scenario" / "product" / "xianyu_product_create.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"审核 YAML 配置文件不存在: {yaml_path}")
        
        audit_case = load_audit_template(str(yaml_path))
        audit_body = audit_case['body']
        audit_body['id'] = product_id_db
        
        allure.attach(json.dumps(audit_body, indent=2), "审核请求体", attachment_type=allure.attachment_type.TEXT)
        return audit_body

    def _send_audit_request(self, admin_api_client, audit_body):
        """发送审核请求"""
        response = admin_api_client.post("/hzsx/xianyu/product/opeAuditProductPost", json=audit_body)
        allure.attach(str(response.status_code), "HTTP 状态码", attachment_type=allure.attachment_type.TEXT)
        
        result = response.json()
        allure.attach(json.dumps(result, indent=2, ensure_ascii=False), "商品审核-接口响应", attachment_type=allure.attachment_type.JSON)
        
        if not result.get('businessSuccess'):
            error_detail = (
                f"商品审核业务失败\n"
                f"  错误码: {result.get('errorCode', 'N/A')}\n"
                f"  错误类型: {result.get('responseType', 'N/A')}\n"
                f"  错误信息: {result.get('errorMessage', '未知错误')}"
            )
            attach_error_detail(error_detail, "业务错误详情")
        
        return result

    def _assert_audit_response(self, result):
        """验证审核响应"""
        assert result.get('businessSuccess') is True, (
            f"商品审核业务失败！\n"
            f"  期望值: True\n"
            f"  实际值: {result.get('businessSuccess')}\n"
            f"  错误码: {result.get('errorCode', 'N/A')}\n"
            f"  错误信息: {result.get('errorMessage', '未知错误')}"
        )
        
        assert result.get('data') is True, (
            f"商品审核 data 字段不符合预期！\n"
            f"  期望值: True\n"
            f"  实际值: {result.get('data')}"
        )
        
        assert result.get('rpcResult') == 'SUCCESS', (
            f"商品审核 rpcResult 不符合预期！\n"
            f"  期望值: SUCCESS\n"
            f"  实际值: {result.get('rpcResult')}\n"
            f"  错误码: {result.get('errorCode', 'N/A')}"
        )

    def _verify_audit_status(self, db, product_id_db):
        """验证数据库审核状态"""
        result = db.fetch_one("SELECT audit_state FROM llxz_product.ct_product WHERE id = %s", (product_id_db,))
        
        assert result is not None, f"未找到商品记录，id={product_id_db}"
        
        actual_audit_state = result.get('audit_state')
        assert actual_audit_state is not None, "数据库中 audit_state 字段为空"
        
        allure.attach(
            f"商品ID: {product_id_db}\n审核状态: {actual_audit_state}",
            "数据库审核状态",
            attachment_type=allure.attachment_type.TEXT
        )
        
        assert actual_audit_state == 2, (
            f"商品审核状态不符合预期！\n"
            f"  期望值: 2\n"
            f"  实际值: {actual_audit_state}\n"
            f"  商品ID: {product_id_db}"
        )