# testcases/admin/api/kuaishou_product/test_kuaishou_product_operation.py
"""
运营端 - 快手商品操作测试

测试用例1: 修改快手商品信息
测试用例2: 上架快手商品
测试用例3: 下架快手商品
测试用例4: 复制快手商品
"""
import random

import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables

_DATA_FILE = "data/admin/api/kuaishou_product/kuaishou_product_operation_api.yaml"


@allure.epic("运营端")
@allure.feature("运营端-商品管理")
@allure.story("快手商品操作")
class TestKuaishouProductOperation:
    """快手商品操作：修改、上架、下架、复制"""

    _global_vars = None
    # 修改商品信息相关
    _product_db_id = None
    _product_db_product_id = None
    _original_product_name = None
    # 上架/下架相关
    _off_shelf_product_id = None
    _on_shelf_product_id = None
    # 复制商品相关
    _copy_product_id = None
    _copy_product_name = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    # # ==================== 测试用例1: 修改快手商品信息 ====================
    @pytest.mark.order(1)
    @allure.title("KPU_001 - 查询待修改的快手商品")
    def test_step1_query_product_for_update(self, admin_api_client, db):
        """步骤1：通过 SQL 查询已审核通过的快手商品，获取 id 和 product_id"""
        cases = get_test_data(_DATA_FILE, "kuaishou_product_update_tests")
        case = cases[0]
        global_vars = self._load_global_vars()

        # 执行SQL查询
        sql = case.get("sql", [{}])[0].get("query", "")
        allure.attach(sql, name="SQL查询语句", attachment_type=allure.attachment_type.TEXT)

        results = db.fetch_all(sql)
        if not results:
            skip_msg = "数据库中未找到已审核通过的快手商品，跳过修改测试"
            logger.warning(f"[跳过] {skip_msg}")
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        # 获取第一条记录
        selected = results[0]
        self.__class__._product_db_id = selected.get("id")
        self.__class__._product_db_product_id = selected.get("product_id")
        # 从数据库查询商品名称，用于修改时拼接
        self.__class__._original_product_name = selected.get("name", "无划痕苹果手机Pro")

        logger.info(
            f"[KPU_001] 查询到商品: id={self._product_db_id}, "
            f"product_id={self._product_db_product_id}, name={self._original_product_name}"
        )

        allure.attach(
            f"商品ID: {self._product_db_id}\n"
            f"商品编号: {self._product_db_product_id}\n"
            f"商品名称: {self._original_product_name}",
            name="查询到的商品信息",
            attachment_type=allure.attachment_type.TEXT,
        )

        # 执行API请求验证
        global_vars["product_db_id"] = str(self._product_db_id)
        global_vars["product_db_product_id"] = str(self._product_db_product_id)
        global_vars["original_product_name"] = self._original_product_name

        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)

    @pytest.mark.order(2)
    @allure.title("KPU_002 - 修改快手商品信息")
    def test_step2_update_product(self, admin_api_client, db):
        """步骤2：调用 updateExamineProduct 接口修改快手商品信息"""
        cases = get_test_data(_DATA_FILE, "kuaishou_product_update_tests")
        case = cases[1]
        global_vars = self._load_global_vars()

        if not self._product_db_id:
            pytest.skip("步骤1未获取到商品ID，跳过修改测试")

        global_vars["product_db_id"] = str(self._product_db_id)
        global_vars["product_db_product_id"] = str(self._product_db_product_id)
        global_vars["original_product_name"] = self._original_product_name

        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info(f"[KPU_002] 修改商品成功: id={self._product_db_id}")

    # ==================== 测试用例2: 上架快手商品 ====================
    @pytest.mark.order(3)
    @allure.title("KPOS_001 - 查询已下架的快手商品")
    def test_step3_query_off_shelf_products(self, admin_api_client, db):
        """步骤1：查询所有已下架(type=3)的快手商品，从中随机选择一个"""
        cases = get_test_data(_DATA_FILE, "kuaishou_product_on_shelf_tests")
        case = cases[0]
        global_vars = self._load_global_vars()
        print("global_vars:", global_vars)
        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)

        # 从响应中提取 product_id
        self.__class__._off_shelf_product_id = global_vars.get("off_shelf_product_id")

        if not self._off_shelf_product_id:
            skip_msg = "未查询到已下架的快手商品，跳过上架测试"
            logger.warning(f"[跳过] {skip_msg}")
            pytest.skip(skip_msg)

        logger.info(f"[KPOS_001] 选择下架商品: product_id={self._off_shelf_product_id}")

    @pytest.mark.order(4)
    @allure.title("KPOS_002 - 上架快手商品")
    def test_step4_on_shelf_product(self, admin_api_client, db):
        """步骤2：调用 setProuctShowState 接口上架快手商品（type=1）"""
        cases = get_test_data(_DATA_FILE, "kuaishou_product_on_shelf_tests")
        case = cases[1]
        global_vars = self._load_global_vars()

        if not self._off_shelf_product_id:
            pytest.skip("步骤1未获取到下架商品ID，跳过上架测试")

        global_vars["off_shelf_product_id"] = self._off_shelf_product_id

        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info(f"[KPOS_002] 上架商品成功: product_id={self._off_shelf_product_id}")

    # ==================== 测试用例3: 下架快手商品 ====================
    @pytest.mark.order(5)
    @allure.title("KPOFS_001 - 查询已上架的快手商品")
    def test_step5_query_on_shelf_products(self, admin_api_client, db):
        """步骤1：查询所有已上架(type=1)的快手商品，从中随机选择一个"""
        cases = get_test_data(_DATA_FILE, "kuaishou_product_off_shelf_tests")
        case = cases[0]
        global_vars = self._load_global_vars()

        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)

        # 从响应中提取 product_id
        self.__class__._on_shelf_product_id = global_vars.get("on_shelf_product_id")

        if not self._on_shelf_product_id:
            skip_msg = "未查询到已上架的快手商品，跳过下架测试"
            logger.warning(f"[跳过] {skip_msg}")
            pytest.skip(skip_msg)

        logger.info(f"[KPOFS_001] 选择上架商品: product_id={self._on_shelf_product_id}")

    @pytest.mark.order(6)
    @allure.title("KPOFS_002 - 下架快手商品")
    def test_step6_off_shelf_product(self, admin_api_client, db):
        """步骤2：调用 setProuctShowState 接口下架快手商品（type=3）"""
        cases = get_test_data(_DATA_FILE, "kuaishou_product_off_shelf_tests")
        case = cases[1]
        global_vars = self._load_global_vars()

        if not self._on_shelf_product_id:
            pytest.skip("步骤1未获取到上架商品ID，跳过下架测试")

        global_vars["on_shelf_product_id"] = self._on_shelf_product_id

        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info(f"[KPOFS_002] 下架商品成功: product_id={self._on_shelf_product_id}")

    # ==================== 测试用例4: 复制快手商品 ====================
    @pytest.mark.order(7)
    @allure.title("KPC_001 - 查询待复制的快手商品")
    def test_step7_query_product_for_copy(self, admin_api_client, db):
        """步骤1：查询快手商品列表，获取 product_id 和 name 用于复制"""
        cases = get_test_data(_DATA_FILE, "kuaishou_product_copy_tests")
        case = cases[0]
        global_vars = self._load_global_vars()

        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)

        # 从响应中提取 product_id 和 name
        self.__class__._copy_product_id = global_vars.get("copy_product_id")
        self.__class__._copy_product_name = global_vars.get("copy_product_name")

        if not self._copy_product_id:
            skip_msg = "未查询到可复制的快手商品，跳过复制测试"
            logger.warning(f"[跳过] {skip_msg}")
            pytest.skip(skip_msg)

        logger.info(
            f"[KPC_001] 选择复制商品: product_id={self._copy_product_id}, "
            f"name={self._copy_product_name}"
        )

    @pytest.mark.order(8)
    @allure.title("KPC_002 - 复制快手商品")
    def test_step8_copy_product(self, admin_api_client, db):
        """步骤2：调用 busCopyTikTokProductForShop 接口复制快手商品到指定店铺"""
        cases = get_test_data(_DATA_FILE, "kuaishou_product_copy_tests")
        case = cases[1]
        global_vars = self._load_global_vars()

        if not self._copy_product_id:
            pytest.skip("步骤1未获取到商品ID，跳过复制测试")

        global_vars["copy_product_id"] = self._copy_product_id
        global_vars["copy_product_name"] = self._copy_product_name

        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info(f"[KPC_002] 复制商品成功: product_id={self._copy_product_id}")

    @pytest.mark.order(9)
    @allure.title("KPC_003 - 审核通过复制后的快手商品")
    def test_step9_audit_copied_product(self, admin_api_client, db):
        """步骤3：复制商品后，调用 examineProductConfirm 接口审核通过，id 通过 SQL 从 ct_product 动态获取"""
        cases = get_test_data(_DATA_FILE, "kuaishou_product_copy_tests")
        case = cases[2]
        global_vars = self._load_global_vars()

        if not self._copy_product_name:
            pytest.skip("步骤1未获取到商品名称，跳过审核测试")

        global_vars["copy_product_name"] = self._copy_product_name

        allure.dynamic.title(f"{case['case_id']} | {case.get('title', '')}")
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info(f"[KPC_003] 审核复制商品成功: name={self._copy_product_name}")
