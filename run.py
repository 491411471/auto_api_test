#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# [OPTIMIZED] 增强执行入口：支持企业微信通知、结果统计、彩色输出
import argparse
import json
import os
import subprocess
import sys
import time
from config.config import HTTP_REPORT_BASE, WECHAT_WEBHOOK, WECHAT_USERID
from datetime import datetime
from utils.wechat_sender import send_wechat_report
from common.logger import logger
import pytest
from colorama import init, Fore, Style

init(autoreset=True)


def parse_allure_stats(allure_results_dir='reports/allure_results'):
    """从 Allure 的原始结果目录中读取统计信息（备用方案）"""
    summary_file = os.path.join(allure_results_dir, 'widgets', 'summary.json')
    color_print(f"summary:{summary_file}", 'cyan')
    if not os.path.exists(summary_file):
        return None
    with open(summary_file, 'r', encoding='utf-8') as f:
        summary_data = json.load(f)
    statistic = summary_data.get('statistic', {})
    color_print(f"statistic:{statistic}", 'cyan')
    return {
        'passed': statistic.get('passed', 0),
        'failed': statistic.get('failed', 0),
        'broken': statistic.get('broken', 0),
        'skipped': statistic.get('skipped', 0),
        'total': statistic.get('total', 0),
    }


def set_allure_language_to_zh(report_dir='reports/allure_html'):
    """最简单的 Allure 报告中文设置：向 index.html 注入语言切换脚本"""
    index_path = os.path.join(report_dir, 'index.html')
    if not os.path.exists(index_path):
        return
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()
    script = '''
<script>
    localStorage.setItem('ALLURE_REPORT_SETTINGS', JSON.stringify({language: 'zh', sidebarCollapsed: false}));
    console.log('Allure 报告已切换为中文');
</script>
'''
    if 'ALLURE_REPORT_SETTINGS' not in content:
        content = content.replace('</body>', f'{script}</body>')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(" Allure 报告已设置为中文界面")
    else:
        print(" Allure 报告已经是中文界面")


def _resolve_test_paths(api_only: bool, scenario_only: bool, endpoint: str = None) -> list:
    """根据测试类型和端点类型，解析实际的测试目录路径

    路径规则：testcases/{endpoint}/{api|scenario}
    若未指定 endpoint，默认扫描所有已知端点（merchant + admin）
    """
    base = 'testcases'
    # 端点列表：endpoint 指定时用单个，否则扫描所有已知端点
    endpoints = [endpoint] if endpoint else ['merchant', 'admin']
    # 测试类型：api / scenario / 两者皆选
    if api_only and not scenario_only:
        test_types = ['api']
    elif scenario_only and not api_only:
        test_types = ['scenario']
    else:
        test_types = ['api', 'scenario']

    paths = [f"{base}/{ep}/{tt}" for ep in endpoints for tt in test_types]
    # 过滤掉不存在的目录，避免 pytest 报路径错误
    valid_paths = [p for p in paths if os.path.isdir(p)]
    # 若所有目录都不存在，降级到 testcases 根目录（让 pytest 自行报错）
    return valid_paths if valid_paths else [base]


def color_print(message, color='white'):
    colors = {
        'green': Fore.GREEN, 'red': Fore.RED, 'blue': Fore.BLUE,
        'yellow': Fore.YELLOW, 'cyan': Fore.CYAN, 'magenta': Fore.MAGENTA,
        'white': Fore.WHITE
    }
    print(f"{colors.get(color, Fore.WHITE)}{message}{Style.RESET_ALL}")


