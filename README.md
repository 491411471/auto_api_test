# 完美接口自动化测试框架

##  特性一览
- 多环境一键切换 (dev/test/prod)
- 单接口 / 业务流程测试分离存放，分开执行
- 数据与代码完全解耦 (YAML)
- 支持 API Key、Bearer Token、Basic Auth
- 失败重试 + 详细日志 + Allure 炫酷报告
- 支持数据库校验 (MySQL)
- 并行执行加速回归
- **5 分钟上手**，零基础可用

## ⚡ 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt




python run.py                # 默认 test 环境
python run.py --env dev      # 切换 dev 环境
python run.py --api          # 只运行单接口用例
python run.py --scenario     # 只运行流程用例
python run.py -n 4           # 4 进程并行执行
python run.py -m smoke       # 只执行冒烟用例