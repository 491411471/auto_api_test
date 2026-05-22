"""
测试请求间隔功能
"""
import time
from common.api_client import APIClient

def test_request_interval():
    """测试请求间隔是否正常工作"""
    # 创建一个带有1秒间隔的API客户端
    client = APIClient(
        base_url="https://httpbin.org",
        request_interval=1.0
    )
    
    print("开始测试请求间隔功能...")
    start_time = time.time()
    
    # 连续发送3个请求
    for i in range(3):
        print(f"\n发送第 {i+1} 个请求...")
        resp = client.get("/get")
        elapsed = time.time() - start_time
        print(f"请求完成，总耗时: {elapsed:.2f}秒")
    
    total_time = time.time() - start_time
    print(f"\n总耗时: {total_time:.2f}秒")
    print(f"预期最少耗时: 2秒 (3个请求之间有2个间隔，每个1秒)")
    
    if total_time >= 2.0:
        print("✓ 请求间隔功能正常工作")
    else:
        print("✗ 请求间隔功能可能未正常工作")

if __name__ == "__main__":
    test_request_interval()