def run_tests(env='test', endpoint=None, api_only=False, scenario_only=False, mark=None, keyword=None, parallel=None,
              send_notify=False):
    """执行测试，并可选择发送企业微信通知"""
    print("=" * 70)
    color_print("          ★ 接口自动化测试框架 ★", 'cyan')
    print("=" * 70)

    if env:
        os.environ["TEST_ENV"] = env
    if endpoint:
        os.environ["TEST_ENDPOINT"] = endpoint

    try:
        from common.config_manager import config_manager
        print(f"当前激活环境: {config_manager.current_env}, 终端: {config_manager.current_endpoint}")
        api_cfg = config_manager.get_api_client_config()
        print(f"使用 base_url: {api_cfg['base_url']}")
    except Exception as e:
        print(f"加载配置失败: {e}")

    # 确定测试路径（支持 merchant/admin 端点动态切换）
    test_paths = _resolve_test_paths(api_only, scenario_only, endpoint)

    # 创建报告目录
    os.makedirs('reports/allure_results', exist_ok=True)
    os.makedirs('logs', exist_ok=True)

    # 构建 pytest 命令（test_paths 始终为 list）
    pytest_args = test_paths + ['-v', '--alluredir=./reports/allure_results', '--clean-alluredir']
    pytest_args.append('--json-report')
    pytest_args.append('--json-report-file=reports/test_result.json')
    if mark:
        pytest_args.extend(['-m', mark])
    if keyword:
        pytest_args.extend(['-k', keyword])
    if parallel:
        pytest_args.extend(['-n', str(parallel)])

    color_print(f" 执行命令: pytest {' '.join(pytest_args)}", 'yellow')
    start_time = time.time()
    exit_code = pytest.main(pytest_args)
    elapsed = (time.time() - start_time) / 60

    # 生成 Allure HTML 报告
    print("\n 正在生成 Allure HTML 报告...")
    subprocess.run('allure generate ./reports/allure_results -o ./reports/allure_html --clean', shell=True)
    report_path = os.path.abspath('./reports/allure_html/index.html')
    print(f"\n 测试完成！报告已生成: file://{report_path}")

    # 将allure报告界面设置为中文
    set_allure_language_to_zh('reports/allure_html')

    # ---------- 准确读取 pytest-json-report 生成的统计信息 ----------
    json_report = 'reports/test_result.json'
    stats = {'total': 0, 'passed': 0, 'failed': 0, 'error': 0, 'skipped': 0, "elapsed": 0.0}
    if os.path.exists(json_report):
        try:
            with open(json_report, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # pytest-json-report 的标准结构：data['summary'] 中包含关键计数
            color_print(f" 已成功读取data: {data}", 'yellow')
            summary = data.get('summary', {})
            stats['total'] = summary.get('total', 0)
            stats['passed'] = summary.get('passed', 0)
            stats['failed'] = summary.get('failed', 0)
            stats['skipped'] = summary.get('skipped', 0)
            stats['elapsed'] = round(elapsed, 1)  # 保留一位小数
            # error 在 json-report 中通常对应 'error' 字段，表示用例执行过程中发生未捕获异常的数量
            stats['error'] = summary.get('error', 0)
            # 可选：记录 skipped, xfailed, xpassed 等扩展信息（暂不使用）
            color_print(" 已成功读取 pytest-json-report 统计信息", 'green')
        except Exception as e:
            color_print(f" 读取 JSON 报告失败：{e}，将尝试使用 Allure 统计", 'yellow')
            allure_stats = parse_allure_stats()
            if allure_stats:
                stats = allure_stats
                stats['error'] = stats.pop('broken', 0)  # 将 broken 映射为 error
            else:
                color_print(" 无法获取任何测试统计，请检查报告生成过程", 'red')
    else:
        color_print(f" 未找到 JSON 报告文件：{json_report}，尝试使用 Allure 统计", 'yellow')
        allure_stats = parse_allure_stats()
        if allure_stats:
            stats = allure_stats
            stats['error'] = stats.pop('broken', 0)
        else:
            color_print(" 无法获取任何测试统计，请确保 pytest 执行生成了报告", 'red')

    # 显示测试结果摘要
    print("\n" + "=" * 50)
    color_print(f"  执行耗时: {elapsed:.2f} （分钟)", 'cyan')
    if stats['total'] > 0:
        color_print(f" 总用例数: {stats['total']}", 'blue')
        color_print(f" 通过: {stats['passed']}", 'green')
        color_print(f" 失败: {stats['failed']}", 'red')
        color_print(f" 跳过: {stats['skipped']}", 'red')
        color_print(f" 错误: {stats['error']}", 'magenta')
        pass_rate = (stats['passed'] / stats['total']) * 100 if stats['total'] else 0
        color_print(f" 通过率: {pass_rate:.1f}%", 'yellow')
    else:
        color_print(" 未检测到任何测试用例，请检查测试路径或标记", 'red')
    print("=" * 50)

    # 发送企业微信通知（修正逻辑：send_notify=True 才发送）
    if send_notify and WECHAT_WEBHOOK:
        test_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        report_url = f"{HTTP_REPORT_BASE}allure_html/index.html"  # 需要配置外部可访问地址
        success = send_wechat_report(
            test_elapsed = stats['elapsed'],
            test_time=test_time_str,
            total_cases=stats['total'],
            report_path=report_url,
            passed=stats['passed'],
            failed=stats['failed'],
            skipped=stats['skipped'],
            error=stats['error'],
            webhook_url=WECHAT_WEBHOOK,
            wechat_userids=WECHAT_USERID
        )
        if success:
            color_print(" 企业微信通知发送成功", 'green')
        else:
            color_print(" 企业微信通知发送失败", 'red')
    elif send_notify and not WECHAT_WEBHOOK:
        color_print(" 未配置企业微信 Webhook，跳过通知发送", 'yellow')

    sys.exit(exit_code)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='增强版接口自动化测试框架')
    parser.add_argument('--env', default='test', help='环境，如 test/prod，覆盖配置文件')
    parser.add_argument('--endpoint', default=None, help='终端类型，如 merchant/admin，覆盖配置文件')
    parser.add_argument('--api', action='store_true', help='仅执行单接口测试')
    parser.add_argument('--scenario', action='store_true', help='仅执行业务流程测试')
    parser.add_argument('-m', '--mark', help='执行指定标记的用例')
    parser.add_argument('-k', '--keyword', help='按关键字过滤')
    parser.add_argument('-n', '--parallel', type=int, nargs='?', const='auto', help='并行执行')
    parser.add_argument('--no-notify', action='store_true', help='不发送企业微信通知')
    args = parser.parse_args()
    # 修正：--no-notify 时 send_notify=False
    send_notify = not args.no_notify
    run_tests(
        env=args.env,
        api_only=args.api,
        scenario_only=args.scenario,
        mark=args.mark,
        keyword=args.keyword,
        parallel=args.parallel,
        send_notify=send_notify
    )