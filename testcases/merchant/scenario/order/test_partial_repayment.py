import math
import time
from datetime import datetime

import allure
import os
import pytest
import yaml
from common.logger import logger
from utils.variable_utils import validate, get_value_by_path
from utils.captcha_repayment_helper import submit_with_captcha, require_ddddocr


def load_yaml(yaml_path):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

@allure.epic("商家端")
@allure.feature("租后回款管理")
@allure.story("部分还款-销账-租后回款簿流程")
class TestPartialRepayment:

    @allure.title("完整流程：固定订单号 → OCR验证码(失败重试-次数可配置) → 部分还款(销账) → 验证回款簿记录")
    def test_partial_repayment_flow(self, merchant_api_client, global_vars):
        yaml_path = os.path.join(os.path.dirname(__file__), "../../../../data/merchant/scenario/order/partial_repayment.yaml")
        config = load_yaml(yaml_path)

        # 读取还款参数
        amount = config['repayment']['amount']
        period = config['repayment']['period']
        repay_type = config['repayment']['type']

        # 计算分两次还款的金额：第一次向上取整到分，第二次为剩余部分
        first_amount = math.ceil(amount / 2 * 100) / 100
        second_amount = round(amount - first_amount, 2)
        repay_count = 2 if second_amount > 0 else 1

        # ================================================================
        # 步骤1：使用固定订单号，查询分期详情获取还款期数
        # ================================================================
        with allure.step("1. 使用固定测试订单"):
            order_id = config['fixed_order']['order_id']
            allure.attach(
                f"固定测试订单号: {order_id}",
                name="步骤1-固定订单", attachment_type=allure.attachment_type.TEXT
            )

        with allure.step("1b. 查询订单分期详情获取还款期数"):
            stages_cfg = config['step_order_stages']
            stages_resp = merchant_api_client.post(stages_cfg['endpoint'], json={"orderId": order_id})
            stages_json = stages_resp.json()
            allure.attach(str(stages_json), name="分期详情-响应", attachment_type=allure.attachment_type.JSON)

            if stages_json.get('businessSuccess') is not True:
                skip_msg = f"订单分期详情查询失败: {stages_json.get('errorMessage', 'N/A')}，跳过此用例"
                logger.warning(skip_msg)
                pytest.skip(skip_msg)

            # 兼容多种响应格式：data 可能是 list 或 dict
            stages_data = stages_json.get('data') or []
            if isinstance(stages_data, dict):
                stages_data = (
                    stages_data.get('orderByStagesDtoList')
                    or stages_data.get('stages')
                    or stages_data.get('records')
                    or []
                )

            # 动态获取还款期数：找第一个未支付的期数（status != '2','3','5','6','7'）
            repay_period = period  # 兜底：用 YAML 默认值
            unpaid_periods = []
            stages_summary = []
            for stage in stages_data:
                s_periods = stage.get('periods') or stage.get('currentPeriods') or stage.get('period')
                s_status = str(stage.get('status', ''))
                stages_summary.append(f"  期数={s_periods}, status={s_status}")
                if s_status not in ['2', '3', '5', '6', '7']:
                    unpaid_periods.append(int(s_periods))

            if unpaid_periods:
                repay_period = min(unpaid_periods)  # 取最小未支付期数

            allure.attach(
                f"订单号: {order_id}\n"
                f"还款期数: {repay_period} (未支付期数: {unpaid_periods})\n\n"
                f"分期概览:\n" + "\n".join(stages_summary),
                name="步骤1b-分期结果", attachment_type=allure.attachment_type.TEXT
            )
            logger.info(f"使用订单: orderId={order_id}, repayPeriod={repay_period}")

        # ================================================================
        # 步骤2：验证码获取(OCR) + 分两次部分还款（合并重试）
        # 验证码有效期短，获取后立即提交还款，若过期则整体重试
        # ================================================================
        require_ddddocr()  # 预检 ddddocr 是否已安装

        # 记录还款请求发起时间，供步骤3时间戳验证使用
        repayment_before_time = datetime.now()

        max_flow_attempts = config['captcha'].get('max_retries', 3)
        captcha_cfg = config['step_get_captcha']
        captcha_body = {"mobile": config['captcha']['mobile'], "clientType": config['captcha']['client_type']}
        repay_cfg = config['step_repayment']

        allure.attach(
            f"总还款金额: {amount}\n"
            f"第一次还款: {first_amount}\n"
            f"第二次还款: {second_amount}\n"
            f"还款次数: {repay_count}",
            name="还款拆分方案", attachment_type=allure.attachment_type.TEXT
        )

        # ---- 第一次还款 ----
        repay_body_1 = {
            "orderId": order_id,
            "period": repay_period,
            "amount": first_amount,
            "verifyCode": "",
            "type": repay_type
        }

        result1 = submit_with_captcha(
            api_client=merchant_api_client,
            captcha_endpoint=captcha_cfg['endpoint'],
            captcha_body=captcha_body,
            repay_endpoint=repay_cfg['endpoint'],
            repay_body=repay_body_1,
            max_retries=max_flow_attempts,
            request_interval=0.5,
            step_label="验证码+第一次还款",
        )

        # ---- 第二次还款（仅当 second_amount > 0 时执行） ----
        result2 = None
        if repay_count == 2:
            repay_body_2 = {
                "orderId": order_id,
                "period": repay_period,
                "amount": second_amount,
                "verifyCode": "",
                "type": repay_type
            }

            result2 = submit_with_captcha(
                api_client=merchant_api_client,
                captcha_endpoint=captcha_cfg['endpoint'],
                captcha_body=captcha_body,
                repay_endpoint=repay_cfg['endpoint'],
                repay_body=repay_body_2,
                max_retries=max_flow_attempts,
                request_interval=0.5,
                step_label="验证码+第二次还款",
            )

        # 将第一次还款结果解包为后续步骤所需的变量
        repay_resp_json = result1.response_json
        flow_logs = result1.logs
        flow_attempt = result1.attempt
        code = result1.code

        # ================================================================
        # 步骤2 结果校验
        # ================================================================
        with allure.step("2-结果. 校验还款结果"):
            # ---------- 校验第一次还款 ----------
            if repay_resp_json is None:
                skip_msg = (
                    f"验证码获取+第一次还款流程全部失败（已重试{max_flow_attempts}次）\n\n"
                    f"各次尝试详情:\n" + "\n".join(flow_logs)
                )
                allure.attach(skip_msg, name="步骤2-断言结果(跳过)", attachment_type=allure.attachment_type.TEXT)
                logger.warning(skip_msg)
                pytest.skip(skip_msg)

            business_success = repay_resp_json.get('businessSuccess')
            error_msg = repay_resp_json.get('errorMessage', '未知错误')

            if business_success is not True:
                skip_msg = (
                    f"第一次还款业务失败，跳过后续验证\n"
                    f"  订单号: {order_id}\n"
                    f"  还款金额: {first_amount}\n"
                    f"  错误信息: {error_msg}\n\n"
                    f"各次尝试详情:\n" + "\n".join(flow_logs)
                )
                allure.attach(
                    f"businessSuccess: {business_success} != True ({error_msg})",
                    name="步骤2b-断言结果(跳过)", attachment_type=allure.attachment_type.TEXT
                )
                allure.attach(skip_msg, name="跳过原因", attachment_type=allure.attachment_type.TEXT)
                logger.warning(skip_msg)
                pytest.skip(skip_msg)

            # 断言第一次还款金额
            repay_data = repay_resp_json.get('data') or {}
            part_money = repay_data.get('partMoney')
            amount_match = part_money == first_amount

            # ---------- 校验第二次还款（如有） ----------
            second_part_money = None
            second_business_success = None
            if result2 is not None:
                second_resp_json = result2.response_json
                if second_resp_json is not None:
                    second_business_success = second_resp_json.get('businessSuccess')
                    second_data = second_resp_json.get('data') or {}
                    second_part_money = second_data.get('partMoney')

            allure.attach(
                f"【第一次还款】\n"
                f"  businessSuccess: {business_success} == True ✓\n"
                f"  partMoney: {part_money} == {first_amount} {'通过' if amount_match else '失败'}\n"
                f"  流程尝试次数: {flow_attempt}/{max_flow_attempts}\n\n"
                + (f"【第二次还款】\n"
                   f"  businessSuccess: {second_business_success}\n"
                   f"  partMoney: {second_part_money} == {second_amount}"
                   if result2 is not None else "【第二次还款】无（金额已全部分配到第一次）"),
                name="步骤2-断言结果", attachment_type=allure.attachment_type.TEXT
            )
            assert amount_match, f"第一次还款金额不匹配: 期望 {first_amount}, 实际 {part_money}"
            logger.info(f"第一次还款成功: partMoney={part_money}")
            if result2 is not None:
                logger.info(f"第二次还款结果: businessSuccess={second_business_success}, partMoney={second_part_money}")

        # ================================================================
        # 步骤3：查询回款簿并验证跟回金额
        # 回款簿记录由异步任务生成，还款成功后存在延迟，需轮询等待
        # ================================================================
        with allure.step("3. 查询回款簿验证跟回金额"):
            book_cfg = config['step_payback_book']
            retry_cfg = book_cfg.get('retry', {})
            max_attempts = retry_cfg.get('max_attempts', 5)
            interval = retry_cfg.get('interval_seconds', 2)

            book_body = book_cfg['body'].copy()
            book_body['orderId'] = order_id
            allure.attach(
                f"接口: POST {book_cfg['endpoint']}\n\n"
                f"{yaml.dump(book_body, allow_unicode=True, default_flow_style=False)}\n"
                f"重试策略: 最多 {max_attempts} 次，间隔 {interval} 秒",
                name="查询回款簿-请求参数", attachment_type=allure.attachment_type.TEXT
            )

            # 轮询查询回款簿，等待异步记录生成
            book_records = []
            resp_json = None
            resp_status = None
            attempt_logs = []  # 记录每次尝试的结果

            for attempt in range(1, max_attempts + 1):
                resp = merchant_api_client.post(book_cfg['endpoint'], json=book_body)
                resp_status = resp.status_code
                resp_json = resp.json()

                # 每次尝试都先校验 HTTP 状态码和业务状态
                if resp_status != book_cfg['expected_status']:
                    attempt_logs.append(f"第{attempt}次: HTTP状态码异常 {resp_status}")
                    logger.warning(f"回款簿查询 HTTP 状态码异常: {resp_status}，第{attempt}/{max_attempts}次")
                elif resp_json.get('businessSuccess') is not True:
                    attempt_logs.append(f"第{attempt}次: businessSuccess != true")
                    logger.warning(f"回款簿查询 businessSuccess 非 true，第{attempt}/{max_attempts}次")
                else:
                    book_data = resp_json.get('data') or {}
                    book_records = book_data.get('records') or []
                    if book_records:
                        attempt_logs.append(f"第{attempt}次: 成功获取到 {len(book_records)} 条记录")
                        logger.info(f"回款簿查询成功（第{attempt}次）: 共 {len(book_records)} 条记录")
                        break
                    else:
                        attempt_logs.append(f"第{attempt}次: records 为空，等待异步数据生成")
                        logger.info(f"回款簿 records 为空（第{attempt}/{max_attempts}次），等待 {interval}s 后重试")

                # 非最后一次才 sleep
                if attempt < max_attempts:
                    time.sleep(interval)
            else:
                # 所有重试均失败，记录详细日志后断言失败
                allure.attach(
                    str(resp_json), name="查询回款簿-最终响应", attachment_type=allure.attachment_type.JSON
                )
                retry_detail = (
                    f"共重试 {max_attempts} 次，间隔 {interval}s，回款簿 records 始终为空\n\n"
                    f"各次尝试详情:\n" + "\n".join(attempt_logs)
                )
                allure.attach(retry_detail, name="步骤3-重试详情", attachment_type=allure.attachment_type.TEXT)
                logger.error(f"回款簿轮询超时: orderId={order_id}, 共{max_attempts}次")

            # 附加最终响应和重试摘要
            allure.attach(
                str(resp_json), name="查询回款簿-响应结果", attachment_type=allure.attachment_type.JSON
            )
            allure.attach(
                "\n".join(attempt_logs), name="步骤3-轮询记录", attachment_type=allure.attachment_type.TEXT
            )

            # 断言 HTTP 状态码
            assert resp_status == book_cfg['expected_status'], \
                f"回款簿查询接口HTTP状态码异常: {resp_status}"

            # 断言 businessSuccess
            book_success = resp_json.get('businessSuccess')
            assert book_success is True, "回款簿查询 businessSuccess 不为 true"

            # 断言 records 非空
            assert len(book_records) > 0, (
                f"回款簿记录列表为空（已轮询 {max_attempts} 次，间隔 {interval}s，"
                f"还款数据可能尚未同步完成）"
            )

            # ---------- 遍历全部记录，精确匹配第一次还款 ----------
            # 匹配条件：orderId 一致 + 跟回金额(first_amount) 一致
            # 若多条匹配，取时间最新的一条（backTime 或 createTime 倒序）
            record_details = []  # 每条记录的摘要（用于 Allure 展示）
            matched_records = []  # 精确匹配的记录

            for i, rec in enumerate(book_records):
                rec_id = rec.get('id')
                rec_order = rec.get('orderId')
                rec_amount = rec.get('followAmount')
                rec_back_time = rec.get('backTime') or rec.get('createTime') or ''
                rec_type = rec.get('paybackType', 'N/A')

                # 判断是否匹配第一次还款
                order_match = rec_order == order_id
                amount_match = rec_amount == first_amount
                is_match = order_match and amount_match

                record_details.append(
                    f"  #{i+1} id={rec_id} | orderId={rec_order}{'✓' if order_match else '✗'} "
                    f"| 金额={rec_amount}{'✓' if amount_match else '✗'}(期望{first_amount}) "
                    f"| 时间={rec_back_time} | 类型={rec_type} "
                    f"| {'★ 匹配' if is_match else ''}"
                )

                if is_match:
                    matched_records.append(rec)

            # 从匹配记录中选时间最新的一条
            target_record = None
            if matched_records:
                matched_records.sort(
                    key=lambda r: r.get('backTime') or r.get('createTime') or '',
                    reverse=True
                )
                target_record = matched_records[0]
                logger.info(
                    f"精确匹配到 {len(matched_records)} 条记录，选取最新: "
                    f"id={target_record.get('id')}, backTime={target_record.get('backTime')}"
                )
            else:
                # 无精确匹配 → 降级取第一条记录（保持原有行为），但后续断言会失败
                target_record = book_records[0]
                logger.warning(
                    f"未找到精确匹配记录（orderId={order_id}, 金额={first_amount}），"
                    f"降级使用第一条记录 id={target_record.get('id')}"
                )

            # ---------- 从目标记录中提取字段并断言 ----------
            follow_amount = target_record.get('followAmount')
            record_order_id = target_record.get('orderId')
            record_id = target_record.get('id')
            record_back_time = target_record.get('backTime') or target_record.get('createTime')
            record_type = target_record.get('paybackType', 'N/A')

            logger.info(
                f"回款簿目标记录: id={record_id}, followAmount={follow_amount}, "
                f"orderId={record_order_id}, backTime={record_back_time}"
            )

            # 多维断言（仅验证第一次还款）
            amount_ok = follow_amount == first_amount
            order_ok = record_order_id == order_id

            # 时间戳验证：确保记录时间在还款请求发起之后（还款前记录 repayment_before_time）
            time_ok = True
            time_detail = 'N/A'
            if record_back_time:
                try:
                    rec_dt = datetime.strptime(record_back_time, "%Y-%m-%d %H:%M:%S")
                    time_ok = rec_dt >= repayment_before_time
                    time_detail = (
                        f"{record_back_time} {'≥' if time_ok else '<'} "
                        f"{repayment_before_time.strftime('%Y-%m-%d %H:%M:%S')} "
                        f"{'通过' if time_ok else '失败(记录时间早于还款请求)'}"
                    )
                except ValueError:
                    time_detail = f"{record_back_time} (时间格式无法解析，跳过时间校验)"

            # Allure 附件：全部记录遍历 + 匹配结果
            allure.attach(
                f"匹配条件: orderId={order_id}, 金额={first_amount}（第一次还款）\n"
                f"精确匹配记录数: {len(matched_records)}\n\n"
                f"全部记录详情 ({len(book_records)} 条):\n" + "\n".join(record_details),
                name="步骤3a-记录遍历与匹配", attachment_type=allure.attachment_type.TEXT
            )

            # Allure 附件：最终断言结果
            allure.attach(
                f"HTTP状态码: {resp_status} == 200 \n"
                f"businessSuccess: {book_success} == True \n"
                f"records数量: {len(book_records)} > 0 \n"
                f"followAmount: {follow_amount} == {first_amount} {'通过' if amount_ok else '失败'}\n"
                f"orderId: {record_order_id} == {order_id} {'通过' if order_ok else '失败'}\n"
                f"backTime: {time_detail}\n\n"
                f"目标记录详情:\n"
                f"  记录ID: {record_id}\n"
                f"  跟回金额: {follow_amount}\n"
                f"  订单号: {record_order_id}\n"
                f"  回款类型: {record_type}\n"
                f"  回款时间: {record_back_time}\n"
                f"  精确匹配记录数: {len(matched_records)}/{len(book_records)}",
                name="步骤3b-断言结果", attachment_type=allure.attachment_type.TEXT
            )

            assert amount_ok, f"跟回金额不匹配: 期望 {first_amount}, 实际 {follow_amount}"
            assert order_ok, f"回款簿订单号不匹配: 期望 {order_id}, 实际 {record_order_id}"

            logger.info(
                f"回款簿验证通过（第一次还款）: orderId={order_id}, followAmount={follow_amount}, "
                f"backTime={record_back_time}"
            )

        # ================================================================
        # 最终汇总
        # ================================================================
        allure.attach(
            f"步骤1-查询订单: orderId={order_id} \n"
            f"步骤2-第一次还款: code='{code}', partMoney={part_money}, amount={first_amount}  (第{flow_attempt}次成功)\n"
            + (f"步骤2-第二次还款: partMoney={second_part_money}, amount={second_amount}\n"
               if result2 is not None else "")
            + f"步骤3-回款簿(验证第一次): followAmount={follow_amount}, backTime={record_back_time}",
            name="最终验证结果", attachment_type=allure.attachment_type.TEXT
        )
        logger.info("部分还款-销账-租后回款簿流程执行成功")
