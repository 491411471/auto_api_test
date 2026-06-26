# testcases/admin/api/product_management/test_product_edit.py
"""
运营端 - 商品管理：商品列表-编辑商品测试

完整的商品编辑流程，包含6个步骤：
  长租模式：
    步骤1: 查询店铺商品-长租（获取最后一个商品id）
    步骤2: 获取商品信息-长租（查询商品详情）
    步骤3: 修改商品信息-长租（增加规格3、修改名称、修改地址）
  短租模式：
    步骤4: 查询店铺商品-短租（获取最后一个商品id）
    步骤5: 获取商品信息-短租（查询商品详情）
    步骤6: 修改商品信息-短租（增加规格3、修改日历库存）

数据策略：所有测试数据在YAML中定义，Python代码仅负责：
  1. 从响应中提取变量
  2. 将商品详情转换为YAML模板所需的变量（保持原始数据结构完整）
  3. 调用框架执行测试用例

关键修复（2026-06-25）：
  - 保留SKU的所有原始字段（skuId、cycs、parts等）
  - 不修改cycs中的审计字段（id、createTime、itemId等）
  - 确保数值类型正确（skuId为整数，不是字符串）
"""
import json
import uuid
import random
from datetime import datetime, timedelta
from copy import deepcopy

import allure
import pytest

from common.logger import logger
from common.test_helpers import replace_placeholders, validate_response
from utils.assert_utils import assert_status_code
from utils.data_loader import get_test_data, get_global_variables
from utils.variable_utils import validate, get_value_by_path

_DATA_FILE = "data/admin/api/product_management/product_edit_tests.yaml"


