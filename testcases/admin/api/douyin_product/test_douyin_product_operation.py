# testcases/admin/api/douyin_product/test_douyin_product_operation.py
"""
运营端 - 商品管理：抖音商品操作接口测试

覆盖场景：
  DPO_001: 批量库存设置（SQL获取productIds + API）
  DPO_002: 绑定门店（SQL查询门店 + 绑定API）
  DPO_003: 修改商品（查询列表 → 查询编辑信息 → 修改API）
  DPO_004: 商品下架（查询已上架 → 下架API）
  DPO_005: 商品上架（查询不显示 → 上架API）
  DPO_006: 复制商品（查询列表 → 复制API）
  DPO_007: 关锁商品（SQL查询未关锁 → 关锁API）
  DPO_008: 开锁商品（SQL查询已关锁 → 开锁API）

数据策略：复杂场景（分步骤，Class 组织，@pytest.mark.order）
"""
import allure
import pytest
import random
from datetime import datetime

from common.logger import logger
from common.test_helpers import execute_test_case, process_dynamic_data, replace_placeholders
from utils.data_loader import get_test_data, get_global_variables


_DATA_FILE = "data/admin/api/douyin_product/douyin_product_operation_api.yaml"

# 预加载所有用例数据
_ALL_CASES = get_test_data(_DATA_FILE, "douyin_product_operation_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 douyin_product_operation_api.yaml")


