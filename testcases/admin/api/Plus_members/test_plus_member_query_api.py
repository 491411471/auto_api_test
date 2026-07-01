# testcases/admin/api/Plus_members/test_plus_member_query_api.py
"""
运营端 - Plus会员订单管理测试

测试用例1: 以关联渠道为查询条件
测试用例2: 以用户名为查询条件
测试用例3: 以商户为查询条件
测试用例4: 以购买状态-已支付为查询条件（含循环分页金额汇总校验）
测试用例5: 以购买状态-已支付、已退款为查询条件
测试用例6: 以购买状态-已退款为查询条件（含循环分页金额汇总校验）
测试用例7: 以购买状态-待支付为查询条件
测试用例8: 会员Plus-修改价格
"""
import math
import random
import json
import allure
import pytest

from common.logger import logger
from common.test_helpers import execute_test_case, replace_placeholders, validate_response
from utils.assert_utils import assert_status_code
from utils.data_loader import get_test_data, get_global_variables
from utils.variable_utils import get_value_by_path


_DATA_FILE = "data/admin/api/Plus_members/plus_member_query_api.yaml"


@allure.epic("运营端")
@allure.feature("运营端-订单管理")
@allure.story("Plus会员管理")
class TestPlusMemberQuery:
    """Plus会员订单查询测试类"""

    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables(_DATA_FILE)
        return cls._global_vars.copy()

    # ==================== 测试用例1: 以关联渠道为查询条件 ====================
    @pytest.mark.order(1)
    @allure.title("PM_001 - 以关联渠道为查询条件")
    def test_query_by_channel(self, admin_api_client, db):
        """使用渠道编码查询Plus会员订单，验证返回结果"""
        cases = get_test_data(_DATA_FILE, "plus_member_channel_query_tests")
        case = cases[0]
        global_vars = self._load_global_vars()

        allure.dynamic.description(case.get("description", ""))
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info(f"[PM_001] 渠道查询测试完成: channel={case['json'].get('channel')}")

    # ==================== 测试用例2: 以用户名为查询条件 ====================
    @pytest.mark.order(2)
    @allure.title("PM_002 - 以用户名为查询条件")
    def test_query_by_username(self, admin_api_client, db):
        """使用用户名查询Plus会员订单，验证返回结果"""
        cases = get_test_data(_DATA_FILE, "plus_member_username_query_tests")
        case = cases[0]
        global_vars = self._load_global_vars()

        allure.dynamic.description(case.get("description", ""))
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info(f"[PM_002] 用户名查询测试完成: userName={case['json'].get('userName')}")

    # ==================== 测试用例3: 以商户为查询条件 ====================
    @pytest.mark.order(3)
    @allure.title("PM_003 - 以商户为查询条件")
    def test_query_by_shop(self, admin_api_client, db):
        """使用商户ID查询Plus会员订单，验证返回结果"""
        cases = get_test_data(_DATA_FILE, "plus_member_shop_query_tests")
        case = cases[0]
        global_vars = self._load_global_vars()

        allure.dynamic.description(case.get("description", ""))
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info(f"[PM_003] 商户查询测试完成: shopId={case['json'].get('shopId')}")

    # ==================== 测试用例4: 以购买状态-已支付为查询条件 ====================
    @pytest.mark.order(4)
    @allure.title("PM_004_01 - 查询第一页已支付订单列表")
    def test_query_paid_orders_first_page(self, admin_api_client, db):
        """步骤1：查询第一页已支付状态的订单列表，验证单页数据正确性"""
        cases = get_test_data(_DATA_FILE, "plus_member_paid_status_tests")
        case = cases[0]  # 第一个用例：查询第一页
        global_vars = self._load_global_vars()

        allure.dynamic.description(case.get("description", ""))
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info("[PM_004_01] 第一页已支付订单列表查询完成")

    @pytest.mark.order(5)
    @allure.title("PM_004_02 - 循环查询所有页已支付订单并验证金额汇总")
    def test_verify_paid_amount_summary_with_pagination(self, admin_api_client, db):
        """步骤2：循环查询所有页已支付订单，计算amount总和，与汇总接口的paidAmount进行等值断言"""
        cases = get_test_data(_DATA_FILE, "plus_member_paid_status_tests")
        case = cases[1]  # 第二个用例：汇总验证
        global_vars = self._load_global_vars()

        allure.dynamic.description(case.get("description", ""))

        # ===== 第一阶段：循环分页查询所有已支付订单，计算amount总和 =====
        page_num = 1
        page_size = 100
        total_amount_from_pages = 0.0
        total_records_count = 0
        max_pages = 1000  # 安全限制，防止无限循环

        # 获取分页查询的基础参数
        first_page_case = get_test_data(_DATA_FILE, "plus_member_paid_status_tests")[0]
        base_request_body = first_page_case.get("json", {})

        with allure.step("循环分页查询所有已支付订单"):
            while page_num <= max_pages:
                # 构造当前页的请求参数
                current_page_params = base_request_body.copy()
                current_page_params["pageNum"] = page_num
                current_page_params["pageSize"] = page_size

                allure.attach(
                    json.dumps(current_page_params, ensure_ascii=False, indent=2),
                    name=f"第{page_num}页请求参数",
                    attachment_type=allure.attachment_type.JSON,
                )

                # 发送分页查询请求
                resp = admin_api_client.post(first_page_case["endpoint"],json=current_page_params)
                # 基础断言
                assert_status_code(resp.status_code, first_page_case["expected_status"])
                response_data = resp.json()

                # 提取当前页的数据
                data_obj = response_data.get("data", {})
                records = data_obj.get("records", [])
                current_page_size = len(records)
                total_records = data_obj.get("total", 0)

                # 记录总记录数（只记录一次）
                if page_num == 1:
                    total_records_count = total_records
                    allure.attach(
                        f"总记录数: {total_records_count}",
                        name="分页查询概况",
                        attachment_type=allure.attachment_type.TEXT,
                    )

                # 计算当前页的amount总和
                page_amount_sum = 0.0
                for record in records:
                    amount = record.get("amount")
                    if amount is not None:
                        # 统一转换为float类型
                        page_amount_sum += float(amount)

                total_amount_from_pages += page_amount_sum

                allure.attach(
                    f"第{page_num}页记录数: {current_page_size}\n"
                    f"第{page_num}页金额总和: {page_amount_sum:.2f}\n"
                    f"累计金额总和: {total_amount_from_pages:.2f}",
                    name=f"第{page_num}页统计",
                    attachment_type=allure.attachment_type.TEXT,
                )

                logger.info(
                    f"[PM_004_02] 第{page_num}页: 记录数={current_page_size}, "
                    f"页金额={page_amount_sum:.2f}, 累计金额={total_amount_from_pages:.2f}"
                )

                # 判断是否还有下一页
                if current_page_size < page_size:
                    logger.info(f"[PM_004_02] 已到达最后一页（第{page_num}页）")
                    break

                page_num += 1

                # 安全限制检查
                if page_num > max_pages:
                    logger.warning(f"[PM_004_02] 达到最大页数限制({max_pages})，停止分页查询")
                    break

            # 分页查询完成后的汇总信息
            allure.attach(
                f"分页查询完成\n"
                f"总页数: {page_num}\n"
                f"总记录数: {total_records_count}\n"
                f"分页计算总金额: {total_amount_from_pages:.2f}",
                name="分页查询最终结果",
                attachment_type=allure.attachment_type.TEXT,
            )

            logger.info(
                f"[PM_004_02] 分页查询完成: 总页数={page_num}, "
                f"总记录数={total_records_count}, 总金额={total_amount_from_pages:.2f}"
            )

        # ===== 第二阶段：调用汇总接口获取paidAmount =====
        with allure.step("调用汇总接口获取已支付订单总金额"):
            # 执行汇总接口请求
            response = admin_api_client.post(
                case["endpoint"],
                json=case.get("json", {})
            )

            # 基础断言
            assert_status_code(response.status_code, case["expected_status"])
            validate_response(case, response.json(), global_vars)

            response_data = response.json()
            summary_data = response_data.get("data", {})
            paid_amount = summary_data.get("paidAmount")

            if paid_amount is None:
                skip_msg = "汇总接口未返回paidAmount字段，跳过金额比对"
                logger.warning(f"[跳过] {skip_msg}")
                pytest.skip(skip_msg)

            # 统一转换为float类型
            paid_amount_float = float(paid_amount)

            allure.attach(
                f"汇总接口返回paidAmount: {paid_amount_float:.2f}",
                name="汇总接口结果",
                attachment_type=allure.attachment_type.TEXT,
            )

            logger.info(f"[PM_004_02] 汇总接口返回paidAmount: {paid_amount_float:.2f}")

        # ===== 第三阶段：等值断言 =====
        with allure.step("比对分页计算总金额与汇总接口paidAmount"):
            allure.attach(
                f"分页计算总金额: {total_amount_from_pages:.2f}\n"
                f"汇总接口paidAmount: {paid_amount_float:.2f}\n"
                f"差值: {abs(total_amount_from_pages - paid_amount_float):.4f}",
                name="金额比对详情",
                attachment_type=allure.attachment_type.TEXT,
            )

            # 使用math.isclose进行浮点数等值比较，允许极小误差（1分钱以内）
            is_equal = math.isclose(
                total_amount_from_pages,
                paid_amount_float,
                rel_tol=1e-5,  # 相对误差容忍度
                abs_tol=0.01   # 绝对误差容忍度（1分钱）
            )

            if not is_equal:
                error_msg = (
                    f"金额不一致！\n"
                    f"分页计算总金额: {total_amount_from_pages:.2f}\n"
                    f"汇总接口paidAmount: {paid_amount_float:.2f}\n"
                    f"差值: {abs(total_amount_from_pages - paid_amount_float):.4f}"
                )
                logger.error(f"[PM_004_02] {error_msg}")
                allure.attach(
                    error_msg,
                    name="金额比对失败",
                    attachment_type=allure.attachment_type.TEXT,
                )
                pytest.fail(error_msg)

            logger.info(
                f"[PM_004_02] 金额验证通过: "
                f"分页计算={total_amount_from_pages:.2f}, "
                f"汇总接口={paid_amount_float:.2f}"
            )

    # ==================== 测试用例5: 以购买状态-已支付、已退款为查询条件 ====================
    @pytest.mark.order(6)
    @allure.title("PM_005 - 以购买状态-已支付、已退款为查询条件")
    def test_query_paid_and_refunded(self, admin_api_client, db):
        """查询已支付和已退款状态的订单，验证status字段值在指定范围内"""
        cases = get_test_data(_DATA_FILE, "plus_member_paid_refunded_query_tests")
        case = cases[0]
        global_vars = self._load_global_vars()

        allure.dynamic.description(case.get("description", ""))
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info(f"[PM_005] 已支付/已退款复合状态查询完成: payStatus={case['json'].get('payStatus')}")

    # ==================== 测试用例6: 以购买状态-已退款为查询条件 ====================
    @pytest.mark.order(7)
    @allure.title("PM_006_01 - 查询第一页已退款订单列表")
    def test_query_refunded_orders_first_page(self, admin_api_client, db):
        """步骤1：查询第一页已退款状态的订单列表，验证单页数据正确性"""
        cases = get_test_data(_DATA_FILE, "plus_member_refunded_status_tests")
        case = cases[0]  # 第一个用例：查询第一页
        global_vars = self._load_global_vars()

        allure.dynamic.description(case.get("description", ""))
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info("[PM_006_01] 第一页已退款订单列表查询完成")

    @pytest.mark.order(8)
    @allure.title("PM_006_02 - 循环查询所有页已退款订单并验证金额汇总")
    def test_verify_refunded_amount_summary_with_pagination(self, admin_api_client, db):
        """步骤2：循环查询所有页已退款订单，计算amount总和，与汇总接口的refundAmount进行等值断言"""
        cases = get_test_data(_DATA_FILE, "plus_member_refunded_status_tests")
        case = cases[1]  # 第二个用例：汇总验证
        global_vars = self._load_global_vars()

        allure.dynamic.description(case.get("description", ""))

        # ===== 第一阶段：循环分页查询所有已退款订单，计算amount总和 =====
        page_num = 1
        page_size = 100
        total_amount_from_pages = 0.0
        total_records_count = 0
        max_pages = 1000

        # 获取分页查询的基础参数
        first_page_case = get_test_data(_DATA_FILE, "plus_member_refunded_status_tests")[0]
        base_request_body = first_page_case.get("json", {})

        with allure.step("循环分页查询所有已退款订单"):
            while page_num <= max_pages:
                current_page_params = base_request_body.copy()
                current_page_params["pageNum"] = page_num
                current_page_params["pageSize"] = page_size

                resp = admin_api_client.post(
                    first_page_case["endpoint"],
                    json=current_page_params
                )

                assert_status_code(resp.status_code, first_page_case["expected_status"])

                response_data = resp.json()
                data_obj = response_data.get("data", {})
                records = data_obj.get("records", [])

                if page_num == 1:
                    total_records_count = data_obj.get("total", 0)

                page_amount_sum = 0.0
                for record in records:
                    amount = record.get("amount")
                    if amount is not None:
                        page_amount_sum += float(amount)

                total_amount_from_pages += page_amount_sum

                logger.info(
                    f"[PM_006_02] 第{page_num}页: 记录数={len(records)}, "
                    f"页金额={page_amount_sum:.2f}, 累计金额={total_amount_from_pages:.2f}"
                )

                if len(records) < page_size:
                    break

                page_num += 1

                if page_num > max_pages:
                    logger.warning(f"[PM_006_02] 达到最大页数限制({max_pages})")
                    break

            allure.attach(
                f"分页查询完成\n"
                f"总页数: {page_num}\n"
                f"总记录数: {total_records_count}\n"
                f"分页计算总金额: {total_amount_from_pages:.2f}",
                name="分页查询最终结果",
                attachment_type=allure.attachment_type.TEXT,
            )

        # ===== 第二阶段：调用汇总接口获取refundAmount =====
        with allure.step("调用汇总接口获取已退款订单总金额"):
            response = admin_api_client.post(
                case["endpoint"],
                json=case.get("json", {})
            )

            assert_status_code(response.status_code, case["expected_status"])
            validate_response(case, response.json(), global_vars)

            response_data = response.json()
            summary_data = response_data.get("data", {})
            refund_amount = summary_data.get("refundAmount")

            if refund_amount is None:
                pytest.skip("汇总接口未返回refundAmount字段")

            refund_amount_float = float(refund_amount)

            allure.attach(
                f"汇总接口返回refundAmount: {refund_amount_float:.2f}",
                name="汇总接口结果",
                attachment_type=allure.attachment_type.TEXT,
            )

        # ===== 第三阶段：等值断言 =====
        with allure.step("比对分页计算总金额与汇总接口refundAmount"):
            allure.attach(
                f"分页计算总金额: {total_amount_from_pages:.2f}\n"
                f"汇总接口refundAmount: {refund_amount_float:.2f}",
                name="金额比对详情",
                attachment_type=allure.attachment_type.TEXT,
            )

            is_equal = math.isclose(
                total_amount_from_pages,
                refund_amount_float,
                rel_tol=1e-5,
                abs_tol=0.01
            )

            if not is_equal:
                pytest.fail(
                    f"金额不一致！分页计算={total_amount_from_pages:.2f}, "
                    f"汇总接口={refund_amount_float:.2f}"
                )

            logger.info(
                f"[PM_006_02] 金额验证通过: "
                f"分页计算={total_amount_from_pages:.2f}, "
                f"汇总接口={refund_amount_float:.2f}"
            )

    # ==================== 测试用例7: 以购买状态-待支付为查询条件 ====================
    @pytest.mark.order(9)
    @allure.title("PM_007 - 以购买状态-待支付为查询条件")
    def test_query_unpaid_orders(self, admin_api_client, db):
        """查询待支付状态的订单，验证返回结果"""
        cases = get_test_data(_DATA_FILE, "plus_member_unpaid_status_tests")
        case = cases[0]
        global_vars = self._load_global_vars()

        allure.dynamic.description(case.get("description", ""))
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info(f"[PM_007] 待支付订单查询完成: payStatus={case['json'].get('payStatus')}")

    # ==================== 测试用例8: 会员Plus-修改价格 ====================
    @pytest.mark.order(10)
    @allure.title("PM_008 - 会员Plus-修改价格")
    def test_update_member_price(self, admin_api_client, db):
        """从数据库获取最新记录ID，并更新为随机金额"""
        cases = get_test_data(_DATA_FILE, "plus_member_update_price_tests")
        case = cases[0]
        global_vars = self._load_global_vars()
        print("global_vars:", global_vars)
        # 生成1-100之间的随机两位小数金额
        random_amount = round(random.uniform(1.0, 100.0), 2)
        global_vars["random_float_1_100"] = random_amount

        allure.dynamic.description(f"{case.get('description', '')}\n更新金额为: {random_amount}")

        logger.info(f"[PM_008] 准备更新Plus会员价格，随机金额: {random_amount}")

        # 执行SQL获取ID
        sql_query = case.get("sql", [{}])[0].get("query", "")
        if sql_query:
            with allure.step("执行SQL获取最新记录ID"):
                allure.attach(sql_query, name="SQL语句", attachment_type=allure.attachment_type.TEXT)
                result = db.fetch_one(sql_query)

                if not result:
                    skip_msg = "未查询到Plus会员价格记录，跳过更新测试"
                    logger.warning(f"[跳过] {skip_msg}")
                    pytest.skip(skip_msg)

                record_id = result.get("id") if isinstance(result, dict) else result[0] if result else None
                if record_id is None:
                    pytest.skip("SQL查询结果中未找到ID字段")

                global_vars["id"] = record_id
                logger.info(f"[PM_008] 从数据库获取到记录ID: {record_id}")
                allure.attach(
                    f"记录ID: {record_id}",
                    name="SQL查询结果",
                    attachment_type=allure.attachment_type.TEXT,
                )

        # 执行更新操作
        execute_test_case(case, admin_api_client, db, global_vars)

        logger.info(f"[PM_008] Plus会员价格更新测试完成，更新ID: {global_vars.get('id')}, 新金额: {random_amount}")