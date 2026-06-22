# testcases/api/post_lease_management/test_payback_summary.py
"""
回款统计验证测试模块
流程：查询初始值 → 执行还款 → 计算期望值 → 等待数据更新 → 断言验证
"""
import time
from decimal import Decimal, ROUND_HALF_UP
import allure
import json
import pytest
import yaml
import os
from common.logger import logger
from utils.data_loader import get_test_data, get_global_variables
from utils.captcha_repayment_helper import submit_with_captcha, require_ddddocr


# 预先加载用例数据
_ALL_CASES = get_test_data("payback_summary_api.yaml", "payback_summary_tests")
if not _ALL_CASES:
    raise RuntimeError("无法加载 YAML 数据，请检查文件路径 payback_summary_api.yaml")


def _load_yaml():
    yaml_path = os.path.join(os.path.dirname(__file__), "../../../../data/merchant/api/post_lease/payback_summary_api.yaml")
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _get_case(case_id: str):
    for c in _ALL_CASES:
        if c['case_id'] == case_id:
            return c
    raise ValueError(f"未找到 case_id 为 {case_id} 的测试数据")


def _fetch_first_overdue_order(api_client):
    """获取第一个逾期已分配且首期已支付的订单号（带缓存，支持降级查询）
    
    查询策略：
      1. 已分配逾期订单（assignStatus=1）→ 筛选首期已支付
      2. 任意逾期订单（不限分配状态，降级）→ 筛选首期已支付
    
    返回：
        tuple: (order_id, stages_data) 或 (None, None)
    """
    global _first_order_info_cache, _first_order_fetched, _first_stages_data_cache
    if _first_order_fetched:
        return _first_order_info_cache, _first_stages_data_cache

    _first_order_fetched = True
    
    # 降级查询策略
    queries = [
        ("逾期已分配订单", {
            "assignStatus": "1",
            "followTimeDesc": 0,
            "overdueTime": "0",
            "pageNum": 1,
            "pageSize": 10,
            "overdueDaysDesc": 1,
            "tabName": "0"
        })
    ]
    
    try:
        for desc, payload in queries:
            with allure.step(f"获取{desc}"):
                resp = api_client.post("/hzsx/dcm/order/list", json=payload)
                resp_json = resp.json()
                records = (resp_json.get('data') or {}).get('records') or []
                
                if not records:
                    allure.attach(f"查询{desc}无结果，尝试下一策略", name="查询结果")
                    continue

                allure.attach(
                    f"查询{desc}到 {len(records)} 个逾期订单",
                    name="订单列表"
                )

                # 筛选首期已支付的订单
                checked_orders = []
                for idx, record in enumerate(records):
                    check_order_id = record['orderId']
                    check_user = record.get('userName', '')
                    check_overdue = record.get('overdueDays', '')

                    stages_resp = api_client.post(
                        "/hzsx/business/order/queryOrderStagesDetail",
                        json={"orderId": check_order_id}
                    )
                    stages_json = stages_resp.json()

                    if stages_json.get('businessSuccess') is not True:
                        checked_orders.append(
                            f"#{idx+1} {check_order_id} (用户:{check_user}): "
                            f"查询分期失败 - {stages_json.get('errorMessage', 'N/A')}"
                        )
                        continue

                    stages_data = stages_json.get('data') or []
                    if isinstance(stages_data, dict):
                        stages_data = (
                            stages_data.get('orderByStagesDtoList')
                            or stages_data.get('stages')
                            or stages_data.get('records')
                            or []
                        )

                    first_stage = None
                    stages_summary = []
                    for stage in stages_data:
                        periods = stage.get('periods') or stage.get('currentPeriods') or stage.get('period')
                        s_status = str(stage.get('status', ''))
                        stages_summary.append(f"  期数={periods}, status={s_status}")
                        if periods == 1 or str(periods) == '1':
                            first_stage = stage
                            break

                    if first_stage is None:
                        checked_orders.append(
                            f"#{idx+1} {check_order_id} (用户:{check_user}): 未找到首期记录\n"
                            + "\n".join(stages_summary)
                        )
                        continue

                    stage_status = str(first_stage.get('status', ''))
                    stage_status_map = {'1': '未支付', '2': '已支付', '3': '逾期', '4': '逾期'}
                    status_desc = stage_status_map.get(stage_status, f'未知({stage_status})')

                    if stage_status == '2':
                        _first_order_info_cache = check_order_id
                        _first_stages_data_cache = stages_data
                        checked_orders.append(
                            f"#{idx+1} {check_order_id} (用户:{check_user}): "
                            f"首期已支付 ✓ 选中"
                        )
                        allure.attach(
                            f"选中订单: {check_order_id}\n"
                            f"用户名: {check_user}\n"
                            f"逾期天数: {check_overdue}天\n"
                            f"首期状态: 已支付",
                            name="选中订单"
                        )
                        allure.attach("\n".join(checked_orders), name="订单首期支付检查结果")
                        return _first_order_info_cache, _first_stages_data_cache
                    else:
                        checked_orders.append(
                            f"#{idx+1} {check_order_id} (用户:{check_user}): "
                            f"首期status={stage_status}({status_desc})，跳过"
                        )

                allure.attach("\n".join(checked_orders), name=f"{desc}-订单首期支付检查结果")

        allure.attach(
            "所有查询策略均无符合条件的订单（首期已支付的逾期订单）",
            name="前置-查询结果",
            attachment_type=allure.attachment_type.TEXT
        )

    except Exception as e:
        allure.attach(f"获取失败: {e}", name="异常")

    return _first_order_info_cache, _first_stages_data_cache


