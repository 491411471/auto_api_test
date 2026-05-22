# Token失效问题 - 完整诊断与解决方案

## 🔴 问题现象

运行任何测试都报错：
```json
{"code": "LOGIN_INVALID", "errorMsg": "该账号在别处登录"}
```

**影响范围**：
- ❌ 商家端接口无法访问
- ❌ 闲鱼接口无法访问  
- ❌ 所有使用token的接口都失败

## 🔍 问题根源

### 原因1：Token被踢掉
**最可能的原因**：
1. 你在**浏览器**中登录了同一个账号
2. 或者在**其他设备/环境**中使用了同一个token
3. 平台实行**单点登录**，新登录会把旧session踢掉

### 原因2：Token过期
- Token有有效期（通常几小时到几天）
- 过期后需要重新获取

### 原因3：Token配置错误
- 测试环境和生产环境使用了相同的token
- Token复制不完整或错误

## ✅ 立即解决步骤

### 步骤1：运行诊断工具

```bash
cd D:\PythonProject\api_test
python diagnose_tokens.py
```

这会告诉你：
- 商家端token是否有效
- 运营端token是否有效
- 具体哪个token失效了

### 步骤2：重新获取Token

#### 商家端Token（merchant）

1. **打开浏览器**，访问：`https://test.llxzu.com`

2. **登录商家端账号**

3. **按F12** 打开开发者工具

4. **切换到 Network（网络）标签**

5. **刷新页面** 或进行任意操作

6. **点击任意API请求**（通常是 `.json` 或 `.api` 结尾）

7. **查看 Request Headers**：
   ```
   Request Headers:
     Content-Type: application/json
     token: kumgjkgd8ck4srfm9lfzuzqaxedldvjx  ← 复制这个值
   ```

8. **复制token值**

#### 运营端Token（admin）

1. **使用运营端账号登录**

2. **同样按F12查看Network**

3. **复制token值**

#### 闲鱼Token（xianyu）

1. **使用闲鱼店铺账号登录**

2. **按F12查看Network**

3. **复制token值**

### 步骤3：更新配置文件

编辑 `D:\PythonProject\api_test\config\settings.yaml`：

```yaml
test:
  merchant:
    auth_config:
      key: "token"
      value: "这里填入新的商家端token"        # ← 修改
      xianyu_token: "这里填入新的闲鱼token"  # ← 修改
  admin:
    auth_config:
      key: "token"
      value: "这里填入新的运营端token"        # ← 修改
```

### 步骤4：验证Token

```bash
python diagnose_tokens.py
```

确保输出显示：
```
商家端Token: ✅ 有效
运营端Token: ✅ 有效
```

### 步骤5：重新运行测试

```bash
# 测试订单查询
pytest testcases/api/order/test_query_order_api.py -v

# 测试闲鱼商品
pytest testcases/scenario/product/test_xianyu_product_create.py -v
```

## 📋 完整检查清单

更新token后，请确认：

- [ ] 商家端token已更新（从浏览器获取的新值）
- [ ] 运营端token已更新（从浏览器获取的新值）
- [ ] 闲鱼token已更新（从浏览器获取的新值）
- [ ] 三个token**互不相同**
- [ ] 测试环境和生产环境使用不同的token
- [ ] 运行 `diagnose_tokens.py` 全部通过
- [ ] 测试可以正常运行

## ⚠️ 重要注意事项

### 1. Token唯一性原则

```yaml
# ✅ 正确：三个token都不同
merchant:
  value: "token_abc123"           # 商家端
  xianyu_token: "token_xyz789"    # 闲鱼端
admin:
  value: "token_def456"           # 运营端

# ❌ 错误：token重复使用
merchant:
  value: "token_abc123"
  xianyu_token: "token_abc123"  # 与商家端相同！会冲突
```

### 2. 避免Token被踢

**登录规则**：
- ✅ 可以：在浏览器登录后查看Network获取token
- ❌ 不要：获取token后又在浏览器中继续操作
- ❌ 不要：在多个设备/浏览器同时登录同一账号
- ❌ 不要：在Postman等其他工具中使用同一token

**最佳实践**：
1. 登录 → 获取token → **立即关闭浏览器**
2. 或者：使用浏览器的**无痕模式**获取token
3. 获取token后**不要**再用浏览器访问该平台

### 3. Token有效期

- 测试环境token：通常几小时到1天
- 生产环境token：通常1-7天
- 过期后需要重新获取

### 4. 环境隔离

```yaml
# 测试环境和生产环境必须使用不同的token
test:
  merchant:
    value: "test_token_xxx"
prod:
  merchant:
    value: "prod_token_yyy"  # 必须是不同的token
```

## 🔧 进阶：自动化Token管理

### 方案1：Token刷新脚本（如果平台支持）

如果平台提供token刷新API，可以创建自动刷新脚本：

```python
# refresh_tokens.py
import requests

def refresh_token(base_url, refresh_token):
    """自动刷新token"""
    response = requests.post(f"{base_url}/auth/refresh", json={
        "refresh_token": refresh_token
    })
    return response.json().get('token')
```

### 方案2：Token过期检测

在测试前自动检测token是否有效：

```python
# conftest.py 中添加
@pytest.fixture(scope="session", autouse=True)
def validate_tokens(api_client, admin_api_client):
    """测试会话开始前验证所有token"""
    # 验证商家端token
    try:
        response = api_client.get("/hzsx/userInfo")
        if response.json().get('code') == 'LOGIN_INVALID':
            pytest.fail("商家端token已失效，请重新获取")
    except Exception as e:
        pytest.fail(f"验证商家端token失败: {e}")
    
    # 验证运营端token
    try:
        response = admin_api_client.get("/hzsx/userInfo")
        if response.json().get('code') == 'LOGIN_INVALID':
            pytest.fail("运营端token已失效，请重新获取")
    except Exception as e:
        pytest.fail(f"验证运营端token失败: {e}")
```

## 📞 常见问题

### Q1: 为什么每次都要重新获取token？
A: 平台的token有有效期，且实行单点登录。建议：
- 获取token后立即关闭浏览器
- 或者使用专门的测试账号

### Q2: 可以同时运行多个测试吗？
A: 可以，但要确保：
- 使用同一个token的测试不会互相冲突
- 不要在不同的pytest进程中使用同一token

### Q3: Token突然失效怎么办？
A: 检查：
1. 是否在浏览器中登录了同一账号
2. 是否在其他设备使用了同一token
3. Token是否过期

### Q4: 如何知道token是否快过期？
A: 观察响应中的警告信息，或者：
- 记录token获取时间
- 定期检查token有效性
- 运行 `diagnose_tokens.py`

### Q5: 能否延长token有效期？
A: 这取决于平台策略。可以：
- 联系平台管理员
- 查看是否有token刷新机制
- 使用refresh token自动刷新

## 📊 问题排查流程

```
出现 LOGIN_INVALID 错误
    ↓
运行 diagnose_tokens.py
    ↓
    ├─ 商家端token失效 → 重新登录商家端获取token
    ├─ 运营端token失效 → 重新登录运营端获取token
    └─ 都有效 → 检查是否有其他地方使用了同一token
    ↓
更新 settings.yaml
    ↓
再次运行 diagnose_tokens.py 验证
    ↓
运行测试
```

## 📝 相关文档

- `docs/闲鱼Token配置问题修复指南.md` - 闲鱼token专项说明
- `docs/闲鱼API客户端配置说明.md` - 闲鱼API客户端架构说明
- `diagnose_tokens.py` - Token诊断工具
- `test_xianyu_token.py` - 闲鱼token验证工具