@allure.epic("运营端")
@allure.feature("运营端-商品管理")
@allure.story("商品列表-编辑商品")
class TestProductEdit:
    """商品列表-编辑商品 - 6 个步骤串联"""

    # ==================== 跨步骤共享变量 ====================
    _global_vars = None
    _product_id_long = None  # 长租商品ID
    _product_detail_long = None  # 长租商品详情
    _product_id_short = None  # 短租商品ID
    _product_detail_short = None  # 短租商品详情

    @classmethod
    def _load_global_vars(cls):
        """加载 YAML 全局变量（懒加载 + 缓存）"""
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    # ==================== 辅助方法 ====================
    def _send_request_and_assert(self, api_client, case: dict, global_vars: dict):
        """
        发送请求并执行基础断言。
        返回 response_data。
        """
        # 如果存在 json_template，先将其转换为 json
        if "json_template" in case:
            case = deepcopy(case)
            case["json"] = case.pop("json_template")
        
        case_replaced = replace_placeholders(case, global_vars)

        with allure.step("发送请求"):
            endpoint = case_replaced.get("endpoint", "")
            method = case_replaced.get("method", "GET").upper()

            if method == "GET":
                params = case_replaced.get("params", {})
                allure.attach(
                    json.dumps(params, ensure_ascii=False, indent=2, default=str),
                    name="请求参数",
                    attachment_type=allure.attachment_type.JSON,
                )
                resp = api_client.get(endpoint, params=params)
            else:
                body_data = case_replaced.get("json", {})
                allure.attach(
                    json.dumps(body_data, ensure_ascii=False, indent=2, default=str),
                    name="请求体 (JSON)",
                    attachment_type=allure.attachment_type.JSON,
                )
                resp = api_client.post(endpoint, json=body_data)

            response_data = resp.json()
            allure.attach(
                json.dumps(response_data, ensure_ascii=False, indent=2, default=str),
                name="完整响应体",
                attachment_type=allure.attachment_type.JSON,
            )

        # 基础断言（使用替换后的case_replaced）
        with allure.step("执行基础断言"):
            assert_status_code(resp.status_code, case_replaced["expected_status"])
            for check in case_replaced["validate_data"]:
                path = check["path"].lstrip("$").lstrip(".")
                actual = get_value_by_path(response_data, path)
                validate(actual, check["operator"], check.get("value"), path)

        return response_data

    @staticmethod
    def _extract_product_vars(product_detail: dict) -> dict:
        """
        从商品详情中提取YAML模板所需的所有变量。
        返回变量字典，可直接合并到 global_vars 中。
        """
        vars_dict = {}
        
        # 基础字段
        for field in [
            "categoryId", "categoryIds", "name", "title", "oldNewDegree",
            "makeOrderServicesIds", "buyOutSupport", "minRentCycle", "maxRentCycle",
            "type", "detail", "freightType", "addIds", "images", "sellPoints",
            "id", "productId", "channelGroupCode", "icon", "iconType",
            "speFirstName", "speSecName", "showPriceRatio", "lockState",
            "commonProblem", "rentalProcess", "productType", "detailButler",
            "province", "city", "itemFineness", "source", "colorSpecs",
            "aliPayImages", "productColorPicture", "specs"
        ]:
            if field in product_detail:
                value = product_detail[field]
                # 关键修复：categoryIds不能为null或空数组，必须是有效的分类ID数组
                # 正确格式：[父级ID, 当前级ID] 例如 [137, 139]
                # 后端代码访问categoryIds[1]，所以数组至少需要2个元素
                if field == "categoryIds":
                    if value is None or len(value) == 0:
                        # 使用categoryId构建分类数组
                        category_id = product_detail.get("categoryId")
                        if category_id:
                            # 构建二级分类数组：[父级ID, 当前级ID]
                            # 如果无法获取父级ID，使用categoryId作为占位符
                            value = [category_id, category_id]
                            logger.warning(f"[警告] 商品详情中categoryIds为null，使用默认值: {value}")
                        else:
                            value = [0, 0]  # 极端情况，使用默认值
                            logger.warning(f"[警告] categoryId也为null，使用默认值: {value}")
                vars_dict[field] = value
        
        return vars_dict

    @staticmethod
    def _add_spec3_to_skuses(product_skuses: list) -> list:
        """
        为每个SKU增加规格3。
        
        关键：保持原有数据结构完整，只修改specAll字段！
        - 保留skuId（整数类型）
        - 保留cycs数组（包含id、createTime、itemId等审计字段）
        - 保留parts数组（不能为null，必须是数组）
        - 删除spuSpecs字段（后端不需要）
        - 清理specAll中的多余字段（specSource、specValueId）
        """
        updated_skuses = []
        for sku in product_skuses:
            # 深拷贝保持所有原始字段
            sku_copy = deepcopy(sku)
            
            # 确保skuId是整数类型
            if "skuId" in sku_copy:
                sku_copy["skuId"] = int(sku_copy["skuId"])
            
            # 关键修复1：parts不能为null，必须是数组
            if "parts" not in sku_copy or sku_copy["parts"] is None:
                sku_copy["parts"] = []
            
            # 关键修复2：删除spuSpecs字段（后端不需要）
            sku_copy.pop("spuSpecs", None)
            
            # 关键修复3：确保sort字段存在
            if "sort" not in sku_copy:
                sku_copy["sort"] = 1
            
            # 增加规格3到specAll
            if "specAll" not in sku_copy:
                sku_copy["specAll"] = []
            
            # 清理specAll中的多余字段，但保留specSource和specValueId
            cleaned_spec_all = []
            for spec in sku_copy["specAll"]:
                cleaned_spec = {
                    "platformSpecId": spec.get("platformSpecId"),
                    "opeSpecId": spec.get("opeSpecId"),
                    "platformSpecName": spec.get("platformSpecName"),
                    "platformSpecValue": spec.get("platformSpecValue"),
                    # 🔧 关键修复：保留specSource和specValueId字段
                    "specSource": spec.get("specSource"),
                    "specValueId": spec.get("specValueId")
                }
                cleaned_spec_all.append(cleaned_spec)
            sku_copy["specAll"] = cleaned_spec_all
            
            # 检查是否已有规格3
            has_spec3 = any(s.get("opeSpecId") == 3 for s in sku_copy["specAll"])
            if not has_spec3:
                # 原本没有规格3，添加
                logger.info(f"[规格3] SKU {sku_copy.get('skuId')} 原本没有规格3，正在添加...")
                sku_copy["specAll"].append({
                    "platformSpecId": None,
                    "opeSpecId": 3,
                    "platformSpecName": None,
                    "platformSpecValue": "3",
                    "specSource": 1,
                    "specValueId": None
                })
            else:
                # 已有规格3，可以选择：
                # 选项1：跳过（当前行为）
                logger.info(f"[规格3] SKU {sku_copy.get('skuId')} 已存在规格3，跳过添加")
                # 选项2：如果要强制添加，取消下面的注释
                # logger.info(f"[规格3] SKU {sku_copy.get('skuId')} 已存在规格3，但仍强制添加")
                # sku_copy["specAll"].append({
                #     "platformSpecId": None,
                #     "opeSpecId": 3,
                #     "platformSpecName": None,
                #     "platformSpecValue": "3-新增"
                # })
            
            # 添加uuid（如果不存在）
            if "uuid" not in sku_copy:
                sku_copy["uuid"] = str(uuid.uuid4())
            
            updated_skuses.append(sku_copy)
        
        return updated_skuses

    @staticmethod
    def _add_spec3_to_specs(specs: list) -> list:
        """
        在specs中增加规格3。
        """
        specs_copy = deepcopy(specs)
        
        # 检查是否已有规格3
        has_spec3 = any(s.get("opeSpecId") == 3 for s in specs_copy)
        if not has_spec3:
            specs_copy.append({
                "name": "品牌",
                "opeSpecId": 3,
                "values": [
                    {"name": "3", "productSpecId": None}
                ]
            })
        
        return specs_copy

    @staticmethod
    def _generate_calendar_inventory(days: int = 16, inventory: int = 1000) -> dict:
        """
        生成日历库存数据。
        从当前日期开始，往后推days天，每天库存设置为inventory。
        """
        now = datetime.now()
        date_inventory_map = {}
        for i in range(days):
            date_str = (now + timedelta(days=i)).strftime("%Y-%m-%d")
            date_inventory_map[date_str] = inventory
        
        return date_inventory_map

    @staticmethod
    def _build_product_skus_inventory_with_calendar(product_skus_inventory_list: list) -> list:
        """
        为短租商品构建带日历库存的productSkusInventoryList。
        """
        updated_list = []
        calendar_inventory = TestProductEdit._generate_calendar_inventory(16, 1000)
        
        for item in product_skus_inventory_list:
            item_copy = deepcopy(item)
            item_copy["productSpecName3"] = "3"
            item_copy["dateDayInventoryMap"] = calendar_inventory
            updated_list.append(item_copy)
        
        return updated_list

    @staticmethod
    def _build_calendar_with_spec3(product_skuses: list) -> list:
        """
        为短租商品构建calendar数据（带规格3）。
        根据正确的请求参数格式，需要：
        1. 保留原始SKU的完整结构（第一个calendar项）- 需要添加规格3
        2. 添加新的SKU变体（第二个calendar项，包含规格3的不同值"33"）
        """
        calendar_list = []
        
        for sku in product_skuses:
            # ========== 第一个calendar项：原始SKU（完整结构） ==========
            calendar_item_original = deepcopy(sku)
            
            # 清理specAll，但保留所有必要字段
            if "specAll" in calendar_item_original:
                cleaned_spec_all = []
                for spec in calendar_item_original["specAll"]:
                    cleaned_spec = {
                        "platformSpecId": spec.get("platformSpecId"),
                        "opeSpecId": spec.get("opeSpecId"),
                        "platformSpecName": spec.get("platformSpecName"),
                        "platformSpecValue": spec.get("platformSpecValue"),
                        "specSource": spec.get("specSource"),
                        "specValueId": spec.get("specValueId")
                    }
                    cleaned_spec_all.append(cleaned_spec)
                calendar_item_original["specAll"] = cleaned_spec_all
            else:
                calendar_item_original["specAll"] = []
            
            # 检查并添加规格3
            has_spec3 = any(s.get("opeSpecId") == 3 for s in calendar_item_original["specAll"])
            if not has_spec3:
                logger.info(f"[规格3-calendar] 原始SKU {calendar_item_original.get('skuId')} 没有规格3，正在添加...")
                calendar_item_original["specAll"].append({
                    "platformSpecId": None,
                    "opeSpecId": 3,
                    "platformSpecName": None,
                    "platformSpecValue": "3",
                    "specSource": 1,
                    "specValueId": None
                })
            else:
                logger.info(f"[规格3-calendar] 原始SKU {calendar_item_original.get('skuId')} 已存在规格3")
            
            # 确保其他必要字段
            if "parts" not in calendar_item_original or calendar_item_original["parts"] is None:
                calendar_item_original["parts"] = []
            calendar_item_original.pop("spuSpecs", None)
            if "uuid" not in calendar_item_original:
                calendar_item_original["uuid"] = str(uuid.uuid4())
            
            calendar_list.append(calendar_item_original)
            
            # ========== 第二个calendar项：新SKU变体（简化结构，规格3值为"33"） ==========
            # 直接复制原始SKU的完整结构
            calendar_item_new = deepcopy(sku)
            
            # 清理specAll
            if "specAll" in calendar_item_new:
                cleaned_spec_all = []
                for spec in calendar_item_new["specAll"]:
                    cleaned_spec = {
                        "platformSpecId": spec.get("platformSpecId"),
                        "opeSpecId": spec.get("opeSpecId"),
                        "platformSpecName": spec.get("platformSpecName"),
                        "platformSpecValue": spec.get("platformSpecValue"),
                        "specSource": spec.get("specSource"),
                        "specValueId": spec.get("specValueId")
                    }
                    cleaned_spec_all.append(cleaned_spec)
                calendar_item_new["specAll"] = cleaned_spec_all
            else:
                calendar_item_new["specAll"] = []
            
            # 移除原有的规格3（如果有），然后添加新的规格3（值为"33"）
            calendar_item_new["specAll"] = [
                s for s in calendar_item_new["specAll"] if s.get("opeSpecId") != 3
            ]
            calendar_item_new["specAll"].append({
                "platformSpecId": None,
                "opeSpecId": 3,
                "platformSpecName": None,
                "platformSpecValue": "33",
                "specSource": 1,
                "specValueId": None
            })
            
            # 确保其他必要字段
            if "parts" not in calendar_item_new or calendar_item_new["parts"] is None:
                calendar_item_new["parts"] = []
            calendar_item_new.pop("spuSpecs", None)
            calendar_item_new["uuid"] = str(uuid.uuid4())
            
            calendar_list.append(calendar_item_new)
        
        return calendar_list

    # ==================== 长租模式 ====================
    # 步骤1: 查询店铺商品-长租
    @pytest.mark.order(1)
    @allure.title("PE_001 | 查询店铺商品-长租")
    def test_step1_query_long_rental(self, admin_api_client, db):
        """步骤1：查询长租模式已审核商品列表，获取最后一个商品的id"""
        case = get_test_data(_DATA_FILE, "step1_query_long_rental")
        global_vars = self._load_global_vars()
        allure.dynamic.description(case.get("description", ""))

        response_data = self._send_request_and_assert(admin_api_client, case, global_vars)

        # 检查 records 是否为空
        records = response_data.get("data", {}).get("records", [])
        if not records:
            skip_msg = "未查询到长租商品，跳过后续测试"
            logger.warning(f"[跳过] {skip_msg}")
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        # 随机选择一个商品（不再固定最后一个）
        selected_product = random.choice(records)
        self.__class__._product_id_long = selected_product["id"]
        
        logger.info(f"[PE_001] 随机选择长租商品ID: {self._product_id_long}（共{len(records)}个商品）")
        allure.attach(
            f"长租商品ID: {self._product_id_long}\n商品名称: {selected_product.get('name', '')}\n商品总数: {len(records)}",
            name="提取的商品数据",
            attachment_type=allure.attachment_type.TEXT,
        )

    # 步骤2: 获取商品信息-长租
    @pytest.mark.order(2)
    @allure.title("PE_002 | 获取商品信息-长租")
    def test_step2_get_product_detail_long(self, admin_api_client, db):
        """步骤2：根据商品id查询商品详情信息"""
        if not self.__class__._product_id_long:
            pytest.skip("步骤1未获取到商品ID，跳过")

        case = get_test_data(_DATA_FILE, "step2_get_product_detail_long")
        global_vars = self._load_global_vars()
        global_vars["product_id_long"] = self.__class__._product_id_long
        allure.dynamic.description(case.get("description", ""))

        response_data = self._send_request_and_assert(admin_api_client, case, global_vars)

        # 保存商品详情供后续使用
        self.__class__._product_detail_long = response_data.get("data", {})
        logger.info(f"[PE_002] 获取商品详情成功: {self._product_id_long}")

    # 步骤3: 修改商品信息-长租
    @pytest.mark.order(3)
    @allure.title("PE_003 | 修改商品信息-长租")
    def test_step3_update_product_long(self, admin_api_client, db):
        """步骤3：编辑长租商品，增加规格3、修改名称、修改地址"""
        if not self.__class__._product_detail_long:
            pytest.skip("步骤2未获取到商品详情，跳过")

        case = get_test_data(_DATA_FILE, "step3_update_product_long")
        global_vars = self._load_global_vars()
        global_vars["product_id_long"] = self.__class__._product_id_long
        allure.dynamic.description(case.get("description", ""))

        # 从商品详情中提取变量
        product_vars = self._extract_product_vars(self._product_detail_long)
        global_vars.update(product_vars)
        
        # 调试：打印categoryIds的值
        logger.info(f"[调试] categoryId: {global_vars.get('categoryId')}")
        logger.info(f"[调试] categoryIds: {global_vars.get('categoryIds')}")
        
        # 打印编辑商品的商品信息
        product_id = self._product_detail_long.get("id")
        product_code = self._product_detail_long.get("productId")
        product_name = self._product_detail_long.get("name")
        logger.info(f"[PE_003] 正在编辑长租商品 - 商品ID: {product_id}, 商品编码: {product_code}, 商品名称: {product_name}")
        
        # 处理SKU数据：增加规格3（保持原始结构完整）
        if "productSkuses" in self._product_detail_long:
            global_vars["productSkuses_with_spec3"] = self._add_spec3_to_skuses(
                self._product_detail_long["productSkuses"]
            )
            # 调试：打印第一个SKU的specAll
            first_sku = global_vars["productSkuses_with_spec3"][0]
            logger.info(f"[调试-长租] 第一个SKU {first_sku.get('skuId')} 的specAll: {json.dumps(first_sku.get('specAll', []), ensure_ascii=False, indent=2)}")
        
        # 处理specs数据：增加规格3
        if "specs" in self._product_detail_long:
            global_vars["specs_with_spec3"] = self._add_spec3_to_specs(
                self._product_detail_long["specs"]
            )
        
        # 生成规格3的UUID
        global_vars["spec3_uuid_1"] = str(uuid.uuid4())
        global_vars["spec3_uuid_2"] = str(uuid.uuid4())

        allure.attach(
            json.dumps(global_vars.get("productSkuses_with_spec3", {}), ensure_ascii=False, indent=2, default=str),
            name="处理后的SKU数据（含规格3）",
            attachment_type=allure.attachment_type.JSON,
        )

        self._send_request_and_assert(admin_api_client, case, global_vars)
        logger.info(f"[PE_003] 长租商品编辑成功 - 商品ID: {product_id}, 商品编码: {product_code}")

    # ==================== 短租模式 ====================
    # 步骤4: 查询店铺商品-短租
    @pytest.mark.order(4)
    @allure.title("PE_004 | 查询店铺商品-短租")
    def test_step4_query_short_rental(self, admin_api_client, db):
        """步骤4：查询短租模式已审核商品列表，获取最后一个商品的id"""
        case = get_test_data(_DATA_FILE, "step4_query_short_rental")
        global_vars = self._load_global_vars()
        allure.dynamic.description(case.get("description", ""))

        response_data = self._send_request_and_assert(admin_api_client, case, global_vars)

        # 检查 records 是否为空
        records = response_data.get("data", {}).get("records", [])
        if not records:
            skip_msg = "未查询到短租商品，跳过后续测试"
            logger.warning(f"[跳过] {skip_msg}")
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        # 随机选择一个商品（不再固定最后一个）
        selected_product = random.choice(records)
        self.__class__._product_id_short = selected_product["id"]
        
        logger.info(f"[PE_004] 随机选择短租商品ID: {self._product_id_short}（共{len(records)}个商品）")
        allure.attach(
            f"短租商品ID: {self._product_id_short}\n商品名称: {selected_product.get('name', '')}\n商品总数: {len(records)}",
            name="提取的商品数据",
            attachment_type=allure.attachment_type.TEXT,
        )

    # 步骤5: 获取商品信息-短租
    @pytest.mark.order(5)
    @allure.title("PE_005 | 获取商品信息-短租")
    def test_step5_get_product_detail_short(self, admin_api_client, db):
        """步骤5：根据商品id查询商品详情信息"""
        if not self.__class__._product_id_short:
            pytest.skip("步骤4未获取到商品ID，跳过")

        case = get_test_data(_DATA_FILE, "step5_get_product_detail_short")
        global_vars = self._load_global_vars()
        global_vars["product_id_short"] = self.__class__._product_id_short
        allure.dynamic.description(case.get("description", ""))

        response_data = self._send_request_and_assert(admin_api_client, case, global_vars)

        # 保存商品详情供后续使用
        self.__class__._product_detail_short = response_data.get("data", {})
        logger.info(f"[PE_005] 获取商品详情成功: {self._product_id_short}")

    # 步骤6: 修改商品信息-短租
    @pytest.mark.order(6)
    @allure.title("PE_006 | 修改商品信息-短租")
    def test_step6_update_product_short(self, admin_api_client, db):
        """步骤6：编辑短租商品，增加规格3、修改日历库存"""
        if not self.__class__._product_detail_short:
            pytest.skip("步骤5未获取到商品详情，跳过")

        case = get_test_data(_DATA_FILE, "step6_update_product_short")
        global_vars = self._load_global_vars()
        global_vars["product_id_short"] = self.__class__._product_id_short
        allure.dynamic.description(case.get("description", ""))

        # 从商品详情中提取变量
        product_vars = self._extract_product_vars(self._product_detail_short)
        global_vars.update(product_vars)
        
        # 打印编辑商品的商品信息
        product_id = self._product_detail_short.get("id")
        product_code = self._product_detail_short.get("productId")
        product_name = self._product_detail_short.get("name")
        logger.info(f"[PE_006] 正在编辑短租商品 - 商品ID: {product_id}, 商品编码: {product_code}, 商品名称: {product_name}")
        
        # 处理SKU数据：增加规格3（保持原始结构完整）
        if "productSkuses" in self._product_detail_short:
            global_vars["productSkuses_with_spec3"] = self._add_spec3_to_skuses(
                self._product_detail_short["productSkuses"]
            )
            # 调试：打印第一个SKU的specAll
            first_sku = global_vars["productSkuses_with_spec3"][0]
            logger.info(f"[调试-短租] 第一个SKU {first_sku.get('skuId')} 的specAll: {json.dumps(first_sku.get('specAll', []), ensure_ascii=False, indent=2)}")
        
        # 构建calendar数据（短租模式特有）
        if "productSkuses" in self._product_detail_short:
            calendar_data = self._build_calendar_with_spec3(
                self._product_detail_short["productSkuses"]
            )
            global_vars["calendar_with_spec3"] = calendar_data
            # 打印第一个calendar项的specAll
            if calendar_data:
                first_calendar = calendar_data[0]
                logger.info(f"[调试-短租] 第一个calendar项的specAll: {json.dumps(first_calendar.get('specAll', []), ensure_ascii=False, indent=2)}")
                logger.info(f"[调试-短租] calendar项总数: {len(calendar_data)}")
        
        # 处理specs数据：增加规格3
        if "specs" in self._product_detail_short:
            global_vars["specs_with_spec3"] = self._add_spec3_to_specs(
                self._product_detail_short["specs"]
            )
        
        # 处理日历库存数据
        if "productSkusInventoryList" in self._product_detail_short:
            global_vars["productSkusInventoryList_with_calendar"] = self._build_product_skus_inventory_with_calendar(
                self._product_detail_short["productSkusInventoryList"]
            )
        
        # 删除重复的calendar构建代码（已在上面构建）
        
        # 生成规格3的UUID
        global_vars["spec3_uuid_1"] = str(uuid.uuid4())
        global_vars["spec3_uuid_2"] = str(uuid.uuid4())

        allure.attach(
            json.dumps(global_vars.get("productSkusInventoryList_with_calendar", {}), ensure_ascii=False, indent=2, default=str),
            name="处理后的日历库存数据",
            attachment_type=allure.attachment_type.JSON,
        )

        self._send_request_and_assert(admin_api_client, case, global_vars)
        logger.info(f"[PE_006] 短租商品编辑成功 - 商品ID: {product_id}, 商品编码: {product_code}")
