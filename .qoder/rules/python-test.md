# Perfect API Test 项目协作规范

## 1. 核心协作原则（咱们一起遵守）
- **数据驱动**：所有测试数据放在 `data/` 目录下的 YAML 文件里，测试代码只负责读取和执行。
- **框架复用**：
  - **API 请求**：只用 `common.api_client.APIClient`。
  - **数据库**：只用 `common.database.DatabaseManager`。
  - **断言与变量**：只用 `common.test_helpers.execute_test_case` 执行，它会自动处理变量替换（`${}`）和断言。
- **禁止事项**：尽量别直接用 `requests`、`pymysql` 或原生 `assert`，交给框架处理。

## 2. 测试用例生成策略（分两种）

### A. 通用场景（参数化，单函数）
- **适用**：接口单一，仅参数不同（如不同状态查询）。
- **生成**：一个 YAML 文件 + 一个 `test_` 函数 + `@pytest.mark.parametrize`。

### B. 复杂场景（分步骤，多函数）
- **适用**：多接口串联、需数据库校验、依赖前序结果。
- **生成**：
  - **代码**：用 `class` 组织，每个步骤一个 `test_` 方法。
  - **顺序**：必须用 `@pytest.mark.order` 指定执行顺序。
  - **数据**：YAML 中每个步骤定义 `step_id`，通过 `variables` fixture 传递数据。
  - **清理**：在 `setup/teardown` 中清理测试数据。

## 3. 代码规范
- **命名**：
  - 文件：`test_<模块>.py`。
  - 类：`Test<业务场景>`（复杂场景用 Class，通用场景用 Function）。
  - 方法/函数：`test_<步骤描述>`。
- **Allure**：用 `@allure.feature` 和 `@allure.story` 组织报告层级。

## 4. 示例

### 通用场景（参数化）
python

@pytest.mark.parametrize("case", get_test_data("data/api/audit_add.yaml"))

def test_audit_add(case, api_client, db, variables):

execute_test_case(case, api_client, db, variables)

### 复杂场景（分步骤，Class 组织）
python

@allure.feature("租后管理")

@allure.story("仲裁合同全流程")

class TestAuditFlowComplex:

@pytest.mark.order(1)

def test_step1_submit(self, api_client, db, variables):

case = get_test_data("data/scenario/audit_flow.yaml", "step1_submit")

execute_test_case(case, api_client, db, variables)

## 5. YAML 数据规范（复杂场景）

yaml

step_id: "step1_submit"

title: "提交申请"

output_variables: ["log_id"]  # 产出变量

... 其他字段

step_id: "step2_audit"

title: "审核"

depends_on: ["step1_submit"]  # 依赖步骤

params:

id: "${log_id}"  # 使用上一步变量

... 其他字段