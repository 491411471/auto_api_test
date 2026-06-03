# utils/data_loader.py
import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

_FILE_CACHE = {}


def _find_project_root(start_path: Optional[Path] = None, markers: List[str] = None) -> Path:
    if markers is None:
        markers = ['data', '.git', 'pyproject.toml', 'requirements.txt', 'pytest.ini']
    if start_path is None:
        start_path = Path(__file__).resolve().parent
    current = start_path.resolve()
    for parent in [current] + list(current.parents):
        for marker in markers:
            if (parent / marker).exists():
                return parent
    return current.parent.parent


def _find_file_smart(filename: str, debug: bool = False) -> Optional[Path]:
    """智能查找 YAML 文件（增强版 - 支持新旧路径）"""
    def _debug(msg):
        if debug:
            print(f"[DEBUG] {msg}")

    file_path = Path(filename)
    if file_path.is_absolute():
        _debug(f"绝对路径: {file_path}")
        return file_path if file_path.exists() else None

    try:
        current_dir = Path(__file__).resolve().parent
    except NameError:
        current_dir = Path.cwd()
    
    project_root = _find_project_root(current_dir)

    # 【新增】定义新旧路径映射（优先级：新路径 > 旧路径）
    path_mappings = {
        'data/api/order/': 'data/merchant/api/order/',
        'data/api/product_management/': 'data/merchant/api/product/',
        'data/api/post_lease_management/': 'data/merchant/api/post_lease/',
        'data/scenario/order/': 'data/merchant/scenario/order/',
        'data/scenario/product/': 'data/merchant/scenario/product/',
        'data/scenario/contract-lifecycle/': 'data/merchant/scenario/contract-lifecycle/',
        'data/scenario/inventory/': 'data/common/inventory/',
    }

    # 【新增】策略1：尝试新路径（如果文件已迁移）
    for old_prefix, new_prefix in path_mappings.items():
        if old_prefix in filename:
            new_filename = filename.replace(old_prefix, new_prefix)
            new_path = project_root / new_filename
            if new_path.exists():
                _debug(f"[新路径] 找到: {new_path}")
                return new_path

    # 【原有】策略2：标准搜索位置
    search_locations = [
        current_dir / filename,
        current_dir / 'data' / filename,
        current_dir.parent / filename,
        current_dir.parent / 'data' / filename,
        current_dir.parent.parent / filename,
        current_dir.parent.parent / 'data' / filename,
        Path.cwd() / filename,
        Path.cwd() / 'data' / filename,
        project_root / filename,
        project_root / 'data' / filename,
    ]

    # 添加环境变量路径
    if os.environ.get('PROJECT_ROOT'):
        search_locations.append(Path(os.environ['PROJECT_ROOT']) / filename)
    if os.environ.get('DATA_DIR'):
        search_locations.append(Path(os.environ['DATA_DIR']) / filename)

    for loc in search_locations:
        if loc and loc.exists():
            _debug(f"[标准路径] 找到: {loc}")
            return loc

    # 【原有】策略3：递归搜索（深度≤5）
    for depth in range(1, 6):
        for base in [project_root] + list(project_root.parents[:depth]):
            found = list(base.rglob(filename))
            if found:
                _debug(f"[递归搜索] 找到: {found[0]}")
                return found[0]
    
    # 【新增】策略4：路径归一化搜索（兼容硬编码相对路径）
    if '/' in filename or '\\' in filename:
        # 归一化路径：移除多余的 ../ 和分隔符
        normalized = filename.replace('\\', '/')
        while '/../../' in normalized:
            normalized = normalized.replace('/../../', '/')
        normalized = normalized.lstrip('./')
        
        normalized_path = project_root / normalized
        if normalized_path.exists():
            _debug(f"[归一化路径] 找到: {normalized_path}")
            return normalized_path
        
        # 仅用文件名搜索（最后手段）
        simple_filename = Path(filename).name
        _debug(f"[文件名搜索] 尝试: {simple_filename}")
        for base in [project_root] + list(project_root.parents[:2]):
            found = list(base.rglob(simple_filename))
            if found:
                _debug(f"[文件名搜索] 找到: {found[0]}")
                return found[0]

    _debug(f"未找到文件: {filename}")
    return None


def _load_yaml_cached(file_path: Union[str, Path], use_cache: bool = True, debug: bool = False) -> Dict[str, Any]:
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"YAML 文件不存在: {path}")

    if use_cache:
        cache_key = f"{path}:{path.stat().st_mtime}"
        if cache_key in _FILE_CACHE:
            if debug:
                print(f"[DEBUG] 从缓存加载: {path}")
            return _FILE_CACHE[cache_key]

    for encoding in ['utf-8-sig', 'utf-8', 'gbk', 'latin-1']:
        try:
            with open(path, 'r', encoding=encoding) as f:
                data = yaml.safe_load(f) or {}
            if debug:
                print(f"[DEBUG] 使用编码 {encoding} 加载: {path}")
            break
        except UnicodeDecodeError:
            continue
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 解析失败 ({path}): {e}")
    else:
        raise UnicodeDecodeError(f"无法解码文件: {path}")

    if use_cache:
        cache_key = f"{path}:{path.stat().st_mtime}"
        _FILE_CACHE[cache_key] = data
    return data


def get_test_data(data_file: str, data_key: str = None, debug: bool = False) -> Union[Dict[str, Any], List[Any]]:
    """智能加载测试数据，cache 默认开启"""
    file_path = _find_file_smart(data_file, debug)
    if file_path is None:
        print(f"警告: 无法找到 YAML 文件: {data_file}")
        return [] if data_key else {}
    data = _load_yaml_cached(file_path, debug=debug)
    if debug:
        print(f"[DEBUG] 已加载: {file_path}")
    if data_key is None:
        return data
    return data.get(data_key, [])


def clear_file_cache():
    global _FILE_CACHE
    _FILE_CACHE.clear()

def get_global_variables(data_file: str, debug: bool = False) -> Dict[str, Any]:
    """
    智能加载 YAML 文件中的顶层 variables 字段
    返回字典，若不存在则返回空字典
    debug：当 debug=True 时，函数内部的 _debug(msg) 会通过 print 输出信息
    """
    # 查找yaml文件路径
    file_path = _find_file_smart(data_file, debug)
    if file_path is None:
        if debug:
            print(f"警告: 无法找到 YAML 文件: {data_file}")
        return {}
    data = _load_yaml_cached(file_path, debug=debug)
    return data.get('variables', {})