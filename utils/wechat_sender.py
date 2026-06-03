# utils/wechat_sender.py
import json
import requests
from typing import List, Optional

def send_wechat_report(
        test_elapsed: float,
        test_time: str,
        total_cases: int,
        report_path: str,
        passed: int,
        failed: int,
        skipped: int,
        error: int,
        wechat_userids: Optional[List[str]] = None,
        mentioned_mobiles: Optional[List[str]] = None,
        webhook_url: Optional[str] = None,
        timeout: int = 30
) -> bool:
    """发送 Markdown 格式测试报告到企业微信"""
    if webhook_url is None:
        try:
            from config.config import WECHAT_WEBHOOK
            webhook_url = WECHAT_WEBHOOK
        except (ImportError, AttributeError):
            print("未提供 webhook_url 且无法从 config 读取")
            return False

    pass_rate = (passed / total_cases * 100) if total_cases else 0
    content = f"""
    # ✦ 品品 · 接口自动化测试报告 ✦ \n

    **测试时间**：<font color="comment">{test_time}</font>
    **执行耗时**：<font color="comment">{test_elapsed}(分钟)</font>
    <font color="comment">----------------------------</font>
    **测试统计**

    <font color="info">通过:{passed}</font>  <font color="warning">失败:{failed}</font>  <font color="#FF3366">错误:{error}</font>  <font color="#87CEFA">跳过:{skipped}</font>　
    **总计:**<font color="comment">{total_cases}</font>    **通过率:**<font color="comment">{pass_rate:.1f}</font>%

    <font color="comment">----------------------------</font>

    [>>点击查看详细报告<<]({report_path})
    """
    # @用户处理
    mentioned_userid_list = []
    if wechat_userids:
        cleaned = [str(u).strip() for u in wechat_userids if str(u).strip()]
        mentioned_userid_list = list(set(cleaned))
        if mentioned_userid_list:
            content += " ".join([f"<@{uid}>" for uid in mentioned_userid_list])

    mentioned_mobile_list = []
    if mentioned_mobiles:
        cleaned = [str(m).strip().replace(" ", "") for m in mentioned_mobiles]
        mentioned_mobile_list = list(set(cleaned))

    payload = {"msgtype": "markdown", "markdown": {"content": content}}
    if mentioned_userid_list:
        payload["markdown"]["mentioned_userid_list"] = mentioned_userid_list
    if mentioned_mobile_list:
        payload["markdown"]["mentioned_mobile_list"] = mentioned_mobile_list

    try:
        resp = requests.post(
            url=webhook_url,
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            timeout=timeout
        )
        if resp.status_code == 200:
            result = resp.json()
            if result.get("errcode") == 0:
                print("企业微信报告发送成功")
                return True
            else:
                print(f"企业微信 API 错误：{result.get('errmsg')}")
                return False
        else:
            print(f"HTTP 错误：{resp.status_code}")
            return False
    except Exception as e:
        print(f"请求异常：{str(e)}")
        return False