# testcases/Ali_app/api/test_ali_app_miniprogram.py
"""
支付宝-小程序 接口自动化测试

完整流程包含5个步骤：
  步骤1: 商家入驻申请（动态生成姓名和手机号）
  步骤2: 小程序发起投诉（动态生成姓名和手机号）
  步骤3: 撤销投诉（SQL查询投诉记录ID，若不存在则跳过）
  步骤4: 查看领券中心优惠券信息（需添加channelid=008请求头）
  步骤5: 小程序端领取优惠券（从步骤4随机选取模板ID，若不存在则跳过）
"""
import copy
import random

import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case, replace_placeholders
from utils.data_generator import generate_test_data
from utils.data_loader import get_test_data, get_global_variables

_DATA_FILE = "data/Ali_app/api/ali_app_miniprogram.yaml"


@allure.epic("支付宝-小程序")
@allure.feature("支付宝-小程序接口测试")
@allure.story("支付宝小程序全流程")
class TestAliAppMiniprogram:
    """
    支付宝小程序全流程测试：
    商家入驻 → 发起投诉 → 撤销投诉 → 查看领券中心 → 领取优惠券
    """

    # ==================== 跨步骤共享变量 ====================
    _global_vars = None
    _coupon_template_ids = None

    @classmethod
    def _load_global_vars(cls):
        """加载 YAML 全局变量（懒加载 + 缓存）"""
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    # ==================== 步骤1：商家入驻申请 ====================
    @pytest.mark.order(1)
    @allure.title("ALI_001 - 商家入驻申请")
    def test_step1_merchant_add(self, merchant_api_client, db):
        """动态生成姓名和手机号，调用商家入驻接口"""
        case = get_test_data(_DATA_FILE, "step1_merchant_add")
        global_vars = self._load_global_vars()

        # 动态生成测试数据
        name = generate_test_data("cn_name")
        cellphone = generate_test_data("cn_phone")

        # 注入动态变量
        global_vars["name"] = name
        global_vars["cellphone"] = cellphone

        allure.dynamic.title(f"{case['case_id']} | {case['title']}")
        allure.attach(
            f"name = {name}\ncellphone = {cellphone}",
            name="动态生成的入驻信息",
            attachment_type=allure.attachment_type.TEXT,
        )

        execute_test_case(case, merchant_api_client, db, global_vars)
        logger.info(f"[ALI_001] 商家入驻申请成功: name={name}, cellphone={cellphone}")

    # ==================== 步骤2：小程序发起投诉 ====================
    @pytest.mark.order(2)
    @allure.title("ALI_002 - 小程序发起投诉")
    def test_step2_add_complaint(self, merchant_api_client, db):
        """动态生成姓名和手机号，调用投诉接口发起投诉"""
        case = get_test_data(_DATA_FILE, "step2_add_complaint")
        global_vars = self._load_global_vars()

        # 动态生成测试数据
        complaint_name = generate_test_data("cn_name")
        complaint_phone = generate_test_data("cn_phone")

        # 注入动态变量
        global_vars["complaint_name"] = complaint_name
        global_vars["complaint_phone"] = complaint_phone

        allure.dynamic.title(f"{case['case_id']} | {case['title']}")
        allure.attach(
            f"complaint_name = {complaint_name}\ncomplaint_phone = {complaint_phone}\norder_id = {global_vars.get('order_id')}",
            name="动态生成的投诉信息",
            attachment_type=allure.attachment_type.TEXT,
        )

        execute_test_case(case, merchant_api_client, db, global_vars)
        logger.info(f"[ALI_002] 投诉发起成功: name={complaint_name}, order_id={global_vars.get('order_id')}")

    # ==================== 步骤3：撤销投诉 ====================
    @pytest.mark.order(3)
    @allure.title("ALI_003 - 撤销投诉")
    def test_step3_revoke_complaint(self, merchant_api_client, db):
        """
        通过 SQL 查询投诉记录ID，调用撤销投诉接口。
        若未查询到投诉记录，则跳过本用例并将跳过原因写入Allure报告。
        """
        case = get_test_data(_DATA_FILE, "step3_revoke_complaint")
        global_vars = self._load_global_vars()

        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        # 手动执行 SQL 查询投诉记录ID（先替换变量）
        sql_config = case.get("sql", {})
        query = sql_config.get("query", "")
        query_replaced = replace_placeholders(query, global_vars)
        print("执行的 SQL:", query_replaced)
        with allure.step("查询投诉记录ID"):
            allure.attach(query_replaced, name="执行的 SQL", attachment_type=allure.attachment_type.TEXT)
            logger.info(f"执行 SQL: {query_replaced}")
            result = db.fetch_one(query_replaced)

        if result is None or result.get("id") is None:
            skip_msg = f"未查询到投诉记录ID（order_id={global_vars.get('order_id')}），跳过撤销投诉测试"
            logger.warning(skip_msg)
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        complaint_id = result["id"]
        global_vars["complaint_id"] = complaint_id
        allure.attach(f"complaint_id = {complaint_id}", name="查询到的投诉记录ID", attachment_type=allure.attachment_type.TEXT)
        logger.info(f"查询到投诉记录ID: {complaint_id}")

        # 深拷贝 case 并移除 sql 配置，避免 execute_test_case 再次执行 SQL
        case_copy = copy.deepcopy(case)
        case_copy.pop("sql", None)

        execute_test_case(case_copy, merchant_api_client, db, global_vars)
        logger.info(f"[ALI_003] 撤销投诉成功: complaint_id={complaint_id}")

    # ==================== 步骤4：查看领券中心优惠券信息 ====================
    @pytest.mark.order(4)
    @allure.title("ALI_004 - 查看领券中心优惠券信息")
    def test_step4_coupon_center(self, merchant_api_client, db):
        """查询领券中心优惠券信息，需在请求头中添加 channelid=008"""
        case = get_test_data(_DATA_FILE, "step4_coupon_center")
        global_vars = self._load_global_vars()

        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        # 添加 channelid=008 请求头
        merchant_api_client.session.headers["channelid"] = "008"
        logger.info("已添加请求头: channelid=008")
        allure.attach("channelid=008", name="自定义请求头", attachment_type=allure.attachment_type.TEXT)

        try:
            execute_test_case(case, merchant_api_client, db, global_vars)
        finally:
            # 确保请求头被清理，避免影响后续测试
            if "channelid" in merchant_api_client.session.headers:
                del merchant_api_client.session.headers["channelid"]
                logger.info("已移除请求头: channelid=008")

        # 提取优惠券模板ID列表供步骤5使用
        coupon_template_ids = global_vars.get("coupon_template_ids")
        self.__class__._coupon_template_ids = coupon_template_ids

        if coupon_template_ids:
            allure.attach(
                f"共获取到 {len(coupon_template_ids)} 个优惠券模板ID: {coupon_template_ids}",
                name="优惠券模板ID列表",
                attachment_type=allure.attachment_type.TEXT,
            )
            logger.info(f"[ALI_004] 获取优惠券模板ID成功: {coupon_template_ids}")
        else:
            logger.warning("[ALI_004] 未获取到优惠券模板ID")

    # ==================== 步骤5：小程序端领取优惠券 ====================
    @pytest.mark.order(5)
    @allure.title("ALI_005 - 小程序端领取优惠券")
    def test_step5_bind_coupon(self, merchant_api_client, db):
        """
        从步骤4获取的优惠券模板ID中随机选取一个进行领取。
        若未获取到模板ID，则跳过本用例。
        """
        case = get_test_data(_DATA_FILE, "step5_bind_coupon")
        global_vars = self._load_global_vars()

        allure.dynamic.title(f"{case['case_id']} | {case['title']}")

        # 检查是否有可用的优惠券模板ID
        coupon_template_ids = self._coupon_template_ids
        if not coupon_template_ids or not isinstance(coupon_template_ids, list) or len(coupon_template_ids) == 0:
            skip_msg = "未获取到优惠券模板ID（步骤4未返回可用模板），跳过领取优惠券测试"
            logger.warning(skip_msg)
            allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
            pytest.skip(skip_msg)

        # 随机选取一个模板ID
        template_id = random.choice(coupon_template_ids)
        bind_phone = generate_test_data("cn_phone")

        # 注入动态变量
        global_vars["template_id"] = template_id
        global_vars["bind_phone"] = bind_phone

        allure.attach(
            f"template_id = {template_id}\nbind_phone = {bind_phone}",
            name="动态生成的领券信息",
            attachment_type=allure.attachment_type.TEXT,
        )

        execute_test_case(case, merchant_api_client, db, global_vars)
        logger.info(f"[ALI_005] 领取优惠券成功: template_id={template_id}, phone={bind_phone}")
