# 闲鱼API客户端配置说明

## 概述
本次优化将闲鱼店铺的专用token从YAML测试数据文件统一迁移到 `settings.yaml` 配置文件中，并通过 `conftest.py` 创建独立的fixture。

## 配置文件说明

### 1. settings.yaml (统一配置)
**路径**: `config/settings.yaml`

在 `merchant` 终端配置中增加了 `xianyu_token` 字段：

```yaml
environments:
  test:
    merchant:
      auth_type: "api_token"
      auth_config:
        key: "token"
        value: "kumgjkgd8ck4srfm9lfzuzqaxedldvjx"
        xianyu_token: "test_xianyu_token_value_here"  # 闲鱼店铺专用token
      timeout: 15
      max_retries: 3
      request_interval: 3
```

### 2. conftest.py (Fixture定义)
**路径**: `testcases/conftest.py`

新增了 `xianyu_api_client` fixture：

```python
@pytest.fixture(scope="session")
def xianyu_api_client():
    """闲鱼店铺 API 客户端（使用 merchant 配置中的 xianyu_token）"""
    # 获取商家端配置
    merchant_cfg = config_manager.get_api_client_config(endpoint='merchant')
    
    # 从配置中获取闲鱼专用token
    xianyu_token = merchant_cfg.get('auth_config', {}).get('xianyu_token')
    
    if not xianyu_token:
        raise ValueError("商家端配置中未找到 xianyu_token，请在 settings.yaml 中配置")
    
    # 使用闲鱼token创建独立的API客户端
    client = APIClient(
        base_url=merchant_cfg['base_url'],
        auth_type='bearer',
        auth_config={'token': xianyu_token},
        timeout=merchant_cfg.get('timeout', 15),
        max_retries=merchant_cfg.get('max_retries', 3),
        request_interval=merchant_cfg.get('request_interval', 1.0)
    )
    logger.info(f"闲鱼店铺 API 客户端初始化完成 (token: {xianyu_token[:10]}...)")
    yield client
    logger.info("闲鱼店铺 API 客户端关闭")
```

### 3. 测试文件使用方式
**路径**: `testcases/scenario/product/test_xianyu_product_create.py`

在测试方法中直接使用 `xianyu_api_client` fixture：

```python
@allure.title("新建闲鱼商品-完整流程验证")
def test_create_xianyu_product_success(self, xianyu_api_client, db, admin_api_client):
    project_root = Path(__file__).resolve().parent.parent.parent.parent

    # 第一阶段：创建闲鱼商品（使用闲鱼token）
    with allure.step("阶段一：创建闲鱼商品"):
        product_id_db = self._create_xianyu_product(xianyu_api_client, db, project_root)

    # 第二阶段：审核商品（使用运营端token）
    with allure.step("阶段二：审核闲鱼商品"):
        self._audit_xianyu_product(admin_api_client, db, project_root, product_id_db)
```

## 架构优势

### 1. 配置集中管理
- ✅ 所有环境的闲鱼token统一在 `settings.yaml` 中管理
- ✅ 支持测试环境和生产环境使用不同的token
- ✅ 避免token散落在多个YAML文件中

### 2. 代码复用性
- ✅ `xianyu_api_client` fixture可在所有闲鱼相关测试中复用
- ✅ 无需在每个测试文件中重复创建客户端
- ✅ 统一处理请求间隔、重试等机制

### 3. 安全性提升
- ✅ Token集中管理，便于定期更换
- ✅ 日志中只显示token前10位，避免泄露
- ✅ 支持通过环境变量覆盖配置

### 4. 职责清晰
- ✅ `xianyu_api_client`: 闲鱼店铺接口（使用闲鱼token）
- ✅ `admin_api_client`: 运营端接口（使用运营端token）
- ✅ `merchant_api_client`: 商家端通用接口（使用商家端token）

## 使用示例

### 示例1：闲鱼商品创建测试
```python
def test_create_xianyu_product(self, xianyu_api_client, db):
    # 使用闲鱼token上传图片
    image_url = upload_test_image(xianyu_api_client, "/path/to/image.jpg")
    
    # 使用闲鱼token创建商品
    response = xianyu_api_client.post("/hzsx/xianyu/product/addXianYuProduct", json=payload)
```

### 示例2：多端协作测试
```python
def test_full_flow(self, xianyu_api_client, admin_api_client, db):
    # 1. 使用闲鱼token创建商品
    product_id = create_product(xianyu_api_client)
    
    # 2. 使用运营端token审核商品
    audit_product(admin_api_client, product_id)
```

## 环境切换

通过命令行参数切换环境时，会自动使用对应环境的闲鱼token：

```bash
# 使用测试环境的闲鱼token
pytest test_xianyu_product_create.py --env test

# 使用生产环境的闲鱼token
pytest test_xianyu_product_create.py --env prod
```

## 注意事项

1. **Token配置**: 确保在 `settings.yaml` 的每个环境中都配置了 `xianyu_token`
2. **权限控制**: 闲鱼token仅用于闲鱼相关接口，不要用于其他业务
3. **日志记录**: 日志中token会被截断显示，保护敏感信息
4. **会话复用**: `xianyu_api_client` 是 session 级别fixture，整个测试会话共享

## 迁移指南

如果之前在其他测试文件中手动创建了闲鱼客户端，可以按以下步骤迁移：

### Before (旧方式)
```python
def test_old_way(self, api_client):
    # 手动从YAML读取token
    yaml_path = "path/to/xianyu_product_create.yaml"
    with open(yaml_path) as f:
        yaml_config = yaml.safe_load(f)
    xianyu_token = yaml_config['variables']['xianyu_token']
    
    # 手动创建客户端
    xianyu_api_client = APIClient(
        base_url=api_client.base_url,
        auth_type='bearer',
        auth_config={'token': xianyu_token}
    )
```

### After (新方式)
```python
def test_new_way(self, xianyu_api_client):
    # 直接使用fixture，无需手动创建
    response = xianyu_api_client.post("/hzsx/xianyu/product/addXianYuProduct", json=payload)
```

## 相关文件

- `config/settings.yaml` - 统一配置文件
- `testcases/conftest.py` - Fixture定义
- `common/api_client.py` - API客户端实现
- `common/config_manager.py` - 配置管理器
- `testcases/scenario/product/test_xianyu_product_create.py` - 闲鱼商品测试
