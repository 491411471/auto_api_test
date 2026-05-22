# utils/assert_utils.py
import json
from decimal import Decimal

import allure
from deepdiff import DeepDiff
from utils.variable_utils import get_value_by_path   # 复用路径取值


def _normalize_numeric_types(actual, expected):
    """
    统一数值类型，避免 Decimal vs float、int vs float 等类型不匹配导致 == 断言失败。
    返回归一化后的 (actual, expected) 元组。
    """
    # Decimal 与 float/int 混合：统一转为 float
    if isinstance(actual, Decimal) or isinstance(expected, Decimal):
        if isinstance(actual, Decimal):
            actual = float(actual)
        if isinstance(expected, Decimal):
            expected = float(expected)
        return actual, expected
    # int 与 float 混合：统一转为 float
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        if type(actual) != type(expected):
            return float(actual), float(expected)
    return actual, expected


def assert_status_code(actual_status: int, expected_status: int, message: str = "") -> None:
    """验证 HTTP 状态码"""
    with allure.step("验证HTTP状态码"):
        if actual_status == expected_status:
            allure.attach(
                f"HTTP状态码验证成功\n期望: {expected_status}\n实际: {actual_status}",
                name="HTTP状态码验证", attachment_type=allure.attachment_type.TEXT
            )
        else:
            error_msg = f"HTTP状态码不匹配: 期望 {expected_status}，实际 {actual_status}"
            final_message = f"{message}\n{error_msg}" if message else error_msg
            allure.attach(
                f"HTTP状态码验证失败\n期望: {expected_status}\n实际: {actual_status}\n\n{final_message}",
                name="HTTP状态码验证失败", attachment_type=allure.attachment_type.TEXT
            )
            raise AssertionError(final_message)


def assert_json_equal(actual_json, expected_json, ignore_order=True):
    """深度比较两个 JSON（可忽略数组顺序）"""
    diff = DeepDiff(expected_json, actual_json, ignore_order=ignore_order)
    if diff:
        allure.attach(json.dumps(diff, indent=2, ensure_ascii=False), "JSON差异", allure.attachment_type.JSON)
        raise AssertionError(f"JSON不一致: {diff}")
    allure.attach("JSON 完全匹配", "验证结果", attachment_type=allure.attachment_type.TEXT)


def assert_json_value(data: dict, path: str, expected_value, operator: str = "==", message: str = "") -> None:
    """
    验证 JSON 中指定路径的值
    支持操作符: ==, !=, >, >=, <, <=, contains, not_contains, length, length_gt, length_lt
    """
    with allure.step(f"验证JSON路径 '{path}' 的值"):
        try:
            actual_value = get_value_by_path(data, path)
        except (KeyError, IndexError, TypeError) as e:
            error_msg = f"路径 '{path}' 不存在或无效: {str(e)}"
            allure.attach(error_msg, name="断言失败详情", attachment_type=allure.attachment_type.TEXT)
            raise AssertionError(error_msg)

        # 比较逻辑 - 比较前统一数值类型
        if operator == "==":
            cmp_actual, cmp_expected = _normalize_numeric_types(actual_value, expected_value)
            result = cmp_actual == cmp_expected
            error_msg = f"期望 {expected_value}，实际 {actual_value}"
        elif operator == "!=":
            result = actual_value != expected_value
            error_msg = f"期望不等于 {expected_value}，实际 {actual_value}"
        elif operator == ">":
            result = actual_value > expected_value
            error_msg = f"期望大于 {expected_value}，实际 {actual_value}"
        elif operator == ">=":
            result = actual_value >= expected_value
            error_msg = f"期望大于等于 {expected_value}，实际 {actual_value}"
        elif operator == "<":
            result = actual_value < expected_value
            error_msg = f"期望小于 {expected_value}，实际 {actual_value}"
        elif operator == "<=":
            result = actual_value <= expected_value
            error_msg = f"期望小于等于 {expected_value}，实际 {actual_value}"
        elif operator == "contains":
            result = expected_value in str(actual_value)
            error_msg = f"期望包含 '{expected_value}'，实际 '{actual_value}'"
        elif operator == "not_contains":
            result = expected_value not in str(actual_value)
            error_msg = f"期望不包含 '{expected_value}'，实际 '{actual_value}'"
        elif operator == "length":
            result = len(actual_value) == expected_value
            error_msg = f"期望长度为 {expected_value}，实际 {len(actual_value)}"
        elif operator == "length_gt":
            result = len(actual_value) > expected_value
            error_msg = f"期望长度大于 {expected_value}，实际 {len(actual_value)}"
        elif operator == "length_lt":
            result = len(actual_value) < expected_value
            error_msg = f"期望长度小于 {expected_value}，实际 {len(actual_value)}"
        else:
            raise ValueError(f"不支持的操作符: {operator}")

        if result:
            allure.attach(
                f"断言成功\n路径: {path}\n操作符: {operator}\n期望值: {expected_value}\n实际值: {actual_value}",
                name="断言成功详情", attachment_type=allure.attachment_type.TEXT
            )
        else:
            final_message = f"{message}\n{error_msg}" if message else error_msg
            allure.attach(
                f"断言失败\n路径: {path}\n操作符: {operator}\n期望值: {expected_value}\n实际值: {actual_value}\n\n{final_message}",
                name="断言失败详情", attachment_type=allure.attachment_type.TEXT
            )
            allure.attach(str(data), name="完整响应数据", attachment_type=allure.attachment_type.JSON)
            raise AssertionError(final_message)


