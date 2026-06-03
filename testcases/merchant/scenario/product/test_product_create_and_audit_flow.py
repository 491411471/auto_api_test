import json

import allure
from pathlib import Path
import yaml

from utils.product_utils import (
    gen_product_name,
    generate_uuid,
    upload_test_image,
    generate_inventory_date_map,
    replace_placeholders
)


def load_request_template(yaml_path: str) -> dict:
    """
    加载请求模板 YAML 文件
    
    Args:
        yaml_path: YAML 文件路径
        
    Returns:
        dict: 模板数据
    """
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data['product_create_tests']

# ==================== 测试类 ====================
@allure.feature("商家端-商品管理")
@allure.story("新增商品 → 运营端审核通过 → 验证审核状态")
class TestProductCreateAndAudit:

    @allure.title("完整流程：新增短租商品 → 调用审核接口通过 → 验证商品审核状态为2")
    def test_create_product_and_audit_pass(self, api_client, db, admin_api_client):
        # 获取项目根目录
        project_root = Path(__file__).resolve().parent.parent.parent.parent

        # ---------- 步骤1：生成动态变量 ----------
        with allure.step("生成动态测试数据"):
            # 生成商品名称
            product_name = gen_product_name()
            
            # 生成 UUID
            uuid_1 = generate_uuid()
            uuid_2 = generate_uuid()
            
            # 上传测试图片
            image_path = "/data/common/images/test_image.png"
            image_url,image_id = upload_test_image(api_client, image_path)
            
            # 生成库存日期映射（未来14天）
            inventory_map = generate_inventory_date_map(days=14)
            
            # 构造测试变量字典
            variables = {
                "product_name": product_name,
                "uuid_1": uuid_1,
                "uuid_2": uuid_2,
                "image_url": image_url,
                "inventory_date_map": inventory_map,
                "category_id": 1230,
                "channel_group_code": "001"
            }
            
            # 附加动态变量到 Allure 报告
            allure.attach(
                json.dumps(variables, indent=2, ensure_ascii=False, default=str),
                "动态测试数据",
                allure.attachment_type.JSON
            )

        # ---------- 步骤2：加载商品创建模板并替换 ----------
        with allure.step("加载商品创建请求模板"):
            # 构建 YAML 文件路径
            yaml_path = project_root / "data" / "merchant" / "scenario" / "product" / "product_create_and_audit_api.yaml"
            
            # 验证文件是否存在
            if not yaml_path.exists():
                raise FileNotFoundError(f"YAML 配置文件不存在: {yaml_path}")
            
            # 加载模板
            template = load_request_template(str(yaml_path))
            allure.attach(json.dumps(template, indent=2), "原始模板", attachment_type=allure.attachment_type.JSON)

        with allure.step("替换请求体中的占位符"):
            create_payload = replace_placeholders(template, variables)
            allure.attach(json.dumps(create_payload, indent=2), "最终请求体", attachment_type=allure.attachment_type.JSON)
        json_data=create_payload.get("json")
        # ---------- 步骤3：调用新增商品接口 ----------
        with allure.step("发送商品创建请求"):
            # 验证必填参数
            if not json_data.get('categoryId'):
                raise ValueError("商品分类ID (categoryId) 是必传参数")
            
            # 发送 POST 请求
            create_response = api_client.post(
                "/hzsx/product/busInsertProduct",
                json=json_data
            )
            
            # 附加 HTTP 状态码
            allure.attach(
                str(create_response.status_code),
                "HTTP 状态码",
                allure.attachment_type.TEXT
            )
            
            # 解析响应数据
            create_result = create_response.json()
            
            # 附加完整响应体到 Allure 报告
            allure.attach(
                json.dumps(create_result, indent=2, ensure_ascii=False),
                "商品创建-接口响应",
                allure.attachment_type.JSON
            )
            
            # 如果业务失败，记录详细错误信息
            if not create_result.get('businessSuccess'):
                error_detail = (
                    f"商品创建业务失败\n"
                    f"  错误码: {create_result.get('errorCode', 'N/A')}\n"
                    f"  错误类型: {create_result.get('responseType', 'N/A')}\n"
                    f"  错误信息: {create_result.get('errorMessage', '未知错误')}"
                )
                allure.attach(error_detail, "业务错误详情", attachment_type=allure.attachment_type.TEXT)
        
        # 断言商品创建接口响应
        with allure.step("断言1: 商品创建业务成功"):
            assert create_result.get('businessSuccess') is True, (
                f"商品创建业务失败！\n"
                f"  期望值: True\n"
                f"  实际值: {create_result.get('businessSuccess')}\n"
                f"  错误码: {create_result.get('errorCode', 'N/A')}\n"
                f"  错误信息: {create_result.get('errorMessage', '未知错误')}"
            )
        
        with allure.step("断言2: 商品创建返回数据为 true"):
            assert create_result.get('data') is True, (
                f"商品创建 data 字段不符合预期！\n"
                f"  期望值: True\n"
                f"  实际值: {create_result.get('data')}"
            )
        
        with allure.step("断言3: 商品创建 RPC 结果为 SUCCESS"):
            assert create_result.get('rpcResult') == 'SUCCESS', (
                f"商品创建 rpcResult 不符合预期！\n"
                f"  期望值: SUCCESS\n"
                f"  实际值: {create_result.get('rpcResult')}\n"
                f"  错误码: {create_result.get('errorCode', 'N/A')}"
            )

        # ---------- 步骤4：从数据库获取商品 id 和 product_spec_id ----------
        with allure.step("查询数据库获取商品 ID 和规格 ID"):
            row=db.fetch_one("SELECT id, product_id FROM llxz_product.ct_product WHERE name = %s ORDER BY create_time DESC LIMIT 1",(product_name,))
            assert row, f"未找到商品: {product_name}"
            product_id_db = row["id"]  # 自增主键 id
            product_code = row["product_id"]   # product_id 字段（业务编码）
            allure.attach(f"id = {product_id_db}, product_id = {product_code}", "商品信息", attachment_type=allure.attachment_type.TEXT)

            # 获取 product_spec_id（假设规格表有 product_spec_id 字段，关联到商品主键 id）
            spec_row=db.fetch_one("SELECT id FROM llxz_product.ct_product_spec WHERE item_id = %s LIMIT 1",(product_code,))
            assert spec_row, "未找到商品规格"
            product_spec_id = spec_row["id"]
            allure.attach(f"product_spec_id = {product_spec_id}", "规格ID", attachment_type=allure.attachment_type.TEXT)

        # ---------- 步骤5：调用审核通过接口 ----------
        with allure.step("加载审核接口请求模板"):
            # 构建审核 YAML 文件路径
            audit_yaml_path = project_root / "data" / "scenario" / "product" / "product_audit_api.yaml"
            
            # 验证文件是否存在
            if not audit_yaml_path.exists():
                raise FileNotFoundError(f"审核 YAML 配置文件不存在: {audit_yaml_path}")
            
            # 加载审核配置
            with open(audit_yaml_path, 'r', encoding='utf-8') as f:
                audit_data = yaml.safe_load(f)
            
            audit_case = audit_data['product_audit_tests'][0]  # 取第一个用例
            audit_body = audit_case['body']
            
            # 构造替换变量
            audit_vars = {
                "id": product_id_db,
                "spec_id": product_spec_id  # 修复：变量名必须与 YAML 中的 ${spec_id} 匹配
            }
            
            # 替换占位符
            audit_payload = replace_placeholders(audit_body, audit_vars)
            allure.attach(json.dumps(audit_payload, indent=2), "审核请求体", attachment_type=allure.attachment_type.JSON)
        with allure.step("发送 POST 请求到 /hzsx/examineProduct/productAudit"):
            # 发送审核请求
            audit_response_obj = admin_api_client.post("/hzsx/examineProduct/productAudit", json=audit_payload)
            
            # 附加 HTTP 状态码
            allure.attach(
                str(audit_response_obj.status_code),
                "HTTP 状态码",
                attachment_type=allure.attachment_type.TEXT
            )
            
            # 解析响应数据
            audit_result = audit_response_obj.json()
            
            # 附加完整响应体到 Allure 报告
            allure.attach(
                json.dumps(audit_result, indent=2, ensure_ascii=False),
                "商品审核-接口响应",
                attachment_type=allure.attachment_type.JSON
            )
            
            # 如果业务失败，记录详细错误信息
            if not audit_result.get('businessSuccess'):
                error_detail = (
                    f"商品审核业务失败\n"
                    f"  错误码: {audit_result.get('errorCode', 'N/A')}\n"
                    f"  错误类型: {audit_result.get('responseType', 'N/A')}\n"
                    f"  错误信息: {audit_result.get('errorMessage', '未知错误')}"
                )
                allure.attach(error_detail, "业务错误详情", attachment_type=allure.attachment_type.TEXT)

        # 断言商品审核接口响应
        with allure.step("断言4: 商品审核业务成功"):
            assert audit_result.get('businessSuccess') is True, (
                f"商品审核业务失败！\n"
                f"  期望值: True\n"
                f"  实际值: {audit_result.get('businessSuccess')}\n"
                f"  错误码: {audit_result.get('errorCode', 'N/A')}\n"
                f"  错误信息: {audit_result.get('errorMessage', '未知错误')}"
            )
        
        with allure.step("断言5: 商品审核返回数据为 true"):
            assert audit_result.get('data') is True, (
                f"商品审核 data 字段不符合预期！\n"
                f"  期望值: True\n"
                f"  实际值: {audit_result.get('data')}"
            )
        
        with allure.step("断言6: 商品审核 RPC 结果为 SUCCESS"):
            assert audit_result.get('rpcResult') == 'SUCCESS', (
                f"商品审核 rpcResult 不符合预期！\n"
                f"  期望值: SUCCESS\n"
                f"  实际值: {audit_result.get('rpcResult')}\n"
                f"  错误码: {audit_result.get('errorCode', 'N/A')}"
            )


        # ---------- 步骤6：查询运营端审核标签配置（可选验证）----------
        with allure.step("查询运营端审核标签配置"):
            try:
                # 构造查询参数
                query_params = {"labelKey": "GoodsProcess"}
                
                # 发送 GET 请求
                label_response = api_client.get(
                    "/hzsx/userOrderMessagesNew/querySearchLabel",
                    params=query_params
                )
                
                # 附加 HTTP 状态码
                allure.attach(
                    str(label_response.status_code),
                    "HTTP 状态码",
                    attachment_type=allure.attachment_type.TEXT
                )
                
                # 解析响应数据
                label_data = label_response.json()
                
                # 附加完整响应体到 Allure 报告
                allure.attach(
                    json.dumps(label_data, indent=2, ensure_ascii=False),
                    "审核标签查询响应",
                    attachment_type=allure.attachment_type.JSON
                )
                
                # 断言业务成功
                with allure.step("断言8: 审核标签查询成功"):
                    assert label_data.get('businessSuccess') is True, (
                        f"审核标签查询失败！\n"
                        f"  期望值: True\n"
                        f"  实际值: {label_data.get('businessSuccess')}\n"
                        f"  错误信息: {label_data.get('errorMessage', '未知错误')}"
                    )
                    
            except Exception as e:
                # 记录详细错误信息
                error_detail = (
                    f"审核标签查询异常\n"
                    f"  错误类型: {type(e).__name__}\n"
                    f"  错误信息: {str(e)}\n"
                    f"  接口路径: /hzsx/userOrderMessagesNew/querySearchLabel\n"
                    f"  查询参数: {query_params}"
                )
                allure.attach(error_detail, "错误详情", attachment_type=allure.attachment_type.TEXT)
                raise

        # ---------- 步骤7：验证数据库中的审核状态是否为 2 ----------
        with allure.step("查询数据库验证商品审核状态"):
            try:
                # 查询数据库获取审核状态（返回格式：{'audit_state': 2}）
                result = db.fetch_one("SELECT audit_state FROM llxz_product.ct_product WHERE id = %s",(product_id_db,))
                # 验证查询结果是否存在
                assert result is not None, f"未找到商品记录，id={product_id_db}"
                # 提取审核状态值
                actual_audit_state = result.get('audit_state')
                assert actual_audit_state is not None, "数据库中 audit_state 字段为空"
                # 附加到 Allure 报告
                allure.attach(
                    f"商品ID: {product_id_db}\n审核状态: {actual_audit_state}",
                    "数据库审核状态",
                    attachment_type=allure.attachment_type.TEXT
                )
                
                # 断言审核状态应为 2（审核通过）
                with allure.step("断言7: 审核状态应为 2（审核通过）"):
                    assert actual_audit_state == 2, (
                        f"商品审核状态不符合预期！\n"
                        f"  期望值: 2\n"
                        f"  实际值: {actual_audit_state}\n"
                        f"  商品ID: {product_id_db}"
                    )
                    
            except Exception as e:
                # 记录详细错误信息到 Allure 报告
                error_detail = (
                    f"数据库查询或验证失败\n"
                    f"  错误类型: {type(e).__name__}\n"
                    f"  错误信息: {str(e)}\n"
                    f"  商品ID: {product_id_db}"
                )
                allure.attach(error_detail, "错误详情", attachment_type=allure.attachment_type.TEXT)
                raise

        allure.attach("完整流程验证通过：商品创建成功 → 审核接口调用成功 → 审核状态变为2",
                      "最终结果", attachment_type=allure.attachment_type.TEXT)