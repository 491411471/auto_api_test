# common/test_helpers.py
import copy
import json
import re
import time
from typing import Any, Dict, Set, List

import allure
from common.logger import logger
from utils.assert_utils import assert_status_code
from utils.variable_utils import validate,needs_replacement

try:
    # 优先使用 jsonpath_ng.ext.parse（支持过滤表达式 [?(@.field=="value")]）
    # ext.parse 是 parse 的超集，完全向后兼容
    from jsonpath_ng.ext import parse as jsonpath_parse
    from jsonpath_ng.exceptions import JsonPathParserError, JsonPathLexerError
    JSONPATH_AVAILABLE = True
except ImportError:
    try:
        from jsonpath_ng import parse as jsonpath_parse
        from jsonpath_ng.exceptions import JsonPathParserError, JsonPathLexerError
        JSONPATH_AVAILABLE = True
    except ImportError:
        JSONPATH_AVAILABLE = False
        JsonPathParserError = Exception
        JsonPathLexerError = Exception


# ==================== 通用变量替换函数 ====================
def replace_placeholders(data: Any, variables: Dict[str, Any]) -> Any:
    """递归替换对象中所有字符串值里的 ${key} 占位符。"""
    if isinstance(data, str):
        # 完全匹配占位符 ${key}
        for key, value in variables.items():
            placeholder = f"${{{key}}}"
            if data == placeholder:
                # 递归处理 value（可能包含嵌套占位符）
                return replace_placeholders(value, variables)
        # 部分匹配替换（可能字符串内嵌多个占位符）
        def replacer(match):
            key = match.group(1)
            if key in variables:
                val = variables[key]
                return str(val) if val is not None else ''
            return match.group(0)
        return re.sub(r'\$\{([^}]+)}', replacer, data)
    elif isinstance(data, dict):
        return {k: replace_placeholders(v, variables) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_placeholders(item, variables) for item in data]
    else:
        return data


def extract_placeholders(obj: Any) -> Set[str]:
    """提取对象中所有 ${xxx} 占位符的键名集合"""
    obj_str = json.dumps(obj, ensure_ascii=False)
    return set(re.findall(r'\$\{([^}]+)}', obj_str))


# ==================== SQL 处理 ====================
def execute_sql(db, sql_config: Dict[str, Any]) -> Any:
    """
    执行 SQL，支持单行/多行结果。
    支持返回多个字段（columns列表）或单个字段（column字符串）。
    """
    query = sql_config.get('query')
    if not query:
        return None

    multiple = sql_config.get('multiple', False)
    column = sql_config.get('column')          # 单个字段名
    columns = sql_config.get('columns')        # 多个字段名列表

    step_name = "执行数据库查询"
    if columns:
        step_name += f" (返回字段: {', '.join(columns)})"
    elif column:
        step_name += f" (返回字段: {column})"
    else:
        step_name += " (返回整行)"
    with allure.step(step_name):
        allure.attach(query, name="执行的 SQL", attachment_type=allure.attachment_type.TEXT)
        logger.info(f"执行 SQL: {query}")

        if multiple:
            rows = db.fetch_all(query)
            if not rows:
                raise ValueError(f"SQL 无结果: {query}")
            if columns:
                # 多行，每行提取指定字段列表 -> 返回列表[字典]
                result = []
                for row in rows:
                    if isinstance(row, dict):
                        result.append({col: row.get(col) for col in columns})
                    else:
                        # 如果 row 是 tuple/list 且 columns 长度匹配
                        result.append(dict(zip(columns, row)))
                allure.attach(str(result), name="SQL 结果（多行，多字段）", attachment_type=allure.attachment_type.TEXT)
                return result
            elif column:
                # 多行，返回列表[值]
                if rows and isinstance(rows[0], dict):
                    values = [row[column] for row in rows]
                else:
                    # 假设结果集第一列就是所需字段
                    values = [row[0] for row in rows]
                allure.attach(f"{column} = {values}", name="SQL 结果", attachment_type=allure.attachment_type.TEXT)
                return values
            else:
                allure.attach(str(rows), name="SQL 结果", attachment_type=allure.attachment_type.TEXT)
                return rows
        else:
            # 单行结果
            result = db.fetch_one(query)
            if result is None:
                raise ValueError(f"SQL 无结果: {query}")

            if columns:
                # 返回字典 {col: value}
                if isinstance(result, dict):
                    data = {col: result.get(col) for col in columns}
                else:
                    # result 可能是 tuple/list，假设顺序与 columns 一致
                    data = dict(zip(columns, result))
                allure.attach(str(data), name="SQL 结果（多字段）", attachment_type=allure.attachment_type.TEXT)
                return data
            elif column:
                # 返回单个值
                if isinstance(result, dict):
                    if column not in result:
                        raise ValueError(f"列 '{column}' 不存在，可用: {list(result.keys())}")
                    value = result[column]
                else:
                    # result 可能是 tuple/list，取第一个元素
                    value = result[0] if result else None
                allure.attach(f"{column} = {value}", name="SQL 结果", attachment_type=allure.attachment_type.TEXT)
                return value
            else:
                # 返回整行（字典或元组）
                allure.attach(str(result), name="SQL 结果", attachment_type=allure.attachment_type.TEXT)
                return result


