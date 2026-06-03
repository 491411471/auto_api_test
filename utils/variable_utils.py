# utils/variable_utils.py
import json
import re
from decimal import Decimal
from typing import Any, Dict, List

from common.logger import logger


def needs_replacement(obj: Any) -> bool:
    """检查对象中是否包含 ${xxx} 占位符"""
    try:
        obj_str = json.dumps(obj, ensure_ascii=False)
    except TypeError:
        obj_str = str(obj)
    return re.search(r'\$\{([^}]+)}', obj_str) is not None


def replace_variables(obj: Any, variables: Dict[str, Any]) -> Any:
    """递归替换对象中所有 ${key} 占位符"""
    if isinstance(obj, dict):
        return {k: replace_variables(v, variables) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_variables(item, variables) for item in obj]
    elif isinstance(obj, str):
        result = obj
        for key, value in variables.items():
            placeholder = f"${{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result
    else:
        return obj


def get_value_by_path(data: Any, path: str) -> Any:
    """
    根据路径获取值，支持：
    - 普通键: "data.records"
    - 数组索引: "data.records[0].status"
    - 通配符: "data.records[*].status"  -> 返回所有 status 值列表
    """
    if data is None:
        return None

    keys = path.split('.')
    result = data
    for key in keys:
        if result is None:
            return None

        # 通配符 [*]
        if '[*]' in key:
            array_key = key.split('[*]')[0]
            if not isinstance(result, dict) or array_key not in result:
                return None
            array_data = result[array_key]
            if not isinstance(array_data, list):
                return None
            remaining = '.'.join(keys[keys.index(key) + 1:])
            return [get_value_by_path(item, remaining) for item in array_data]

        # 数组索引 "records[0]"
        elif '[' in key and key.endswith(']'):
            array_key = key.split('[')[0]
            idx_str = key.split('[')[1].rstrip(']')
            try:
                idx = int(idx_str)
            except ValueError:
                return None
            if not isinstance(result, dict) or array_key not in result:
                return None
            array_data = result[array_key]
            if not isinstance(array_data, list) or len(array_data) <= idx:
                return None
            result = array_data[idx]
        else:
            # 普通键
            if isinstance(result, dict):
                result = result.get(key)
            elif isinstance(result, list) and key.isdigit():
                idx = int(key)
                result = result[idx] if idx < len(result) else None
            else:
                return None
    return result


