#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速启动脚本
帮助用户一键完成环境配置和依赖安装
"""
import os
import sys
import subprocess
from pathlib import Path


def print_step(step_num: int, total_steps: int, message: str):
    """打印步骤信息"""
    print(f"\n{'='*60}")
    print(f"步骤 {step_num}/{total_steps}: {message}")
    print(f"{'='*60}")


def check_python_version():
    """检查 Python 版本"""
    print_step(1, 5, "检查 Python 版本")
    
    if sys.version_info < (3, 8):
        print("Python 版本过低，需要 3.8 或更高版本")
        print(f"当前版本: {sys.version}")
        sys.exit(1)
    
    print(f"Python 版本: {sys.version}")


def create_env_file():
    """创建 .env 文件"""
    print_step(2, 5, "创建环境变量配置文件")
    
    env_file = Path(__file__).parent / '.env'
    env_example = Path(__file__).parent / '.env.example'
    
    if env_file.exists():
        print(".env 文件已存在")
        print(f"文件路径: {env_file}")
        print("\n请确保 .env 文件中已填入真实配置")
        return
    
    if not env_example.exists():
        print("未找到 .env.example 模板文件")
        sys.exit(1)
    
    # 复制模板
    import shutil
    shutil.copy(env_example, env_file)
    
    print("已创建 .env 文件")
    print(f"文件路径: {env_file}")
    print("\n请编辑 .env 文件，填入以下配置：")
    print("   - DB_PASSWORD: 数据库密码")
    print("   - WECHAT_WEBHOOK: 企业微信 Webhook（可选）")
    print("\n使用编辑器打开：")
    print(f"   Windows: notepad {env_file}")
    print(f"   Linux/Mac: vim {env_file}")
    
    # 询问是否继续
    choice = input("\n是否已完成配置？(y/n): ").strip().lower()
    if choice != 'y':
        print("请先编辑 .env 文件，然后重新运行此脚本")
        sys.exit(0)


def install_dependencies():
    """安装依赖"""
    print_step(3, 5, "安装依赖包")
    
    # 安装运行依赖
    print("\n安装运行依赖...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        cwd=Path(__file__).parent
    )
    
    if result.returncode != 0:
        print("运行依赖安装失败")
        sys.exit(1)
    
    print("运行依赖安装成功")
    
    # 询问是否安装开发依赖
    choice = input("\n是否安装开发依赖（black, flake8, mypy 等）？(y/n): ").strip().lower()
    if choice == 'y':
        print("\n安装开发依赖...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"],
            cwd=Path(__file__).parent
        )
        
        if result.returncode != 0:
            print("开发依赖安装失败，但不影响测试运行")
        else:
            print("开发依赖安装成功")


def setup_pre_commit():
    """设置 Pre-commit"""
    print_step(4, 5, "配置 Pre-commit 钩子")
    
    pre_commit_config = Path(__file__).parent / '.pre-commit-config.yaml'
    
    if not pre_commit_config.exists():
        print(" 未找到 .pre-commit-config.yaml，跳过 Pre-commit 配置")
        return
    
    # 检查是否已安装 pre-commit
    try:
        result = subprocess.run(
            ["pre-commit", "--version"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print("未安装 pre-commit，跳过配置")
            print("   安装命令: pip install pre-commit")
            return
        
        print(f"Pre-commit 已安装: {result.stdout.strip()}")
        
    except FileNotFoundError:
        print("未安装 pre-commit，跳过配置")
        return
    
    # 询问是否安装钩子
    choice = input("\n是否安装 Pre-commit 钩子？(y/n): ").strip().lower()
    if choice == 'y':
        print("\n安装 Pre-commit 钩子...")
        result = subprocess.run(
            ["pre-commit", "install"],
            cwd=Path(__file__).parent
        )
        
        if result.returncode == 0:
            print("Pre-commit 钩子安装成功")
            print("   以后每次 git commit 时会自动运行代码质量检查")
        else:
            print("Pre-commit 钩子安装失败")


def verify_installation():
    """验证安装"""
    print_step(5, 5, "验证安装")
    
    # 检查必要模块
    print("\n检查必要模块...")
    
    try:
        import dotenv
        print("python-dotenv")
    except ImportError:
        print(" python-dotenv 未安装")
        return False
    
    try:
        import yaml
        print(" PyYAML")
    except ImportError:
        print(" PyYAML 未安装")
        return False
    
    try:
        import pytest
        print(" pytest")
    except ImportError:
        print(" pytest 未安装")
        return False
    
    # 检查配置文件
    print("\n 检查配置文件...")
    
    env_file = Path(__file__).parent / '.env'
    if not env_file.exists():
        print(" .env 文件不存在")
        return False
    
    print(" .env 文件存在")
    
    # 检查环境变量
    from dotenv import load_dotenv
    load_dotenv(env_file)
    
    db_password = os.getenv("DB_PASSWORD")
    if not db_password:
        print(" DB_PASSWORD 未配置")
        print("   请编辑 .env 文件，填入数据库密码")
        return False
    
    print(" DB_PASSWORD 已配置")
    
    return True


def print_success_message():
    """打印成功信息"""
    print("\n" + "="*60)
    print(" 恭喜！环境配置完成！")
    print("="*60)
    
    print("\n 后续步骤：")
    print("1. 运行测试:")
    print("   python run.py")
    print("\n2. 运行冒烟测试:")
    print("   python run.py -m smoke")
    print("\n3. 查看帮助:")
    print("   python run.py --help")
    
    print("\n 文档：")
    print("   - 迁移指南: docs/MIGRATION_GUIDE.md")
    print("   - 代码质量指南: docs/CODE_QUALITY_GUIDE.md")
    print("   - 优化总结: docs/OPTIMIZATION_SUMMARY.md")
    
    print("\n 提示：")
    print("   - 使用 BaseAPITest 基类可以简化测试代码")
    print("   - 参考 testcases/api/order/test_query_order_api_example.py")
    
    print("\n" + "="*60)


def main():
    """主函数"""
    print("\n" + "="*60)
    print("接口自动化测试框架 - 快速启动")
    print("="*60)
    
    # 切换到项目根目录
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # 执行配置步骤
    check_python_version()
    create_env_file()
    install_dependencies()
    setup_pre_commit()
    
    # 验证安装
    if verify_installation():
        print_success_message()
    else:
        print("\n 验证失败，请检查上述错误并修复")
        print("   修复后重新运行此脚本: python setup.py")
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n 用户中断，配置未完成")
        sys.exit(1)
    except Exception as e:
        print(f"\n 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
