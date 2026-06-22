# testcases/merchant/scenario/order/conftest.py
# -*- coding: utf-8 -*-
"""
商家端 - 订单模块场景测试 - 执行顺序控制

执行顺序：
  1. test_renewal_order.py        （独立订单续租）
  2. test_partial_repayment.py    （部分还款-销账流程）
  3. test_relet_cancel_relet_order.py （续租/取消续租完整流程）
"""


# 定义文件执行优先级（数字越小越先执行）
_FILE_ORDER = {
    "test_renewal_order.py": 1,
    "test_partial_repayment.py": 2,
    "test_relet_cancel_relet_order.py": 3,
}


def pytest_collection_modifyitems(items):
    """按 _FILE_ORDER 中定义的优先级对测试用例重新排序"""
    def sort_key(item):
        filename = item.fspath.basename
        return _FILE_ORDER.get(filename, 99)

    items.sort(key=sort_key)
