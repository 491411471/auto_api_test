# -*- coding: utf-8 -*-
# [NEW] 企业微信通知模块，用于发送测试报告
import requests

from common.logger import logger


def send_wechat_report(test_time, total_cases, report_url, passed, failed, error,
                       webhook_url, mentioned_mobiles=None, timeout=30):
    """
    发送测试报告到企业微信（markdown格式）
    """
    pass_rate = (passed / total_cases * 100) if total_cases else 0
    content = f"""## 📊 接口自动化测试报告
> **测试时间**: {test_time}
> **总用例数**: {total_cases}
> ** 通过**: {passed}
> ** 失败**: {failed}
> ** 错误**: {error}
> ** 通过率**: {pass_rate:.1f}%

[ 查看详细报告]({report_url})
"""
    if mentioned_mobiles:
        at_text = " ".join([f"@{mobile}" for mobile in mentioned_mobiles])
        content += f"\n\n{at_text}"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content,
            "mentioned_mobile_list": [str(m) for m in (mentioned_mobiles or [])]
        }
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=timeout)
        result = resp.json()
        if result.get("errcode") == 0:
            logger.info("企业微信通知发送成功")
            return True
        else:
            logger.error(f"企业微信通知失败: {result.get('errmsg')}")
            return False
    except Exception as e:
        logger.error(f"发送企业微信通知异常: {e}")
        return False