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
    """智能查找 YAML 文件"""
    def _debug(msg):
        if debug:
            print(f"[DEBUG] {msg}")

    file_path = Path(filename)
    if file_path.is_absolute():
        _debug(f"绝对路径: {file_path}")
        return file_path if file_path.exists() else None

    try:
        current_dir = Path(__file__).resolve().parent
        print("当前路径：",current_dir)
    except NameError:
        current_dir = Path.cwd()
    project_root = _find_project_root(current_dir)

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
            _debug(f"找到文件: {loc}")
            return loc

    # 递归搜索（深度≤4）
    for depth in range(1, 5):
        for base in [project_root] + list(project_root.parents[:depth]):
            found = list(base.rglob(filename))
            if found:
                _debug(f"递归找到: {found[0]}")
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
    print("data:",data)
    if data_key is None:
        return data
    return data.get(data_key, [])


def clear_file_cache():
    global _FILE_CACHE
    _FILE_CACHE.clear()

def get_global_variables(data_file: str, debug: bool = True) -> Dict[str, Any]:
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