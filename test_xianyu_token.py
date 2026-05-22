"""
闲鱼token验证工具
用于测试闲鱼店铺token是否有效
"""
import requests

# 配置
BASE_URL = "https://test.llxzu.com"
XIAN_YU_TOKEN = "kumgjkgd8ck4srfm9lfzuzqaxedldvjx"  # 替换为你的闲鱼token

def test_xianyu_token():
    """测试闲鱼token是否有效"""
    url = f"{BASE_URL}/hzsx/xianyu/product/addXianYuProduct"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {XIAN_YU_TOKEN}"
    }
    
    # 发送一个简单请求测试
    # 这里使用一个会返回token状态但不需要完整参数的接口
    test_url = f"{BASE_URL}/hzsx/common/health"  # 或其他健康检查接口
    
    try:
        response = requests.get(test_url, headers=headers, timeout=10)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 'LOGIN_INVALID':
                print("\n❌ Token已过期，需要重新登录获取新token")
            else:
                print("\n✅ Token有效")
        else:
            print(f"\n⚠️  HTTP状态码异常: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 请求失败: {e}")


def test_with_actual_api():
    """使用实际的商品创建接口测试（需要完整参数）"""
    url = f"{BASE_URL}/hzsx/xianyu/product/addXianYuProduct"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {XIAN_YU_TOKEN}"
    }
    
    # 最小化请求体
    payload = {
        "categoryIds": [8, 1230],
        "name": "token测试商品",
        "title": "token测试商品",
        "oldNewDegree": 1,
        "itemLeaseDTO": {
            "inventory": "1",
            "marketPrice": "100",
            "rentalDepositPriceInCent": 0.01,
            "cycs": [{
                "dayOrMonth": "day",
                "days": "1",
                "priceCent": "1",
                "totalRental": "1.00"
            }]
        },
        "images": [],
        "detail": "<p>测试</p>",
        "address": ["110000", "110100", "110101"],
        "freightType": "FREE",
        "type": 1,
        "categoryId": 1230
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        print(f"状态码: {response.status_code}")
        data = response.json()
        print(f"响应: {data}")
        
        if data.get('code') == 'LOGIN_INVALID':
            print("\n❌ Token已过期，错误信息:", data.get('errorMsg'))
            print("\n请重新登录闲鱼商家后台获取新token")
        elif data.get('businessSuccess') is False:
            print("\n⚠️  业务失败（但token有效）:", data.get('errorMessage'))
        else:
            print("\n✅ Token有效，接口调用成功")
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 请求失败: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("闲鱼Token验证工具")
    print("=" * 60)
    print(f"\n当前配置的token: {XIAN_YU_TOKEN[:10]}...")
    print(f"服务器: {BASE_URL}")
    print("\n" + "=" * 60)
    
    print("\n方法1: 测试健康检查接口")
    print("-" * 60)
    test_xianyu_token()
    
    print("\n\n方法2: 测试实际商品创建接口")
    print("-" * 60)
    test_with_actual_api()