def validate(actual: Any, operator: str, expected: Any, path: str = "") -> None:
    """
    通用断言验证，支持多种操作符：
    ==, !=, >, >=, <, <=, contains, not_contains, length, type,
    all_in, any_contain, all_contain, all_eq, all_between, regex_match,
    empty, not_empty, has_key, not_has_key, startswith, endswith,
    between, length_gt, length_ge, length_lt, length_le,
    same_elements, is_none, is_not_none, date_between, datetime_between
    """
    import allure

    if operator == "exists":
        logger.info("⚠️注意：exists 操作符仅判断字段是否存在（actual 不为 None），不校验具体值")
        allure.attach(
            "⚠️注意：exists 操作符仅判断字段是否存在（actual 不为 None），不校验具体值",
            name="exists 操作符说明",
            attachment_type=allure.attachment_type.TEXT
        )

    log_msg = (
        f"\n{'#' * 40}\n"
        f"  操作路径：{path}\n"
        f"  操作符　：{operator}\n"
        f"  期望值　：{expected}\n"
        f"  实际值　：{actual}\n"
        f"{'#' * 40}"
    )
    logger.info(log_msg)
    allure.attach(
        f"操作路径：{path}\n"
        f"操作符　：{operator}\n"
        f"期望值　：{expected}\n"
        f"实际值　：{actual}",
        name="断言详情",
        attachment_type=allure.attachment_type.TEXT
    )

    # 辅助函数：格式化错误信息
    def format_error(msg: str) -> str:
        return f"{msg}\n  Path: {path}\n  Operator: {operator}\n  Expected: {expected}\n  Actual: {actual}"

    # 特殊处理：期望值为字符串 "None" 时转为 None
    if operator == "==" and expected == "None":
        expected = None

    # 基础比较操作符
    if operator == "==":
        # ====== 类型宽容处理：统一数值类型再比较 ======
        try:
            # 1. 实际值是字符串，期望值是数字：尝试将实际值转为数字
            if isinstance(actual, str) and isinstance(expected, (int, float)):
                if actual.lstrip('-').replace('.', '', 1).isdigit():
                    actual = type(expected)(actual)
            # 2. 实际值是数字，期望值是字符串数字：尝试将期望值转为数字
            elif isinstance(actual, (int, float)) and isinstance(expected, str):
                if expected.lstrip('-').replace('.', '', 1).isdigit():
                    expected = type(actual)(expected)
            # 3. 任意一方是 Decimal，统一转为 float 再比较（避免 Decimal 与 float 精度差异）
            elif isinstance(actual, Decimal) or isinstance(expected, Decimal):
                if isinstance(actual, Decimal):
                    actual = float(actual)
                if isinstance(expected, Decimal):
                    expected = float(expected)
            # 4. 实际值是 float/int，期望值也是 float/int，但类型不同（如 int vs float）：统一转为 float
            elif isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
                if type(actual) != type(expected):
                    actual = float(actual)
                    expected = float(expected)
                # 对于两个都是 float 的情况，使用近似比较避免精度问题
                else:
                    # 如果数值非常接近（误差小于 1e-9），认为相等
                    if abs(float(actual) - float(expected)) < 1e-9:
                        # 统一为相同的值以通过断言
                        actual = expected
        except (ValueError, TypeError):
            pass  # 转换失败则保持原样
        # ===========================
        assert actual == expected, format_error(f"期望 {expected}, 实际 {actual}")

    elif operator == "!=":
        assert actual != expected, format_error(f"期望不等于 {expected}, 实际 {actual}")

    elif operator == ">":
        assert actual > expected, format_error(f"期望大于 {expected}, 实际 {actual}")

    elif operator == ">=":
        assert actual >= expected, format_error(f"期望大于等于 {expected}, 实际 {actual}")

    elif operator == "<":
        assert actual < expected, format_error(f"期望小于 {expected}, 实际 {actual}")

    elif operator == "<=":
        assert actual <= expected, format_error(f"期望小于等于 {expected}, 实际 {actual}")

    # 字符串相关操作符
    elif operator in ("contains", "in", "IN"):
        assert expected in str(actual), format_error(f"期望包含 '{expected}', 实际 '{actual}'")

    elif operator == "not_contains":
        assert expected not in str(actual), format_error(f"期望不包含 '{expected}', 实际 '{actual}'")

    elif operator == "startswith":
        assert str(actual).startswith(str(expected)), format_error(f"期望以 '{expected}' 开头, 实际 '{actual}'")

    elif operator == "endswith":
        assert str(actual).endswith(str(expected)), format_error(f"期望以 '{expected}' 结尾, 实际 '{actual}'")

    elif operator == "regex_match":
        assert re.match(expected, str(actual)), format_error(f"字符串 '{actual}' 不匹配正则 '{expected}'")

    # 长度相关操作符
    elif operator == "length":
        assert len(actual) == expected, format_error(f"期望长度 {expected}, 实际 {len(actual)}")

    elif operator == "length_gt":
        assert len(actual) > expected, format_error(f"期望长度大于 {expected}, 实际 {len(actual)}")

    elif operator == "length_ge":
        assert len(actual) >= expected, format_error(f"期望长度大于等于 {expected}, 实际 {len(actual)}")

    elif operator == "length_lt":
        assert len(actual) < expected, format_error(f"期望长度小于 {expected}, 实际 {len(actual)}")

    elif operator == "length_le":
        assert len(actual) <= expected, format_error(f"期望长度小于等于 {expected}, 实际 {len(actual)}")

    # 类型相关操作符
    elif operator == "type":
        type_map = {
            "list": list, "dict": dict, "str": str, "int": int,
            "float": float, "bool": bool, "None": type(None),
            "tuple": tuple, "set": set, "bytes": bytes
        }
        expected_type = type_map.get(expected, str)
        assert isinstance(actual, expected_type), format_error(f"期望类型 {expected}, 实际 {type(actual).__name__}")

    # None 相关操作符
    elif operator == "is_none":
        assert actual is None, format_error(f"期望为 None, 实际 {actual}")

    elif operator == "is_not_none":
        assert actual is not None, format_error(f"期望不为 None, 实际为 None")

    # 空值相关操作符
    elif operator == "empty":
        if isinstance(actual, (list, dict, str, tuple, set)):
            assert len(actual) == 0, format_error(f"期望为空, 实际 {actual}")
        else:
            assert actual is None or actual == "", format_error(f"期望为空, 实际 {actual}")

    elif operator == "not_empty":
        # 验证值不为空
        if isinstance(actual, (list, dict, str, tuple, set)):
            assert len(actual) > 0, format_error(
                f"期望非空\n"
                f"  类型: {type(actual).__name__}\n"
                f"  长度: {len(actual)}\n"
                f"  实际值: {actual}"
            )
        else:
            assert actual is not None and actual != "", format_error(
                f"期望非空\n"
                f"  类型: {type(actual).__name__ if actual is not None else 'NoneType'}\n"
                f"  实际值: {actual}"
            )

    # 字典相关操作符
    elif operator == "has_key":
        assert isinstance(actual, dict), format_error(f"期望字典, 实际 {type(actual).__name__}")
        assert expected in actual, format_error(f"期望包含键 '{expected}', 实际键: {list(actual.keys())}")

    elif operator == "not_has_key":
        assert isinstance(actual, dict), format_error(f"期望字典, 实际 {type(actual).__name__}")
        assert expected not in actual, format_error(f"期望不包含键 '{expected}', 实际包含")

    # 列表相关操作符
    elif operator == "all_in":
        assert isinstance(actual, list), format_error(f"期望列表, 实际 {type(actual)}")
        for item in actual:
            assert item in expected, format_error(f"元素 {item} 不在期望集合 {expected} 中")

    elif operator == "any_contain":
        if isinstance(actual, list):
            assert any(expected in str(item) for item in actual), format_error(f"没有任何元素包含 '{expected}'")
        else:
            assert expected in str(actual), format_error(f"不包含 '{expected}'")

    elif operator == "all_contain":
        assert isinstance(actual, list), format_error(f"期望列表, 实际 {type(actual)}")
        for item in actual:
            assert expected in str(item), format_error(f"元素 {item} 不包含 '{expected}'")

    elif operator == "all_eq":
        assert isinstance(actual, list), format_error(f"期望列表, 实际 {type(actual)}")
        for item in actual:
            print("item", item)
            assert item == expected, format_error(f"元素 {item} 不等于 {expected}")

    elif operator == "all_between":
        start, end = expected
        assert isinstance(actual, list), format_error(f"期望列表, 实际 {type(actual)}")
        for item in actual:
            assert start <= item <= end, format_error(f"元素 {item} 不在 [{start}, {end}] 范围内")

    elif operator == "same_elements":
        assert isinstance(actual, list) and isinstance(expected, list), format_error("期望两个列表")
        assert sorted(actual) == sorted(expected), format_error(
            f"元素不一致\n  实际: {sorted(actual)}\n  期望: {sorted(expected)}")

    # 范围相关操作符
    elif operator == "between":
        start, end = expected
        assert start <= actual <= end, format_error(f"值 {actual} 不在 [{start}, {end}] 范围内")

    elif operator == "date_between":
        from datetime import datetime
        if isinstance(actual, str):
            actual_date = datetime.strptime(actual, "%Y-%m-%d").date()
        else:
            actual_date = actual.date() if hasattr(actual, 'date') else actual

        start_date = expected[0]
        end_date = expected[1]
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        assert start_date <= actual_date <= end_date, format_error(
            f"日期 {actual} 不在 [{expected[0]}, {expected[1]}] 范围内")

    elif operator == "datetime_between":
        from datetime import datetime
        if isinstance(actual, str):
            actual_dt = datetime.fromisoformat(actual)
        else:
            actual_dt = actual

        start_dt = expected[0]
        end_dt = expected[1]
        if isinstance(start_dt, str):
            start_dt = datetime.fromisoformat(start_dt)
        if isinstance(end_dt, str):
            end_dt = datetime.fromisoformat(end_dt)

        assert start_dt <= actual_dt <= end_dt, format_error(
            f"时间 {actual} 不在 [{expected[0]}, {expected[1]}] 范围内")

    elif operator == "exists":
        # 断言字段存在（即提取到的值不为 None）
        assert actual is not None, format_error("期望字段存在，但实际为 None")

    elif operator == "not_exists":
        # 断言字段不存在（即提取到的值为 None）
        assert actual is None, format_error("期望字段不存在，但实际存在")


    else:
        raise ValueError(format_error(f"不支持的验证操作符: {operator}"))