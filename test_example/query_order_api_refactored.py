# testcases/api/order/test_query_order_api_refactored.py
"""
订单查询API测试 - 重构版本
将参数化测试拆分为独立的测试方法
"""
import allure
import pytest
from datetime import datetime, timedelta
from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables


@allure.feature("商家端-订单模块")
@allure.story("订单查询")
class TestOrderQueryRefactored:
    _global_vars = None

    @classmethod
    def _load_global_vars(cls):
        """加载全局变量并缓存"""
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("query_order_api.yaml")
        return cls._global_vars.copy()

    @staticmethod
    def _add_dynamic_date_vars(global_vars: dict) -> dict:
        """动态计算起租日期范围并更新到全局变量中"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        end_date = today.strftime("%Y-%m-%d %H:%M:%S")
        start_date_iso = (today - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00.000Z")
        # 第二个元素为当天16:00:00（与原示例保持一致）
        end_date_iso = datetime.now().replace(hour=16, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        global_vars.update({
            "start_date": start_date,
            "end_date": end_date,
            "start_date_iso": start_date_iso,
            "end_date_iso": end_date_iso,
        })
        return global_vars

    def _prepare_and_run(self, api_client, db, case):
        """准备变量并执行测试用例的通用方法"""
        # 1. 加载全局变量
        global_vars = self._load_global_vars()

        # 2. 合并用例级别变量（如果有）
        if 'variables' in case and isinstance(case['variables'], dict):
            global_vars.update(case['variables'])

        # 3. 动态添加日期变量（关键步骤）
        global_vars = self._add_dynamic_date_vars(global_vars)

        # 4. 更新 allure 标题
        allure.dynamic.title(f"{case['case_id']} - {case.get('title', '')}")

        # 5. 执行测试（内部会调用 replace_variables 替换占位符）
        execute_test_case(case, api_client, db, global_vars)

    @pytest.mark.smoke
    def test_oq_001_query_by_order_id(self, api_client, db):
        """OQ_001: 通过订单号精确查询 - 使用真实存在的订单号进行查询，验证返回唯一记录"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[0]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_002_query_by_nonexistent_order_id(self, api_client, db):
        """OQ_002: 通过不存在的订单号查询 - 使用数据库中不存在的订单号，应返回空列表"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[1]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_003_query_by_order_status(self, api_client, db):
        """OQ_003: 按订单状态查询（订单完成） - 筛选状态为'订单完成'的订单"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[2]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_004_query_by_responsible_person(self, api_client, db):
        """OQ_004: 按责任人查询 - 通过责任人的姓名模糊匹配订单"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[3]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_005_query_by_receiver_phone(self, api_client, db):
        """OQ_005: 按收货人手机号查询 - 严格匹配收货人手机号（11位）"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[4]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_006_query_by_product_name(self, api_client, db):
        """OQ_006: 按商品名称模糊查询 - 根据商品名称关键字查询订单"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[5]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_007_query_by_orderer_name(self, api_client, db):
        """OQ_007: 按下单人姓名查询 - 按下单人的真实姓名查询"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[6]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_008_query_by_orderer_phone(self, api_client, db):
        """OQ_008: 按下单人手机号查询 - 通过下单人手机号精确查询"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[7]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_010_query_by_create_time_range(self, api_client, db):
        """OQ_010: 按创建时间范围查询 - 使用创建时间的起始日期过滤"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[8]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_011_combined_query(self, api_client, db):
        """OQ_011: 组合查询：状态 + 下单人姓名 + 订单编号 - 多条件组合查询，验证结果交集"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[9]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_012_pagination_query(self, api_client, db):
        """OQ_012: 分页查询：第二页数据 - 验证分页参数正常工作"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[10]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_013_order_by_create_time_desc(self, api_client, db):
        """OQ_013: 按创建时间降序排序 - 默认排序应为 create_time DESC，验证第一条记录时间晚于最后一条"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[11]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_014_empty_query_condition(self, api_client, db):
        """OQ_014: 空查询条件（不传任何筛选） - 查询全部订单，应返回分页数据"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[12]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_015_query_high_score_exclusive(self, api_client, db):
        """OQ_015: 订单查询--高分专享 - 订单查询--高分专享单条件查询"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[13]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_016_query_zhima_selection(self, api_client, db):
        """OQ_016: 订单查询--芝麻严选 - 订单查询--芝麻严选单条件查询"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[14]
        self._prepare_and_run(api_client, db, case)

    @pytest.mark.smoke
    def test_oq_017_query_rent_start_date_with_renewal(self, api_client, db):
        """OQ_017: 订单查询--起租日期+续租订单 - 验证订单查询接口中，起租日期在最近一个月内的续租订单"""
        case = get_test_data("query_order_api.yaml", "order_query_tests")[15]
        self._prepare_and_run(api_client, db, case)
