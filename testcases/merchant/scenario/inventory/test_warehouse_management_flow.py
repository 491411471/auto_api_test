import json
import allure
from pathlib import Path
import yaml
import uuid as uuid_module

from utils.product_utils import replace_placeholders


def load_warehouse_template(yaml_path: str) -> dict:
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# ==================== 测试类 ====================
@allure.epic("商家端")
@allure.feature("库存管理")
@allure.story("新增仓库 → 新增商品库存")
class TestWarehouseManagement:

    @staticmethod
    def _send_and_assert(api_client, endpoint, payload, name):
        """发送请求并断言核心字段的通用方法"""
        with allure.step(f"发送{name}请求"):
            allure.attach(json.dumps(payload, indent=2, ensure_ascii=False), f"{name}-请求体", allure.attachment_type.JSON)
            response = api_client.post(endpoint, json=payload)
            result = response.json()
            allure.attach(json.dumps(result, indent=2, ensure_ascii=False), f"{name}-响应体", allure.attachment_type.JSON)
            
        with allure.step(f"断言: {name}成功"):
            assert result.get('businessSuccess') is True, f"{name}业务失败，错误: {result.get('errorMessage', '未知')}"
            assert result.get('data') is True, f"{name} data不为True"
            assert result.get('rpcResult') == 'SUCCESS', f"{name} rpcResult不为SUCCESS"
        return result

    @allure.title("完整流程：新增仓库 → 获取新建仓库id → 新增商品库存")
    def test_create_warehouse_and_add_product_stock(self, api_client, db):
        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        yaml_path = project_root / "data" / "merchant" / "scenario" / "inventory" / "warehouse_management_api.yaml"
        
        # ---------- 步骤1：加载模板与生成动态数据 ----------
        with allure.step("加载模板与生成动态数据"):
            if not yaml_path.exists():
                raise FileNotFoundError(f"YAML 配置文件不存在: {yaml_path}")
            templates = load_warehouse_template(str(yaml_path))
            
            from faker import Faker
            fake = Faker('zh_CN')
            variables = {
                "street": f"{fake.street_address()}{fake.building_number()}--自动化测试",
                "warehouse_name": f"自动化测试--新增仓库-{fake.random_int(min=1000, max=9999)}",
                "uuid_1": str(uuid_module.uuid4()),
                "uuid_2": str(uuid_module.uuid4()),
                "shipping_list_1": f"{fake.random_int(min=50, max=200)}件{fake.word()}手机外壳",
                "accessory_name_1": "手机外壳",
                "shipping_list_2": f"{fake.random_int(min=50, max=200)}件{fake.word()}手机数据线",
                "accessory_name_2": "数据线",
                "province": templates["variables"]["province"],
                "city": templates["variables"]["city"],
                "area": templates["variables"]["area"],
                "total_quantity": templates["variables"]["total_quantity"],
                "available_quantity": templates["variables"]["available_quantity"],
                "warehouse_id": 31,
                "category_ids": templates["variables"]["category_ids"]
            }
            allure.attach(json.dumps(variables, indent=2, ensure_ascii=False, default=str), "动态测试数据", allure.attachment_type.JSON)

        # ---------- 步骤2：新增仓库 ----------
        warehouse_template = templates["warehouse_management_tests"][0]
        warehouse_payload = replace_placeholders(warehouse_template.get("json", {}), variables)
        self._send_and_assert(api_client, warehouse_template.get("endpoint"), warehouse_payload, "新增仓库")

        # ---------- 步骤3：获取新建仓库id ----------
        with allure.step("获取新建仓库id"):
            query_sql = f"select id from llxz_user.ct_inventory_sync_warehouse_address where warehouse_name = '{variables['warehouse_name']}' order by create_time DESC limit 1"
            db_warehouse_result = db.fetch_one(query_sql)
            assert db_warehouse_result is not None, f"未查到新建的仓库记录，warehouse_name={variables['warehouse_name']}"
            variables["warehouse_id"] = db_warehouse_result.get('id')
            allure.attach(f"新建仓库id: {variables['warehouse_id']}", "仓库id", allure.attachment_type.TEXT)

        # ---------- 步骤4：新增商品库存 ----------
        with allure.step("发送新增商品库存请求"):
            stock_template = templates["warehouse_management_tests"][1]
            stock_payload = replace_placeholders(stock_template.get("json", {}), variables)
            allure.attach(json.dumps(stock_payload, indent=2, ensure_ascii=False), "新增商品库存-请求体", allure.attachment_type.JSON)
            
            stock_response = api_client.post(stock_template.get("endpoint"), json=stock_payload)
            stock_result = stock_response.json()
            allure.attach(json.dumps(stock_result, indent=2, ensure_ascii=False), "新增商品库存-响应体", allure.attachment_type.JSON)

            # 处理冲突重试
            if not stock_result.get('businessSuccess') and stock_result.get("errorMessage") == "商品库存分类已存在!":
                with allure.step("处理商品库存分类已存在冲突并重试"):
                    category_id = templates["variables"]["category_ids"][0]
                    db.execute_update(f"UPDATE llxz_product.ct_inventory_sync_product_stock SET delete_time = NOW() WHERE parent_category_id = {category_id};")
                    allure.attach(f"清理类目id: {category_id}的历史数据", "清理历史数据", allure.attachment_type.TEXT)
                    stock_response = api_client.post(stock_template.get("endpoint"), json=stock_payload)
                    stock_result = stock_response.json()
                    allure.attach(json.dumps(stock_result, indent=2, ensure_ascii=False), "重试-新增商品库存-响应体", allure.attachment_type.JSON)

        with allure.step("断言: 新增商品库存成功"):
            assert stock_result.get('businessSuccess') is True, f"新增商品库存业务失败，错误: {stock_result.get('errorMessage', '未知')}"
            assert stock_result.get('data') is True, "新增商品库存 data不为True"
            assert stock_result.get('rpcResult') == 'SUCCESS', "新增商品库存 rpcResult不为SUCCESS"

        # ---------- 步骤5：清理类目下的商品库存 ----------
        with allure.step("清理类目下的商品库存"):
            db.execute_update("UPDATE llxz_product.ct_inventory_sync_product_stock SET delete_time = NOW() WHERE parent_category_id = 10 AND delete_time IS NULL;")
            allure.attach("已清理类目id: 10下的历史库存数据", "清理历史数据", allure.attachment_type.TEXT)

        allure.attach("完整流程验证通过：新增仓库成功 → 新增商品库存成功", "最终结果", allure.attachment_type.TEXT)