def assert_json_contains(data: dict, path: str, expected_keys=None, expected_values=None, message: str = "") -> None:
    """
    验证 JSON 中包含指定的键或键值对
    expected_keys: 字符串或列表
    expected_values: 字典
    """
    with allure.step(f"验证JSON路径 '{path}' 包含指定内容"):
        try:
            target = get_value_by_path(data, path)
        except (KeyError, IndexError, TypeError) as e:
            error_msg = f"路径 '{path}' 不存在或无效: {str(e)}"
            allure.attach(error_msg, name="断言失败详情", attachment_type=allure.attachment_type.TEXT)
            raise AssertionError(error_msg)

        if not isinstance(target, dict):
            error_msg = f"路径 '{path}' 不是字典类型，实际是 {type(target).__name__}"
            allure.attach(error_msg, name="断言失败详情", attachment_type=allure.attachment_type.TEXT)
            raise AssertionError(error_msg)

        success_msgs = []
        error_msgs = []

        # 验证键存在
        if expected_keys:
            if isinstance(expected_keys, str):
                expected_keys = [expected_keys]
            missing = [k for k in expected_keys if k not in target]
            if missing:
                error_msgs.append(f"缺少键: {missing}")
            else:
                success_msgs.extend([f"键 '{k}' 存在" for k in expected_keys])

        # 验证键值对
        if expected_values:
            for key, expected_val in expected_values.items():
                if key not in target:
                    error_msgs.append(f"键 '{key}' 不存在")
                elif target[key] != expected_val:
                    error_msgs.append(f"键 '{key}': 期望 {expected_val}，实际 {target[key]}")
                else:
                    success_msgs.append(f"键 '{key}' 的值为 {expected_val}")

        if error_msgs:
            final_message = f"{message}\n" + "\n".join(error_msgs) if message else "\n".join(error_msgs)
            allure.attach(
                f"断言失败\n路径: {path}\n\n{final_message}",
                name="断言失败详情", attachment_type=allure.attachment_type.TEXT
            )
            allure.attach(str(target), name="目标数据", attachment_type=allure.attachment_type.JSON)
            raise AssertionError(final_message)
        else:
            allure.attach(
                f"断言成功\n路径: {path}\n\n" + "\n".join(success_msgs),
                name="断言成功详情", attachment_type=allure.attachment_type.TEXT
            )