def process_dynamic_data(case: Dict[str, Any], db, variables: Dict[str, Any]) -> None:
    """
    处理 YAML 中的 sql 配置，支持单个 SQL 或 SQL 列表（顺序执行）。
    每个 SQL 返回的字段会更新到 variables 中，供后续 SQL 或请求使用。
    """
    if 'sql' not in case:
        return

    sql_configs = case['sql']
    if not isinstance(sql_configs, list):
        sql_configs = [sql_configs]

    with allure.step("处理 SQL 动态数据（顺序执行）"):
        for idx, sql_config in enumerate(sql_configs):
            step_suffix = f" (步骤 {idx+1}/{len(sql_configs)})" if len(sql_configs) > 1 else ""
            with allure.step(f"执行 SQL 并提取变量{step_suffix}"):
                # 先替换该 SQL 中的占位符（使用当前 variables）
                sql_config_replaced = replace_placeholders(sql_config, variables)
                replaced_query = sql_config_replaced.get('query', '')
                allure.attach(replaced_query, name=f"替换变量后的 SQL{step_suffix}", attachment_type=allure.attachment_type.TEXT)

                try:
                    result = execute_sql(db, sql_config_replaced)
                except Exception as e:
                    # SQL 执行失败时记录完整诊断信息到 Allure，便于定位问题
                    error_msg = str(e)
                    diag_info = (
                        f"SQL 执行失败!\n"
                        f"错误类型: {type(e).__name__}\n"
                        f"错误信息: {error_msg}\n"
                        f"当前 variables 键: {list(variables.keys())}\n"
                        f"SQL 前 500 字符:\n{replaced_query[:500]}"
                    )
                    logger.error(f"SQL 执行失败: {error_msg}")
                    allure.attach(diag_info, name=f"SQL 执行失败诊断{step_suffix}", attachment_type=allure.attachment_type.TEXT)
                    raise

                if result is None:
                    continue

                # 将结果更新到 variables
                if isinstance(result, dict):
                    # 多字段返回：如 {"order_id": "xxx", "status": "04"}
                    variables.update(result)
                    logger.info(f"从数据库获取的变量: {result}")
                    allure.attach(str(result), name=f"从数据库获取的变量（多字段）{step_suffix}", attachment_type=allure.attachment_type.TEXT)
                elif isinstance(result, list):
                    # 多行结果
                    column = sql_config.get('column')
                    columns = sql_config.get('columns')
                    if column:
                        variables[column] = result
                        logger.info(f"从数据库获取的变量（多行）: {column} = {result}")
                        allure.attach(f"{column} = {result}", name=f"从数据库获取的变量（多行）{step_suffix}", attachment_type=allure.attachment_type.TEXT)
                    elif columns:
                        # 多行多字段，通常保存为列表[字典]
                        variables['sql_result'] = result
                        logger.info(f"从数据库获取的变量（多行多字段）: sql_result = {result}")
                        allure.attach(f"sql_result = {result}", name=f"从数据库获取的变量（多行多字段）{step_suffix}", attachment_type=allure.attachment_type.TEXT)
                    else:
                        variables['sql_result'] = result
                        logger.info(f"从数据库获取的变量（多行）: sql_result = {result}")
                        allure.attach(f"sql_result = {result}", name=f"从数据库获取的变量（多行）{step_suffix}", attachment_type=allure.attachment_type.TEXT)
                else:
                    # 单值
                    column = sql_config.get('column')
                    if column:
                        variables[column] = result
                        logger.info(f"从数据库获取的变量: {column} = {result}")
                        allure.attach(f"{column} = {result}", name=f"从数据库获取的变量{step_suffix}", attachment_type=allure.attachment_type.TEXT)
                    else:
                        variables['sql_result'] = result
                        logger.info(f"从数据库获取的变量: sql_result = {result}")
                        allure.attach(f"sql_result = {result}", name=f"从数据库获取的变量{step_suffix}", attachment_type=allure.attachment_type.TEXT)


# ==================== 响应处理与断言 ====================
def get_records_from_response(data: Dict[str, Any]) -> list:
    """安全提取响应中的 records 列表"""
    if not isinstance(data, dict):
        return []
    if 'records' in data and isinstance(data['records'], list):
        return data['records']
    if 'data' in data and isinstance(data['data'], dict):
        inner = data['data']
        if 'records' in inner and isinstance(inner['records'], list):
            return inner['records']
    return []