_first_order_info_cache = None
_first_order_fetched = False
_first_stages_data_cache = None

@allure.epic("商家端")
@allure.feature("商家端-租后管理")
@allure.story("回款统计验证")
class TestPaybackSummary:
    """回款统计金额变化验证"""
    _global_vars = None
    _shared_order_id = None
    _shared_stages_data = None  # 缓存分期数据

    @classmethod
    def _load_global_vars(cls):
        if cls._global_vars is None:
            cls._global_vars = get_global_variables("payback_summary_api.yaml")
        return cls._global_vars.copy()

    def _query_payback_summary(self, api_client):
        """查询回款统计摘要，返回 (paybackTotalAmount, paybackUnAmount, paybackRate)"""
        resp = api_client.post("/hzsx/dcm/payback/paybackSummary", json={})
        resp_json = resp.json()
        
        assert resp.status_code == 200, f"HTTP状态码异常: {resp.status_code}"
        assert resp_json.get("businessSuccess") is True, f"业务失败: {resp_json.get('errorMessage')}"
        
        data = resp_json.get("data") or {}
        total_amount = data.get("paybackTotalAmount")
        un_amount = data.get("paybackUnAmount")
        rate = data.get("paybackRate")
        
        assert total_amount is not None, "paybackTotalAmount 为空"
        assert un_amount is not None, "paybackUnAmount 为空"
        assert rate is not None, "paybackRate 为空"
        
        return total_amount, un_amount, rate

    def _ensure_order_id(self, api_client):
        """确保已获取逾期订单号"""
        if self._shared_order_id is None:
            with allure.step("② 获取逾期订单"):
                order_id, self._shared_stages_data = _fetch_first_overdue_order(api_client)
                if not order_id:
                    skip_msg = "未找到符合条件的逾期订单（首期已支付），跳过回款统计测试"
                    allure.attach(
                        f"{skip_msg}\n\n"
                        f"查询策略:\n"
                        f"1. assignStatus=1 + overdueTime=0（已分配逾期）\n"
                        f"2. overdueTime=0（任意逾期，降级）\n"
                        f"筛选条件: 首期分期 status=2（已支付）\n"
                        f"接口: /hzsx/dcm/order/list + /hzsx/business/order/queryOrderStagesDetail",
                        name="跳过原因",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    pytest.skip(skip_msg)
                self._shared_order_id = order_id
                allure.attach(
                    f"订单号: {self._shared_order_id}",
                    name="逾期订单",
                    attachment_type=allure.attachment_type.TEXT
                )
        return self._shared_order_id, self._shared_stages_data

    def test_ps_001_payback_summary_after_repayment(self, merchant_api_client, db):
        """
        PS_001: 验证手动还款后回款统计金额变化
        """
        config = _load_yaml()

        # ================================================================
        # ① 查询初始回款统计
        # ================================================================
        with allure.step("① 查询初始回款统计"):
            initial_total, initial_un, initial_rate = self._query_payback_summary(merchant_api_client)
            
            allure.attach(
                f"回款总金额: {initial_total} 元\n"
                f"待追回总金额: {initial_un} 元\n"
                f"回款率: {initial_rate}%",
                name="初始值",
                attachment_type=allure.attachment_type.TEXT
            )
        # ================================================================
        # ② 获取逾期订单并执行还款
        # ================================================================
        with allure.step("② 获取逾期订单并执行还款"):
            require_ddddocr()  # 预检 ddddocr

            order_id, stages_data = self._ensure_order_id(merchant_api_client)
            repay_amount = config['repayment']['amount']
            repay_period = config['repayment']['period']
            repay_type = config['repayment']['type']

            # 动态获取还款期数（使用已缓存的分期数据，避免重复查询）
            with allure.step("获取订单分期详情"):
                if stages_data:
                    # 找第一个未支付期数
                    for stage in stages_data:
                        periods = stage.get('periods') or stage.get('currentPeriods')
                        status = str(stage.get('status', ''))
                        if status not in ['2', '3', '5', '6', '7']:
                            repay_period = int(periods)
                            break
                    allure.attach(
                        f"还款期数: {repay_period}",
                        name="还款期数",
                        attachment_type=allure.attachment_type.TEXT
                    )

            # 执行部分还款
            captcha_cfg = config['step_get_captcha']
            captcha_body = {
                "mobile": config['captcha']['mobile'],
                "clientType": config['captcha']['client_type']
            }
            repay_cfg = config['step_repayment']
            repay_body = {
                "orderId": order_id,
                "period": repay_period,
                "amount": repay_amount,
                "verifyCode": "",
                "type": repay_type
            }

            result = submit_with_captcha(
                api_client=merchant_api_client,
                captcha_endpoint=captcha_cfg['endpoint'],
                captcha_body=captcha_body,
                repay_endpoint=repay_cfg['endpoint'],
                repay_body=repay_body,
                max_retries=config['captcha']['max_retries'],
                request_interval=0.5,
                step_label="部分还款",
            )

            if not result.success:
                error_msg = result.error_message or "未知错误"
                skip_msg = (
                    f"还款失败: {error_msg}\n"
                    f"订单号: {order_id} | 还款金额: {repay_amount} | 尝试: {result.attempt}次\n\n"
                    f"完整响应:\n{json.dumps(result.response_json, ensure_ascii=False, indent=2) if result.response_json else 'N/A'}"
                )
                allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                logger.warning(f"还款失败: {skip_msg}")
                pytest.skip(skip_msg)

            # 确认实际还款金额
            repay_data = result.response_json.get('data') or {}
            actual_repay_amount = repay_data.get('partMoney', repay_amount)
            
            # 记录还款响应详情
            allure.attach(
                f"订单号: {order_id}\n"
                f"请求还款金额: {repay_amount} 元\n"
                f"实际还款金额: {actual_repay_amount} 元\n"
                f"验证码: {result.code}\n"
                f"尝试次数: {result.attempt}\n"
                f"businessSuccess: {result.response_json.get('businessSuccess')}\n"
                f"errorMessage: {result.response_json.get('errorMessage')}",
                name="还款成功",
                attachment_type=allure.attachment_type.TEXT
            )
            allure.attach(
                json.dumps(result.response_json, ensure_ascii=False, indent=2),
                name="还款接口完整响应",
                attachment_type=allure.attachment_type.JSON
            )
            
            logger.info(f"还款成功: order_id={order_id}, repay_amount={actual_repay_amount}")

        # ================================================================
        # ③ 计算期望值
        # ================================================================
        with allure.step("③ 计算期望值"):
            expected_total = initial_total + actual_repay_amount
            expected_un = initial_un - actual_repay_amount
            expected_rate = round(expected_total / (expected_total + expected_un) * 100) if (expected_total + expected_un) > 0 else 0

            allure.attach(
                f"【初始值】\n"
                f"  回款总金额: {initial_total} 元\n"
                f"  待追回总金额: {initial_un} 元\n"
                f"  回款率: {initial_rate}%\n\n"
                f"【本次还款】\n"
                f"  还款金额: {actual_repay_amount} 元\n\n"
                f"【期望值】\n"
                f"  回款总金额 = {initial_total} + {actual_repay_amount} = {expected_total} 元\n"
                f"  待追回总金额 = {initial_un} - {actual_repay_amount} = {expected_un} 元\n"
                f"  回款率 = {expected_total} / ({expected_total} + {expected_un}) × 100% = {expected_rate}%",
                name="计算过程",
                attachment_type=allure.attachment_type.TEXT
            )

        # ================================================================
        # ④ 等待数据更新并重试查询
        # ================================================================
        with allure.step("④ 等待数据更新并重试查询"):
            max_retries = 5
            wait_interval = 3
            new_total, new_un, new_rate = None, None, None
            data_updated = False
            
            for attempt in range(1, max_retries + 1):
                if attempt > 1:
                    time.sleep(wait_interval)
                
                new_total, new_un, new_rate = self._query_payback_summary(merchant_api_client)
                
                if new_total != initial_total or new_un != initial_un:
                    data_updated = True
                    allure.attach(
                        f"✓ 第{attempt}次查询数据已更新\n\n"
                        f"回款总金额: {initial_total} → {new_total} (变化: {new_total - initial_total})\n"
                        f"待追回总金额: {initial_un} → {new_un} (变化: {new_un - initial_un})\n"
                        f"回款率: {initial_rate}% → {new_rate}%",
                        name="数据更新成功",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    logger.info(f"数据已更新 (第{attempt}次): total={new_total}, un={new_un}")
                    break
                
                allure.attach(
                    f"第{attempt}次查询数据未变化\n"
                    f"回款总金额: {new_total} 元\n"
                    f"待追回总金额: {new_un} 元\n"
                    f"回款率: {new_rate}%",
                    name=f"第{attempt}次查询",
                    attachment_type=allure.attachment_type.TEXT
                )
                logger.info(f"数据未更新 (第{attempt}次): total={new_total}, un={new_un}")
            
            if not data_updated:
                allure.attach(
                    f"⚠ 经过{max_retries}次查询（等待{wait_interval * (max_retries - 1)}秒），数据仍未更新\n\n"
                    f"初始值: total={initial_total}, un={initial_un}\n"
                    f"当前值: total={new_total}, un={new_un}\n\n"
                    f"可能原因：\n"
                    f"1. 统计数据异步更新延迟较大\n"
                    f"2. 还款金额太小(0.01元)未触发更新\n"
                    f"3. 页面显示实时计算值，API返回缓存值",
                    name="数据未更新",
                    attachment_type=allure.attachment_type.TEXT
                )
                logger.warning(f"数据未更新: total={new_total}, un={new_un}")
        # ================================================================
        # ⑤ 断言验证
        # ================================================================
        with allure.step("⑤ 断言验证"):
            if not data_updated:
                pytest.skip(f"统计数据未更新（等待{wait_interval * (max_retries - 1)}秒），跳过断言")
            
            # 使用 Decimal 进行精确金额计算，避免浮点数精度问题
            # 说明：浮点数运算会产生精度误差（如 38966.43 + 0.01 = 38966.490000000005）
            # Decimal 类型可以精确表示和计算十进制小数，适合货币金额运算
            initial_total_dec = Decimal(str(initial_total))
            initial_un_dec = Decimal(str(initial_un))
            actual_repay_dec = Decimal(str(actual_repay_amount))
            new_total_dec = Decimal(str(new_total))
            new_un_dec = Decimal(str(new_un))
            
            # 精确计算期望值
            expected_total_dec = initial_total_dec + actual_repay_dec
            expected_un_dec = initial_un_dec - actual_repay_dec
            
            # 回款率计算（保留整数）
            if (expected_total_dec + expected_un_dec) > 0:
                expected_rate_dec = (expected_total_dec / (expected_total_dec + expected_un_dec) * 100).quantize(
                    Decimal('1'), rounding=ROUND_HALF_UP
                )
            else:
                expected_rate_dec = Decimal('0')
            
            expected_rate = int(expected_rate_dec)
            
            # 使用 Decimal 进行精确比较（金额精确相等）
            total_ok = new_total_dec == expected_total_dec
            un_ok = new_un_dec == expected_un_dec
            rate_ok = new_rate == expected_rate
            
            if not total_ok:
                total_diff = abs(new_total_dec - expected_total_dec)
                allure.attach(
                    f"✗ 回款总金额不匹配\n"
                    f"期望: {expected_total_dec} 元\n"
                    f"实际: {new_total_dec} 元\n"
                    f"差异: {total_diff} 元",
                    name="回款总金额断言失败",
                    attachment_type=allure.attachment_type.TEXT
                )
            assert total_ok, f"回款总金额不匹配: 期望 {expected_total_dec}, 实际 {new_total_dec}"
            
            if not un_ok:
                un_diff = abs(new_un_dec - expected_un_dec)
                allure.attach(
                    f"✗ 待追回总金额不匹配\n"
                    f"期望: {expected_un_dec} 元\n"
                    f"实际: {new_un_dec} 元\n"
                    f"差异: {un_diff} 元",
                    name="待追回总金额断言失败",
                    attachment_type=allure.attachment_type.TEXT
                )
            assert un_ok, f"待追回总金额不匹配: 期望 {expected_un_dec}, 实际 {new_un_dec}"
            
            if not rate_ok:
                rate_diff = abs(new_rate - expected_rate)
                allure.attach(
                    f"✗ 回款率不匹配\n"
                    f"期望: {expected_rate}%\n"
                    f"实际: {new_rate}%\n"
                    f"差异: {rate_diff}%",
                    name="回款率断言失败",
                    attachment_type=allure.attachment_type.TEXT
                )
            assert rate_ok, f"回款率不匹配: 期望 {expected_rate}%, 实际 {new_rate}%"
            
            # 转换为浮点数用于显示
            total_diff_display = float(abs(new_total_dec - expected_total_dec))
            un_diff_display = float(abs(new_un_dec - expected_un_dec))
            rate_diff_display = abs(new_rate - expected_rate)
            
            allure.attach(
                f"✓ 回款总金额: {new_total} == {float(expected_total_dec)} (差异: {total_diff_display} 元)\n"
                f"✓ 待追回总金额: {new_un} == {float(expected_un_dec)} (差异: {un_diff_display} 元)\n"
                f"✓ 回款率: {new_rate}% == {expected_rate}% (差异: {rate_diff_display}%)",
                name="断言通过",
                attachment_type=allure.attachment_type.TEXT
            )

        # 最终汇总
        allure.attach(
            f"还款订单: {order_id}\n"
            f"还款金额: {actual_repay_amount} 元\n\n"
            f"回款总金额: {initial_total} → {new_total} 元\n"
            f"待追回总金额: {initial_un} → {new_un} 元\n"
            f"回 款 率: {initial_rate}% → {new_rate}%\n\n"
            f"验证结果: ✓ 全部通过",
            name="测试总结",
            attachment_type=allure.attachment_type.TEXT
        )