@allure.epic("运营端")
@allure.feature("运营端-商品管理")
@allure.story("抖音商品操作")
class TestDouyinProductOperation:
    """抖音商品操作测试：库存设置、绑定门店、修改、上下架、复制、关锁/开锁"""

    # ==================== TC_001: 批量库存设置 ====================
    @pytest.mark.order(1)
    @allure.title("DPO_001 - 抖音商品批量库存设置")
    def test_batch_inventory(self, admin_api_client, db):
        """SQL查询2个抖音商品product_id，批量设置库存为10"""
        case = _ALL_CASES[0]  # DPO_001
        global_vars = get_global_variables(_DATA_FILE).copy()
        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== TC_002: 绑定门店 ====================
    @pytest.mark.order(2)
    @allure.title("DPO_002 - 抖音商品绑定门店")
    def test_bind_shop(self, admin_api_client, db):
        """查询门店信息 → 查询抖音商品列表 → 绑定门店"""
        case_s1 = _ALL_CASES[1]  # DPO_002_S1
        case_s2 = _ALL_CASES[2]  # DPO_002_S2
        case_s3 = _ALL_CASES[3]  # DPO_002_S3
        global_vars = get_global_variables(_DATA_FILE).copy()

        # 步骤1:仅执行SQL查询门店信息(不发API请求)
        process_dynamic_data(case_s1, db, global_vars)
        logger.info(f"[DPO_002_S1] 门店: shop_name={global_vars.get('shop_name')}, shop_id={global_vars.get('shop_id')}")

        # 步骤2:查询抖音商品列表,随机获取1-2个商品id
        # 先替换json中的变量占位符
        json_data = replace_placeholders(case_s2.get("json", {}), global_vars)
        # 直接调用API获取响应,不通过execute_test_case(避免重复请求和断言)
        resp = admin_api_client.post(case_s2["endpoint"], json=json_data)
        data = resp.json()
        records = data.get("data", {}).get("records", [])

        if not records:
            allure.attach("查询结果为空,抖音商品列表无数据", name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip("抖音商品列表为空,跳过绑定门店操作")

        # 随机选择1-2个商品
        count = random.randint(1, min(2, len(records)))
        selected_records = random.sample(records, count)
        ids = [str(record.get("id")) for record in selected_records]
        global_vars["ids"] = ids
        logger.info(f"[DPO_002_S2] 随机选择{count}个商品 ids={ids}")
        allure.attach(
            f"从{len(records)}个商品中随机选择{count}个: {ids}",
            name="步骤2-选择商品",
            attachment_type=allure.attachment_type.TEXT
        )

        # 步骤3:绑定门店(使用步骤1的SQL变量和步骤2的商品id)
        execute_test_case(case_s3, admin_api_client, db, global_vars)

    # ==================== TC_003: 修改商品 ====================
    @pytest.mark.order(3)
    @allure.title("DPO_003_S1 - 查询抖音商品列表(修改用)")
    def test_edit_step1_query_list(self, admin_api_client, db):
        """查询抖音商品列表，随机选择一个商品的productId"""
        case = _ALL_CASES[4]  # DPO_003_S1
        self.__class__._edit_global_vars = get_global_variables(_DATA_FILE).copy()

        execute_test_case(case, admin_api_client, db, self.__class__._edit_global_vars)

        # 从响应中获取records并随机选择一个
        records = self.__class__._edit_global_vars.get("data_records")
        if not records:
            # execute_test_case 未缓存 records，需手动查询
            # extract_vars 已提取 records[0].productId，直接使用
            product_id = self.__class__._edit_global_vars.get("product_id")
            if not product_id:
                pytest.skip("未查询到抖音商品，跳过修改")
            self.__class__._edit_product_id = str(product_id)
            return

        record = random.choice(records)
        self.__class__._edit_product_id = str(record.get("productId"))
        self.__class__._edit_global_vars["product_id"] = self.__class__._edit_product_id
        logger.info(f"[DPO_003_S1] 随机选择商品 productId={self.__class__._edit_product_id}")

    @pytest.mark.order(4)
    @allure.title("DPO_003_S2 - 查询商品编辑信息")
    def test_edit_step2_query_edit(self, admin_api_client, db):
        """根据productId查询商品编辑详情"""
        case = _ALL_CASES[5]  # DPO_003_S2

        if not hasattr(self, '_edit_product_id') or not self._edit_product_id:
            pytest.skip("步骤1未获取到productId，跳过编辑查询")

        global_vars = get_global_variables(_DATA_FILE).copy()
        global_vars["product_id"] = self.__class__._edit_product_id

        execute_test_case(case, admin_api_client, db, global_vars)

        # 保存提取的变量供步骤3使用
        self.__class__._edit_global_vars = global_vars

    @pytest.mark.order(5)
    @allure.title("DPO_003_S3 - 修改抖音商品信息")
    def test_edit_step3_update(self, admin_api_client, db):
        """修改商品名称、佣金等信息"""
        case = _ALL_CASES[6]  # DPO_003_S3

        if not hasattr(self, '_edit_global_vars') or not self.__class__._edit_global_vars.get("product_record_id"):
            pytest.skip("步骤2未获取到编辑信息，跳过修改")

        global_vars = self.__class__._edit_global_vars.copy()
        now_str = datetime.now().strftime("%Y%m%d%H%M%S")
        global_vars["product_name"] = f"自动化测试-抖音商品-{now_str}--已经过自动化程序修改商品信息"

        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== TC_004: 商品下架 ====================
    @pytest.mark.order(6)
    @allure.title("DPO_004_S1 - 查询已上架商品(下架用)")
    def test_off_shelf_step1_query(self, admin_api_client, db):
        """查询已上架商品，随机选一个productId"""
        case = _ALL_CASES[7]  # DPO_004_S1
        global_vars = get_global_variables(_DATA_FILE).copy()

        resp = admin_api_client.post(case["endpoint"], json=case["json"])
        data = resp.json()
        records = data.get("data", {}).get("records", [])

        if not records:
            allure.attach("查询结果为空，已上架商品列表无数据", name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip("已上架商品列表为空，跳过下架操作")

        record = random.choice(records)
        self.__class__._off_shelf_product_id = str(record.get("productId"))
        self.__class__._off_shelf_record_id = record.get("id")
        logger.info(f"[DPO_004_S1] 随机选择商品 productId={self.__class__._off_shelf_product_id}, id={self.__class__._off_shelf_record_id}")

    @pytest.mark.order(7)
    @allure.title("DPO_004_S2 - 操作商品下架")
    def test_off_shelf_step2(self, admin_api_client, db):
        """对已上架商品执行下架操作"""
        case = _ALL_CASES[8]  # DPO_004_S2

        if not hasattr(self, '_off_shelf_product_id') or not self._off_shelf_product_id:
            pytest.skip("步骤1未获取到productId，跳过下架")

        global_vars = get_global_variables(_DATA_FILE).copy()
        global_vars["product_id"] = self.__class__._off_shelf_product_id
        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== TC_005: 商品上架 ====================
    @pytest.mark.order(8)
    @allure.title("DPO_005_S1 - 查询不显示商品(上架用)")
    def test_on_shelf_step1_query(self, admin_api_client, db):
        """查询不显示商品，随机选一个productId"""
        case = _ALL_CASES[9]  # DPO_005_S1
        global_vars = get_global_variables(_DATA_FILE).copy()

        resp = admin_api_client.post(case["endpoint"], json=case["json"])
        data = resp.json()
        records = data.get("data", {}).get("records", [])

        if not records:
            allure.attach("查询结果为空，不显示商品列表无数据", name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip("不显示商品列表为空，跳过上架操作")

        record = random.choice(records)
        self.__class__._on_shelf_product_id = str(record.get("productId"))
        logger.info(f"[DPO_005_S1] 随机选择商品 productId={self.__class__._on_shelf_product_id}")

    @pytest.mark.order(9)
    @allure.title("DPO_005_S2 - 操作商品上架")
    def test_on_shelf_step2(self, admin_api_client, db):
        """对不显示商品执行上架操作"""
        case = _ALL_CASES[10]  # DPO_005_S2

        if not hasattr(self, '_on_shelf_product_id') or not self._on_shelf_product_id:
            pytest.skip("步骤1未获取到productId，跳过上架")

        global_vars = get_global_variables(_DATA_FILE).copy()
        global_vars["product_id"] = self.__class__._on_shelf_product_id
        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== TC_006: 复制商品 ====================
    @pytest.mark.order(10)
    @allure.title("DPO_006_S1 - 查询商品列表(复制用)")
    def test_copy_step1_query(self, admin_api_client, db):
        """查询商品列表获取productId和shopId"""
        case = _ALL_CASES[11]  # DPO_006_S1
        global_vars = get_global_variables(_DATA_FILE).copy()

        resp = admin_api_client.post(case["endpoint"], json=case["json"])
        data = resp.json()
        records = data.get("data", {}).get("records", [])

        if not records:
            allure.attach("查询结果为空，商品列表无数据", name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip("商品列表为空，跳过复制操作")

        record = random.choice(records)
        self.__class__._copy_product_id = str(record.get("productId"))
        self.__class__._copy_shop_id = str(record.get("shopId"))
        logger.info(f"[DPO_006_S1] 随机选择商品 productId={self.__class__._copy_product_id}, shopId={self.__class__._copy_shop_id}")

    @pytest.mark.order(11)
    @allure.title("DPO_006_S2 - 复制抖音商品")
    def test_copy_step2(self, admin_api_client, db):
        """复制指定抖音商品到目标门店"""
        case = _ALL_CASES[12]  # DPO_006_S2

        if not hasattr(self, '_copy_product_id') or not self._copy_product_id:
            pytest.skip("步骤1未获取到productId，跳过复制")

        global_vars = get_global_variables(_DATA_FILE).copy()
        global_vars["product_id"] = self.__class__._copy_product_id
        global_vars["source_shop_id"] = self.__class__._copy_shop_id
        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== TC_007: 关锁商品 ====================
    @pytest.mark.order(12)
    @allure.title("DPO_007 - 抖音商品关锁")
    def test_lock_product(self, admin_api_client, db):
        """SQL查询未关锁商品 → 执行关锁操作"""
        case = _ALL_CASES[13]  # DPO_007_S1
        global_vars = get_global_variables(_DATA_FILE).copy()
        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== TC_008: 开锁商品 ====================
    @pytest.mark.order(13)
    @allure.title("DPO_008 - 抖音商品开锁")
    def test_unlock_product(self, admin_api_client, db):
        """SQL查询已关锁商品 → 执行开锁操作"""
        case = _ALL_CASES[14]  # DPO_008_S1
        global_vars = get_global_variables(_DATA_FILE).copy()
        execute_test_case(case, admin_api_client, db, global_vars)