def validate_response(case: Dict[str, Any], response_data: Dict[str, Any], variables: Dict[str, Any]) -> None:
    """执行所有断言验证，每个断言独立写入 Allure 步骤（无额外嵌套）"""

    def get_value_by_path_enhanced(obj: Any, path: str) -> Any:
        """
        增强的路径取值，支持 JSONPath、条件筛选、数组索引、通配符 [*] 等。
        """
        # 1. JSONPath 优先（保留原有逻辑）
        if JSONPATH_AVAILABLE:
            jsonpath_str = path
            if not jsonpath_str.startswith('$'):
                jsonpath_str = '$.' + jsonpath_str
            jsonpath_str = re.sub(r"==\s*'([^']*)'", r'=="\1"', jsonpath_str)
            jsonpath_str = re.sub(r'\?\(\s*@\.', '?(@.', jsonpath_str)
            try:
                expr = jsonpath_parse(jsonpath_str)
                matches = expr.find(obj)
                if matches:
                    # 包含通配符 [*] 的路径始终返回列表，即使只有一个匹配
                    if '[*]' in path:
                        return [m.value for m in matches]
                    return matches[0].value if len(matches) == 1 else [m.value for m in matches]
            except (JsonPathParserError, JsonPathLexerError) as e:
                logger.debug(f"JSONPath 解析失败: {jsonpath_str}, 错误: {e}，降级使用自定义解析")

        # 2. 条件筛选语法：array[?(@.field=='value')].subpath
        pattern = r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*\[\?\s*\(\s*@\.([a-zA-Z_][a-zA-Z0-9_]*)\s*==\s*[\'\"](.*?)[\'\"]\s*\)\s*\](?:\.(.*))?$'
        match = re.match(pattern, path)
        if match:
            array_name, field_name, expected_value, sub_path = match.groups()
            if not isinstance(obj, dict):
                return None
            array_obj = obj.get(array_name)
            if not isinstance(array_obj, list):
                return None
            for item in array_obj:
                if isinstance(item, dict) and str(item.get(field_name)) == expected_value:
                    if sub_path:
                        return get_value_by_path_enhanced(item, sub_path)
                    return item
            return None

        # ==================== 3. 增强的点分隔路径（支持 [*] 通配符） ====================
        # 清洗开头的 '$' 或 '$.'
        clean_path = path
        if clean_path.startswith('$.'):
            clean_path = clean_path[2:]
        elif clean_path.startswith('$'):
            clean_path = clean_path[1:]

        # 将路径按 '.' 分割，并解析每个片段（支持字段名、[数字]、[*]）
        parts = []
        for part in clean_path.split('.'):
            if not part:
                continue
            # 匹配形如 "records[*]" 或 "records[0]" 或 "type"
            bracket_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)?(?:\[(\d+|\*)\])?$', part)
            if bracket_match:
                field_name = bracket_match.group(1)  # 可能为 None（如纯 "[0]"）
                idx_or_wild = bracket_match.group(2)  # 数字或 '*'
                if field_name:
                    parts.append(field_name)
                if idx_or_wild:
                    if idx_or_wild == '*':
                        parts.append('*')  # 通配符标记
                    else:
                        parts.append(int(idx_or_wild))
            else:
                # 普通字段
                parts.append(part)

        # 递归提取函数
        def _extract(current, path_parts):
            if not path_parts:
                return current
            part = path_parts[0]
            rest = path_parts[1:]

            if current is None:
                return None
            if part == '*':
                # 通配符：当前必须是列表，对每个元素递归提取剩余路径，收集结果
                if not isinstance(current, list):
                    return None
                results = []
                for item in current:
                    val = _extract(item, rest)
                    if val is not None:
                        # 如果 val 是列表，则展开（扁平化）
                        if isinstance(val, list):
                            results.extend(val)
                        else:
                            results.append(val)
                return results if results else None
            elif isinstance(part, int):
                # 数字索引
                if isinstance(current, list) and 0 <= part < len(current):
                    return _extract(current[part], rest)
                else:
                    return None
            else:
                # 字典键
                if isinstance(current, dict):
                    return _extract(current.get(part), rest)
                else:
                    return None

        return _extract(obj, parts)

    # ---- expected_fields ----
    if case.get('expected_fields'):
        from utils.assert_utils import assert_json_contains
        for field in case['expected_fields']:
            with allure.step(f"验证字段存在: {field}"):
                assert_json_contains(response_data, "", [field])

    # ---- expected_values ----
    if case.get('expected_values'):
        from utils.assert_utils import assert_json_value
        for key, expected in case['expected_values'].items():
            with allure.step(f"验证键值对: {key} == {expected}"):
                if isinstance(expected, str) and '${' in expected:
                    expected = replace_placeholders(expected, variables)
                assert_json_value(response_data, key, expected)

    # ---- validate_data ----
    records_cache = None
    if case.get('validate_data'):
        # 诊断：记录当前可用变量，便于排查占位符未替换问题
        sql_var_keys = [k for k in variables.keys() if k not in ('base_url', 'channelGroupCode', 'shop_id')]
        if sql_var_keys:
            sql_vars_snapshot = {k: variables[k] for k in sql_var_keys}
            allure.attach(
                json.dumps(sql_vars_snapshot, ensure_ascii=False, indent=2),
                name="断言前可用变量（SQL结果）",
                attachment_type=allure.attachment_type.TEXT
            )
        # 检查是否有未替换的占位符
        validate_data_str = json.dumps(case['validate_data'], ensure_ascii=False)
        if '${' in validate_data_str:
            import re as _re
            unresolved = _re.findall(r'\$\{([^}]+)\}', validate_data_str)
            msg = f"以下变量未替换，可能已导致断言失败:\n" + '\n'.join(f'  ${{{v}}}' for v in set(unresolved))
            logger.warning(msg)
            allure.attach(msg, name="未替换变量警告", attachment_type=allure.attachment_type.TEXT)
        for idx, v in enumerate(case['validate_data']):
            path = v['path']
            operator = v['operator']
            # 使用 .get() 兼容无期望值的操作符（如 exists, is_none, empty 等）
            expected = v.get('value')

            # ====== 改进：递归替换所有类型的期望值（不仅是字符串）======
            # 检查期望值中是否包含占位符（支持字符串、字典、列表）
            if expected is not None and needs_replacement(expected):
                expected = replace_placeholders(expected, variables)
                logger.debug(f"断言 {idx+1} 期望值替换: {v['value']} -> {expected}")
            # ======================================================

            # 特殊处理空 records
            if path == "data.records" and operator == "==" and expected == []:
                if records_cache is None:
                    records_cache = get_records_from_response(response_data)
                with allure.step(f"验证 records 为空列表"):
                    assert records_cache == [], f"期望 records 为空列表，实际为: {records_cache}"
                continue

            if path == "data" and operator == "==" and expected is None:
                actual_data = response_data.get('data') if isinstance(response_data, dict) else None
                with allure.step(f"验证 data 为 None"):
                    assert actual_data is None, f"期望 data 为 None，实际为: {actual_data}"
                continue

            # 每个断言独立步骤（无期望值时只显示操作符）
            if expected is not None:
                step_title = f"断言 {idx+1}: {path} {operator} {expected}"
            else:
                step_title = f"断言 {idx+1}: {path} {operator}"
            with allure.step(step_title):
                actual = get_value_by_path_enhanced(response_data, path)
                
                # ====== 类型归一化：根据 type_check 统一 expected 和 actual 的数据类型 ======
                type_check = v.get('type_check')
                if expected is not None:
                    if type_check == 'float':
                        try:
                            expected = float(expected)
                            if actual is not None:
                                actual = float(actual)
                        except (ValueError, TypeError):
                            pass
                    elif type_check == 'int':
                        try:
                            expected = int(expected)
                            if actual is not None:
                                actual = int(actual)
                        except (ValueError, TypeError):
                            pass
                    elif type_check == 'str':
                        expected = str(expected) if expected is not None else expected
                        actual = str(actual) if actual is not None else actual
                # ===========================
                
                allure.attach(
                    f"路径: {path}\n操作符: {operator}\n期望值: {expected if expected is not None else '(无需期望值)'}\n实际值: {actual}",
                    name="断言详情",
                    attachment_type=allure.attachment_type.TEXT
                )
                # 附加响应数据快照
                response_preview = json.dumps(response_data, ensure_ascii=False)[:2000]
                allure.attach(response_preview, name="响应数据快照", attachment_type=allure.attachment_type.JSON)
                validate(actual, operator, expected, path)

    # ---- min_count ----
    if case.get('min_count'):
        with allure.step(f"验证 records 最小数量 >= {case['min_count']}"):
            if records_cache is None:
                records_cache = get_records_from_response(response_data)
            assert len(records_cache) >= case['min_count'], \
                f"订单数量应不少于 {case['min_count']}, 实际为 {len(records_cache)}"


# ==================== 辅助函数：安全获取 SQL 显示字符串 ====================
def _get_sql_display(case: Dict[str, Any]) -> str:
    """从 case 中提取 SQL 用于日志和附件，兼容列表和字典"""
    sql_conf = case.get('sql')
    if sql_conf is None:
        return ''
    if isinstance(sql_conf, list):
        # 取第一条 SQL 的 query 并标注有多条
        if len(sql_conf) > 0:
            first_query = sql_conf[0].get('query', '')
            return f"[多条 SQL，共 {len(sql_conf)} 条] 第一条: {first_query[:200]}"
        else:
            return '[]'
    elif isinstance(sql_conf, dict):
        return sql_conf.get('query', '')
    else:
        return str(sql_conf)


# ==================== Allure 报告结构化摘要辅助函数 ====================
def _attach_sql_vars_summary(variables: Dict[str, Any]) -> None:
    """将所有 SQL 提取的变量聚合为一个摘要附件，便于报告中一览数据库查询结果"""
    # 排除框架级 / 配置级变量，仅展示 SQL 结果
    _BUILTIN_KEYS = {'base_url', 'channelGroupCode', 'shop_id', 'token', 'access_token'}
    sql_vars = {k: v for k, v in variables.items() if k not in _BUILTIN_KEYS and not k.startswith('_')}
    if not sql_vars:
        return
    summary = json.dumps(sql_vars, ensure_ascii=False, indent=2, default=str)
    allure.attach(summary, name="SQL 提取变量汇总", attachment_type=allure.attachment_type.JSON)
    logger.info(f"SQL 提取变量汇总: {sql_vars}")


def _attach_request_overview(method: str, endpoint: str, params: Any, body_data: Any) -> None:
    """将请求的 method/endpoint/params/body 聚合为一个结构化概览附件"""
    overview: Dict[str, Any] = {
        "method": method,
        "endpoint": endpoint,
    }
    if params:
        overview["params"] = params
    if body_data:
        # 截取过长的 body，避免报告臃肿
        body_str = json.dumps(body_data, ensure_ascii=False)
        overview["body"] = body_data if len(body_str) <= 2000 else json.loads(body_str[:2000] + '"..."}')
    allure.attach(
        json.dumps(overview, ensure_ascii=False, indent=2, default=str),
        name="请求概览",
        attachment_type=allure.attachment_type.JSON
    )


def _attach_response_summary(response_data: Dict[str, Any]) -> None:
    """提取响应中 data 层的关键字段作为摘要附件，便于快速定位业务结果"""
    if not isinstance(response_data, dict):
        return
    summary: Dict[str, Any] = {
        "rpcResult": response_data.get("rpcResult"),
        "businessSuccess": response_data.get("businessSuccess"),
        "errorCode": response_data.get("errorCode"),
        "errorMessage": response_data.get("errorMessage"),
    }
    # 提取 data 层摘要
    data = response_data.get("data")
    if isinstance(data, dict):
        data_summary: Dict[str, Any] = {}
        # 分页字段
        for pf in ("total", "size", "current", "pages"):
            if pf in data:
                data_summary[pf] = data[pf]
        # records 摘要
        records = data.get("records")
        if isinstance(records, list):
            data_summary["records_count"] = len(records)
            if records:
                # 展示首条记录的关键字段（最多 10 个字段）
                first = records[0]
                if isinstance(first, dict):
                    data_summary["records[0]_preview"] = {
                        k: v for i, (k, v) in enumerate(first.items()) if i < 10
                    }
        summary["data"] = data_summary
    elif data is not None:
        summary["data"] = str(data)[:500]

    allure.attach(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        name="响应摘要",
        attachment_type=allure.attachment_type.JSON
    )


# ==================== 从响应提取变量（支持多种配置形式） ====================
def _extract_response_vars(response_data: Any, extract_vars: Any, variables: Dict[str, Any]) -> None:
    """
    从响应中提取变量并写入 variables 字典。

    支持的 extract_vars 格式：
      - None / []: 不做任何事
      - 列表，元素为字符串或字典
      - 字符串形式："var_name=path.to.field"（等号分隔）
      - 字典形式：
          {"var_name": "order_id", "path": "data.orderId", "default": ""}
          或简洁形式 {"order_id": "data.orderId"}
          或支持正则: {"var_name":"x","regex":"orderId\\\":\\\"(\\d+)\\\""}

    path 支持简单的点分层访问及数字索引，如 "data.records[0].id"，以及以 "$" 开头的 JSONPath（如果安装了 jsonpath_ng 则优先使用）。
    """
    if not extract_vars:
        return

    if isinstance(extract_vars, dict):
        extract_list = [extract_vars]
    elif isinstance(extract_vars, list):
        extract_list = extract_vars
    else:
        # 允许单个字符串
        extract_list = [extract_vars]

    with allure.step("从响应中提取变量"):
        for item in extract_list:
            try:
                # 规范化 dict 项为 (var_name, path, extra)
                var_name = None
                path = None
                default = None
                regex = None

                if isinstance(item, str):
                    if '=' in item:
                        var_name, path = item.split('=', 1)
                        var_name = var_name.strip()
                        path = path.strip()
                    else:
                        # 无法解析的字符串，跳过
                        logger.debug(f"无法解析的 extract_vars 字符串: {item}")
                        continue
                elif isinstance(item, dict):
                    if 'var_name' in item or 'name' in item:
                        var_name = item.get('var_name') or item.get('name')
                        path = item.get('path')
                        default = item.get('default')
                        regex = item.get('regex')
                    elif len(item) == 1:
                        # 简洁形式 {"order_id": "data.orderId"}
                        var_name, path = next(iter(item.items()))
                    else:
                        # 兼容可能的形式
                        var_name = item.get('var') or item.get('key')
                        path = item.get('path')
                        default = item.get('default')
                        regex = item.get('regex')
                else:
                    logger.debug(f"未知的 extract_vars 项类型: {type(item)}")
                    continue

                if not var_name:
                    logger.debug(f"跳过无效的 extract_vars 项: {item}")
                    continue

                value = None

                # 正则优先（对整个响应文本匹配）
                if regex:
                    text = response_data if isinstance(response_data, str) else json.dumps(response_data, ensure_ascii=False)
                    m = re.search(regex, text)
                    if m:
                        value = m.group(1) if m.groups() else m.group(0)

                # JSONPath（若可用）或点路径解析
                if value is None and path:
                    # 尝试 JSONPath（当安装 jsonpath_ng 且可能为 jsonpath 表达式时）
                    used_jsonpath = False
                    if JSONPATH_AVAILABLE:
                        jp = path
                        if not jp.startswith('$'):
                            jp = '$.' + jp
                        try:
                            expr = jsonpath_parse(jp)
                            matches = expr.find(response_data)
                            if matches:
                                # 如果只有一个匹配则取单值，否则取列表
                                value = matches[0].value if len(matches) == 1 else [m.value for m in matches]
                                used_jsonpath = True
                        except Exception:
                            used_jsonpath = False

                    # 回退为简单点分路径解析
                    if not used_jsonpath and value is None:
                        # 清理开头的 $.
                        clean = path
                        if clean.startswith('$.'):
                            clean = clean[2:]
                        elif clean.startswith('$'):
                            clean = clean[1:]

                        current = response_data
                        # 支持点分和索引，如 records[0]
                        parts = [p for p in re.split(r'\.(?![^\[]*\])', clean) if p]
                        for part in parts:
                            if current is None:
                                break
                            m = re.match(r'^(?P<key>[^\[]+)?(?:\[(?P<idx>\d+|\*)\])?$', part)
                            if not m:
                                # 非标准片段，尝试作为字典键直接取
                                if isinstance(current, dict):
                                    current = current.get(part)
                                else:
                                    current = None
                                continue

                            key = m.group('key')
                            idx = m.group('idx')

                            if key:
                                if isinstance(current, dict):
                                    current = current.get(key)
                                else:
                                    current = None
                                    break

                            if idx is not None:
                                if idx == '*':
                                    # 通配符，展开所有元素并继续对剩余路径取值
                                    if not isinstance(current, list):
                                        current = None
                                        break
                                    rest = parts[parts.index(part) + 1:]
                                    results = []
                                    for el in current:
                                        sub_path = '.'.join(rest)
                                        if sub_path:
                                            # 递归取剩余路径（简单实现：仅支持单层）
                                            tmp = el
                                            for sub in rest:
                                                if tmp is None:
                                                    break
                                                sm = re.match(r'^(?P<k>[^\[]+)?(?:\[(?P<i>\d+|\*)\])?$', sub)
                                                if not sm:
                                                    tmp = tmp.get(sub) if isinstance(tmp, dict) else None
                                                    continue
                                                kk = sm.group('k')
                                                ii = sm.group('i')
                                                if kk and isinstance(tmp, dict):
                                                    tmp = tmp.get(kk)
                                                if ii is not None and isinstance(tmp, list):
                                                    if ii == '*':
                                                        # 扁平化
                                                        for t in tmp:
                                                            results.append(t)
                                                    else:
                                                        ii_int = int(ii)
                                                        if 0 <= ii_int < len(tmp):
                                                            results.append(tmp[ii_int])
                                            if tmp is not None and not isinstance(tmp, list):
                                                results.append(tmp)
                                    value = results if results else None
                                    break
                                else:
                                    # 索引取值
                                    if isinstance(current, list):
                                        idx_int = int(idx)
                                        if 0 <= idx_int < len(current):
                                            current = current[idx_int]
                                        else:
                                            current = None
                                    else:
                                        current = None
                            # continue loop
                        else:
                            # loop exhausted normally
                            value = current

                # 最终值为空时使用默认值
                if value is None and default is not None:
                    value = default

                # 写入 variables
                variables[var_name] = value
                allure.attach(str(value), name=f"提取变量: {var_name}", attachment_type=allure.attachment_type.TEXT)
                logger.info(f"提取变量 {var_name} = {value}")

            except Exception as e:
                logger.error(f"提取变量失败: {item}, 错误: {e}")
                allure.attach(str(e), name="提取变量错误", attachment_type=allure.attachment_type.TEXT)


# ==================== 主执行函数 ====================
def execute_test_case(case: Dict[str, Any], api_client, db, variables: Dict[str, Any], retry_config: Dict[str, Any] = None) -> None:
    """完整执行测试用例，所有关键步骤写入 Allure 报告"""
    logger.info(f"开始测试用例: {case.get('title', '未知')}")

    # 设置用例标题（用例ID + 标题）
    case_title = f"{case.get('case_id', '未知')} | {case.get('title', '未命名用例')}"
    allure.dynamic.title(case_title)
    allure.dynamic.description(f"用例ID: {case.get('case_id', '未知')}  |  描述: {case.get('description', '无')}")

    # 步骤1：合并变量
    with allure.step("1. 合并测试变量（全局变量 + 用例私有变量）"):
        if 'variables' in case and isinstance(case['variables'], dict):
            merged_vars = {**variables, **case['variables']}
            logger.info(f"合并用例私有变量: {case['variables']}")
        else:
            merged_vars = variables.copy()
        variables.clear()
        variables.update(merged_vars)
        logger.info(f"最终使用的 variables: {variables}")
        allure.attach(str(variables), name="最终 variables", attachment_type=allure.attachment_type.TEXT)

    # 步骤2：第一次变量替换
    with allure.step("2. 第一次变量替换（使用已有变量替换请求参数、SQL 中的已知占位符）"):
        case = replace_placeholders(case, variables)
        logger.info(f"第一次替换后的请求参数: {case.get('params', {})}")
        sql_display = _get_sql_display(case)
        logger.info(f"第一次替换后的 SQL: {sql_display}")
        allure.attach(
            f"请求参数: {case.get('params', {})}\nSQL: {sql_display}",
            name="第一次替换后数据",
            attachment_type=allure.attachment_type.TEXT
        )

    # 保存步骤2之后的 case 和 variables 状态，用于重试时恢复
    case_after_first_replace = copy.deepcopy(case)
    vars_after_first_replace = variables.copy()

    # 获取重试配置
    if retry_config is None:
        retry_config = {}
    max_attempts = retry_config.get('max_attempts', 1)
    interval_seconds = retry_config.get('interval_seconds', 2)
    error_keywords = retry_config.get('error_keywords', [])
    if not error_keywords and 'error_keyword' in retry_config:
        error_keywords = [retry_config['error_keyword']]

    for attempt in range(1, max_attempts + 1):
        logger.info(f"========== 第 {attempt}/{max_attempts} 次执行用例 ==========")
        if max_attempts > 1:
            allure.attach(f"第 {attempt}/{max_attempts} 次执行", name="重试次数", attachment_type=allure.attachment_type.TEXT)

        # 恢复 case 和 variables 到步骤2之后的状态
        case = copy.deepcopy(case_after_first_replace)
        variables.clear()
        variables.update(vars_after_first_replace)

        # 步骤3：处理 SQL 动态数据
        process_dynamic_data(case, db, variables)

        # SQL 结果聚合摘要（便于在报告中一览所有数据库变量）
        if 'sql' in case:
            _attach_sql_vars_summary(variables)

        # 步骤4：第二次变量替换
        with allure.step("3. 第二次变量替换（使用包含数据库结果的完整 variables 替换所有剩余占位符）"):
            case = replace_placeholders(case, variables)
            logger.info(f"最终替换后的请求参数: {case.get('params', {})}")
            sql_display_final = _get_sql_display(case)
            logger.info(f"最终替换后的 SQL: {sql_display_final}")
            allure.attach(
                f"请求参数: {case.get('params', {})}\nSQL: {sql_display_final}",
                name="最终替换后数据",
                attachment_type=allure.attachment_type.TEXT
            )

        # 步骤5：发送请求并验证响应
        with allure.step(f"4. 发送 HTTP {case.get('method', 'POST').upper()} 请求并验证响应"):
            method = case.get('method', 'POST').upper()
            endpoint = case.get('endpoint', '')
            # 初始化变量
            params = case.get('params', {})  # URL 查询参数
            body_data = case.get('json', {})  # 默认请求体数据

            # —— 请求概览（聚合 method/endpoint/params/body 为结构化附件）——
            _attach_request_overview(method, endpoint, params, body_data)

            # 判断是否为 form-urlencoded 格式
            body_type = case.get('body_type', 'json')  # 默认为 json
            if method == 'GET':
                allure.attach(json.dumps(params, ensure_ascii=False, indent=2), name="请求参数 (Query)", attachment_type=allure.attachment_type.JSON)
                resp = api_client.get(endpoint, params=params)
            else:
                if body_type == 'form-urlencoded':
                    import urllib.parse
                    encoded_data = urllib.parse.urlencode(body_data)
                    allure.attach(
                        urllib.parse.unquote(encoded_data),
                        name="请求体 (Form-UrlEncoded)",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    resp = api_client.post(endpoint, data=encoded_data, params=params)
                else:
                    allure.attach(json.dumps(body_data, ensure_ascii=False, indent=2), name="请求体 (JSON)", attachment_type=allure.attachment_type.JSON)
                    if body_data:
                        resp = api_client.post(endpoint, json=body_data, params=params)
                    else:
                        resp = api_client.post(endpoint, params=params)

            logger.info(f"响应状态码: {resp.status_code}")
            allure.attach(str(resp.status_code), name="HTTP 状态码", attachment_type=allure.attachment_type.TEXT)

            response_data = resp.json()
            response_str = json.dumps(response_data, ensure_ascii=False)[:5000]
            allure.attach(response_str, name="完整响应体", attachment_type=allure.attachment_type.JSON)
            logger.info(f"解析后的 JSON 摘要: {response_str[:200]}...")

            # —— 响应摘要（提取 data 层关键字段）——
            _attach_response_summary(response_data)

            # 检查响应是否为可重试的错误（仅在配置了 error_keywords 时）
            if error_keywords and response_data.get('businessSuccess') is False:
                error_msg = response_data.get('errorMessage', '') or ''
                # 动态替换错误关键词中的占位符（如 {name}、{price}）
                dynamic_keywords = []
                for kw in error_keywords:
                    try:
                        formatted_kw = kw.format(**variables)
                        dynamic_keywords.append(formatted_kw)
                    except (KeyError, ValueError):
                        # 如果占位符无法替换，保持原样（支持部分匹配）
                        dynamic_keywords.append(kw)

                is_retryable_error = any(keyword in error_msg for keyword in dynamic_keywords)

                if is_retryable_error:
                    logger.warning(f"第 {attempt} 次执行遇到可重试错误: {error_msg}")
                    allure.attach(
                        f"错误消息: {error_msg}\n匹配关键词: {dynamic_keywords}",
                        name=f"第 {attempt} 次 - 可重试错误详情",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    if attempt < max_attempts:
                        logger.info(f"等待 {interval_seconds} 秒后重试...")
                        time.sleep(interval_seconds)
                        continue  # 重新执行步骤3-5，获取新的数据库数据
                    else:
                        logger.warning(f"已达最大重试次数 {max_attempts}，按最后一次响应进行断言")
                        allure.attach(
                            f"已达最大重试次数 {max_attempts}",
                            name="重试耗尽",
                            attachment_type=allure.attachment_type.TEXT
                        )
                        # 继续执行断言（预期会失败）

            # ==================== 业务错误容错验证 ====================
            # 当 API 返回 businessSuccess=false（如"正在提交中"），但操作可能已成功处理时，
            # 通过 post_sql 验证数据库状态来判断测试是否通过。
            if (case.get('verify_on_business_error')
                    and response_data.get('businessSuccess') is False):
                error_msg = response_data.get('errorMessage', '') or ''
                logger.warning(f"API 返回业务失败: {error_msg}，尝试通过 post_sql 容错验证")
                allure.attach(
                    f"API 错误: {error_msg}\n策略: 通过 post_sql 验证数据库状态",
                    name="业务错误容错验证",
                    attachment_type=allure.attachment_type.TEXT
                )
                try:
                    process_post_operations(case, db, variables)
                    # post_sql 通过 → 操作已成功，测试通过
                    logger.info(f"业务错误容错验证通过（操作已成功）: {error_msg}")
                    allure.attach(
                        "post_sql 验证通过，确认操作已成功处理",
                        name="容错验证结果",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    break
                except AssertionError as e:
                    allure.attach(
                        f"容错验证失败: {e}",
                        name="容错验证失败",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    raise  # 重新抛出，测试失败

            # 执行断言验证
            assert_status_code(resp.status_code, case['expected_status'])
            validate_response(case, response_data, variables)

            # 从响应中提取变量（用于步骤间数据传递，必须在后置 SQL 之前执行）
            _extract_response_vars(response_data, case.get('extract_vars'), variables)

            # 执行后置操作（如 SQL 数据校验，可使用 extract_vars 提取的变量）
            process_post_operations(case, db, variables)

            break  # 断言通过则跳出循环

    logger.info(f"测试通过: {case['case_id']} - {case['title']}")


def get_case_by_id(case_list: List[Dict[str, Any]], case_id: str) -> Dict[str, Any]:
    """
    根据 case_id 从用例列表中获取测试用例数据。
    该函数用于测试框架中，当所有用例数据已通过 YAML 加载为列表后，
    可依据用例编号快速定位具体用例，避免重复遍历和手动判断。
    """
    for case in case_list:
        if case.get('case_id') == case_id:
            return case
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")

# 在接口请求和断言完成后执行
def process_post_operations(case: Dict[str, Any], db, variables: Dict[str, Any]) -> None:
    """
    处理用例中的后置操作，如 post_sql（用于验证数据库状态）。
    支持单个 SQL 或 SQL 列表。
    """
    if 'post_sql' not in case:
        return

    post_sql_configs = case['post_sql']
    if not isinstance(post_sql_configs, list):
        post_sql_configs = [post_sql_configs]

    with allure.step("执行后置 SQL 验证"):
        for idx, sql_config in enumerate(post_sql_configs):
            step_suffix = f" (步骤 {idx+1}/{len(post_sql_configs)})" if len(post_sql_configs) > 1 else ""
            with allure.step(f"后置 SQL 验证{step_suffix}"):
                # 替换变量
                sql_config_replaced = replace_placeholders(sql_config, variables)
                allure.attach(sql_config_replaced.get('query', ''), name=f"后置 SQL{step_suffix}", attachment_type=allure.attachment_type.TEXT)

                # 执行 SQL（复用 execute_sql 逻辑）
                result = execute_sql(db, sql_config_replaced)

                # 获取期望值
                expected_value = sql_config_replaced.get('expected_value')
                expected_operator = sql_config_replaced.get('operator', '==')
                # 如果配置了 expected_value，则进行断言
                if expected_value is not None:
                    # 支持占位符替换
                    if isinstance(expected_value, str) and '${' in expected_value:
                        expected_value = replace_placeholders(expected_value, variables)

                    # 处理可能的多行结果
                    if 'columns' in sql_config_replaced:
                        # 多字段返回，result 是 dict 或 list[dict]
                        for key, exp_val in expected_value.items():
                            actual_val = result.get(key) if isinstance(result, dict) else None
                            # 使用 validate 函数进行断言
                            validate(actual_val, expected_operator, exp_val, path=f"post_sql[{idx}].{key}")
                    elif 'column' in sql_config_replaced:
                        # 单字段返回
                        actual_val = result
                        validate(actual_val, expected_operator, expected_value, path=f"post_sql[{idx}]")
                    else:
                        # 返回整行，期望值应为字典
                        if isinstance(expected_value, dict):
                            for key, exp_val in expected_value.items():
                                actual_val = result.get(key) if isinstance(result, dict) else None
                                validate(actual_val, expected_operator, exp_val, path=f"post_sql[{idx}].{key}")
                        else:
                            # 直接比较整个结果
                            validate(result, expected_operator, expected_value, path=f"post_sql[{idx}]")
                    logger.info(f"后置 SQL 断言通过: {expected_value}")
                else:
                    # 如果没有期望值，只记录结果
                    allure.attach(str(result), name=f"后置 SQL 结果{step_suffix}", attachment_type=allure.attachment_type.TEXT)