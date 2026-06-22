# testcases/admin/api/product_management/test_examine_product_operation_api.py
"""
运营端 - 商品管理：商品审核-商品操作接口测试

接口覆盖：
  - 查看商品详情 + 提交商品审核
  - 编辑商品（展示详情 → 保存草稿箱 → 从草稿箱获取）
  - 隐藏/显示商品
  - 商品锁开/锁关
  - 开启/关闭多台设备

数据策略：Class 组织，步骤0通过SQL获取两组商品数据供后续用例使用
变量传递：SQL 提取的 id/product_id 通过类属性跨方法共享
"""
import copy
import json
from datetime import datetime

import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables


_DATA_FILE = "data/admin/api/product_management/examine_product_operation_api.yaml"

# 预加载所有用例数据
_ALL_CASES = get_test_data(_DATA_FILE, "examine_product_operation_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 examine_product_operation_api.yaml")


def _get_case_by_id(case_id: str) -> dict:
    """根据 case_id 从用例列表中获取测试用例数据"""
    for case in _ALL_CASES:
        if case["case_id"] == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")


@allure.epic("运营端")
@allure.feature("运营端-商品管理")
@allure.story("商品审核-商品操作")
class TestExamineProductOperation:
    """商品审核-商品操作 - 多场景操作测试"""

    _global_vars = None
    # SQL 提取的两组商品数据（跨测试方法共享）
    _first_id = None
    _first_product_id = None
    _second_id = None
    _second_product_id = None
    # 从商品详情响应中提取的动态变量（供提交审核使用）
    _image_item_id = None
    _product_spec_id = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    @staticmethod
    def _add_dynamic_vars(global_vars: dict) -> dict:
        """注入动态变量（如提交理由等运行时生成的值）"""
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        global_vars["submit_reason"] = f"自动化测试提交-{ts}"
        return global_vars

    # ==================== 步骤0：检查可用商品数据是否充足 ====================
    @pytest.mark.order(0)
    @allure.title("EPO_000 | 检查可用商品数据")
    def test_step0_check_data_sufficiency(self, admin_api_client, db):
        """步骤0：轻量级数据检查，确认数据库中有足够的可用商品，不足则跳过后续所有测试。"""
        sql_query = (
            "SELECT COUNT(*) as cnt FROM llxz_product.ct_product "
            "WHERE status = 1"
        )

        with allure.step("检查可用商品数量"):
            allure.attach(sql_query, name="SQL查询", attachment_type=allure.attachment_type.TEXT)
            results = db.fetch_all(sql_query)
            allure.attach(str(results), name="SQL查询结果", attachment_type=allure.attachment_type.TEXT)

        count = results[0]["cnt"] if results else 0
        if count < 2:
            skip_msg = f"可用商品不足2条(实际{count}条)，跳过后续测试"
            logger.warning(f"[跳过] {skip_msg}")
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        logger.info(f"可用商品数据充足，共 {count} 条")

    # ==================== TC1 步骤一：查看商品详情 ====================
    @pytest.mark.order(1)
    @allure.title("EPO_001 | 查看商品详情")
    def test_step1_view_product_detail(self, admin_api_client, db):
        """步骤1：通过框架SQL+var_prefix自动展开商品数据，调用详情接口并提取image_item_id/product_spec_id。"""
        case = _get_case_by_id("EPO_001")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()

        # ---------- 框架执行：SQL + var_prefix自动展开 + API请求 + 断言 + extract_vars ----------
        # YAML 配置 var_prefix: {first: 0, second: 1} 将自动展开为:
        #   global_vars["first_id"], global_vars["first_product_id"]
        #   global_vars["second_id"], global_vars["second_product_id"]
        execute_test_case(case, admin_api_client, db, global_vars)

        # ---------- 从 var_prefix 展开结果中捕获类属性（供后续步骤使用） ----------
        self.__class__._first_id = global_vars.get("first_id")
        self.__class__._first_product_id = global_vars.get("first_product_id")
        self.__class__._second_id = global_vars.get("second_id")
        self.__class__._second_product_id = global_vars.get("second_product_id")

        extracted_info = (
            f"第一组: id={self._first_id}, product_id={self._first_product_id}\n"
            f"第二组: id={self._second_id}, product_id={self._second_product_id}"
        )
        logger.info(f"var_prefix展开的商品数据:\n{extracted_info}")
        allure.attach(extracted_info, name="var_prefix展开的商品数据", attachment_type=allure.attachment_type.TEXT)

        # ---------- 捕获 extract_vars 提取的响应变量 ----------
        extracted_image_id = global_vars.get("image_item_id")
        extracted_spec_id = global_vars.get("product_spec_id")
        if extracted_image_id:
            self.__class__._image_item_id = extracted_image_id
        if extracted_spec_id:
            self.__class__._product_spec_id = extracted_spec_id
        logger.info(f"extract_vars提取: image_item_id={self.__class__._image_item_id}, "
                     f"product_spec_id={self.__class__._product_spec_id}")

    # ==================== TC2 步骤一：编辑商品-展示详情 ====================
    @pytest.mark.order(3)
    @allure.title("EPO_003 | 编辑商品-展示详情")
    def test_step3_edit_product_detail(self, admin_api_client, db):
        """步骤3：使用第二组商品的id获取编辑详情，修改detail字段后保存供草稿箱步骤使用。"""
        if not self.__class__._second_id:
            pytest.skip("前置SQL未获取到商品数据，跳过")

        case = _get_case_by_id("EPO_003")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        global_vars["second_id"] = self.__class__._second_id

        # 手动发送GET请求以提取data对象进行修改
        endpoint = case.get("endpoint", "")
        params = {"id": self.__class__._second_id}

        with allure.step("发送编辑详情查询请求"):
            allure.attach(str(params), name="请求参数", attachment_type=allure.attachment_type.TEXT)
            resp = admin_api_client.get(endpoint, params=params)
            response_data = resp.json()
            allure.attach(str(resp.status_code), name="HTTP 状态码", attachment_type=allure.attachment_type.TEXT)
            allure.attach(
                json.dumps(response_data, ensure_ascii=False, indent=2, default=str),
                name="完整响应体", attachment_type=allure.attachment_type.JSON,
            )

        # 基础断言
        with allure.step("执行基础断言"):
            from utils.assert_utils import assert_status_code
            assert_status_code(resp.status_code, case["expected_status"])
            assert response_data.get("rpcResult") == "SUCCESS", "接口返回失败"
            assert response_data.get("businessSuccess") is True, "业务处理失败"

        # 提取data对象并修改detail字段
        data = response_data.get("data")
        if not data:
            pytest.skip("编辑详情接口返回data为空，跳过后续草稿箱步骤")

        data["detail"] = "【接口自动化测试修改商品详情】"
        self.__class__._modified_product_data = data

        allure.attach(
            "【接口自动化测试修改商品详情】",
            name="修改的detail字段", attachment_type=allure.attachment_type.TEXT,
        )
        logger.info(f"提取并修改商品详情数据成功, id={data.get('id')}, productId={data.get('productId')}")

    # ==================== TC2 步骤二：修改内容并保存草稿箱 ====================
    @pytest.mark.order(4)
    @allure.title("EPO_004 | 修改内容并保存草稿箱")
    def test_step4_save_draft(self, admin_api_client, db):
        """步骤4：将修改后的商品数据保存到草稿箱。"""
        if not hasattr(self.__class__, '_modified_product_data') or not self.__class__._modified_product_data:
            pytest.skip("前置步骤未获取到商品数据，跳过")

        case = _get_case_by_id("EPO_004")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        # 将修改后的商品数据作为 _draft_body 注入
        global_vars["_draft_body"] = self.__class__._modified_product_data

        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== TC2 步骤三：从草稿箱中获取目标内容详情 ====================
    @pytest.mark.order(5)
    @allure.title("EPO_005 | 从草稿箱获取草稿详情")
    def test_step5_get_draft_detail(self, admin_api_client, db):
        """步骤5：通过SQL查询草稿箱id，调用草稿详情接口验证草稿保存成功。"""
        if not self.__class__._second_product_id:
            pytest.skip("前置SQL未获取到商品数据，跳过")

        case = _get_case_by_id("EPO_005")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        global_vars["second_product_id"] = self.__class__._second_product_id

        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== TC3：隐藏商品 ====================
    @pytest.mark.order(6)
    @allure.title("EPO_006 | 隐藏商品")
    def test_step6_hide_product(self, admin_api_client, db):
        """步骤6：隐藏指定商品(type=3)，通过SQL验证type已变更为3。"""
        if not self.__class__._first_product_id:
            pytest.skip("前置SQL未获取到商品数据，跳过")

        case = _get_case_by_id("EPO_006")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        global_vars["first_product_id"] = self.__class__._first_product_id
        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== TC4：显示商品 ====================
    @pytest.mark.order(7)
    @allure.title("EPO_007 | 显示商品")
    def test_step7_show_product(self, admin_api_client, db):
        """步骤7：显示指定商品(type=1)，通过SQL验证type已变更为1。"""
        if not self.__class__._first_product_id:
            pytest.skip("前置SQL未获取到商品数据，跳过")

        case = _get_case_by_id("EPO_007")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        global_vars["first_product_id"] = self.__class__._first_product_id
        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== TC6：商品锁开 ====================
    @pytest.mark.order(8)
    @allure.title("EPO_008 | 商品锁开")
    def test_step8_lock_open(self, admin_api_client, db):
        """步骤8：使用第一组商品的id设置lockState=0(未上锁)，通过SQL验证。"""
        if not self.__class__._first_id:
            pytest.skip("前置SQL未获取到商品数据，跳过")

        case = _get_case_by_id("EPO_008")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        global_vars["first_id"] = self.__class__._first_id

        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== TC7：商品锁关 ====================
    @pytest.mark.order(9)
    @allure.title("EPO_009 | 商品锁关")
    def test_step9_lock_close(self, admin_api_client, db):
        """步骤9：使用第一组商品的id设置lockState=1(已上锁)，通过SQL验证。"""
        if not self.__class__._first_id:
            pytest.skip("前置SQL未获取到商品数据，跳过")

        case = _get_case_by_id("EPO_009")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        global_vars["first_id"] = self.__class__._first_id

        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== TC8：开启多台设备 ====================
    @pytest.mark.order(10)
    @allure.title("EPO_010 | 开启多台设备")
    def test_step10_open_quantity_switch(self, admin_api_client, db):
        """步骤10：开启指定商品的多台设备开关(isOpen=true)。"""
        if not self.__class__._second_product_id:
            pytest.skip("前置SQL未获取到商品数据，跳过")

        case = _get_case_by_id("EPO_010")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        global_vars["second_product_id"] = self.__class__._second_product_id

        execute_test_case(case, admin_api_client, db, global_vars)

    # ==================== TC9：关闭多台设备 ====================
    @pytest.mark.order(11)
    @allure.title("EPO_011 | 关闭多台设备")
    def test_step11_close_quantity_switch(self, admin_api_client, db):
        """步骤11：关闭指定商品的多台设备开关(isOpen=false)。"""
        if not self.__class__._second_product_id:
            pytest.skip("前置SQL未获取到商品数据，跳过")

        case = _get_case_by_id("EPO_011")
        allure.dynamic.description(case.get("description", ""))

        global_vars = self._load_global_vars()
        global_vars["second_product_id"] = self.__class__._second_product_id

        execute_test_case(case, admin_api_client, db, global_vars)
