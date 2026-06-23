# testcases/admin/api/douyin_product_query/test_douyin_product_query.py
"""
运营端 - 商品管理：抖音商品查询接口测试

接口：POST /hzsx/examineProduct/selectExaminePoroductList
覆盖场景：
  DQC_001 ~ DQC_002: 抖音审核状态筛选（待审核/审核通过）
  DQC_003 ~ DQC_004: 上架状态筛选（已上架/已下架）
  DQC_005 ~ DQC_006: 店铺名称/ID 精确查询
  DQC_007 ~ DQC_008: 商品名称/编码查询（SQL 动态获取）
  DQC_009:           产品新旧筛选（全新）
  DQC_010 ~ DQC_011: 平台审核状态筛选（审核通过/审核拒绝）
  DQC_012 ~ DQC_013: 购买套餐筛选（有/无）

数据策略：通用场景（参数化），单函数 + @pytest.mark.parametrize
"""
import allure
import pytest

from common.test_helpers import execute_test_case
from utils.data_loader import get_test_data, get_global_variables


_DATA_FILE = "data/admin/api/douyin_product_query/douyin_product_query_api.yaml"

# 预加载所有用例数据
_ALL_CASES = get_test_data(_DATA_FILE, "douyin_product_query_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 douyin_product_query_api.yaml")


@allure.epic("运营端")
@allure.feature("运营端-商品管理")
@allure.story("抖音商品查询")
@pytest.mark.parametrize("case", _ALL_CASES, ids=[c["case_id"] for c in _ALL_CASES])
def test_douyin_product_query(case, admin_api_client, db):
    """抖音商品查询 - 多条件筛选验证"""
    global_vars = get_global_variables("douyin_product_query_api.yaml")
    execute_test_case(case, admin_api_client, db, global_vars)
