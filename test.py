import requests

url = "https://oss.llxzu.com/bd4a46def46641a79e9b697ec95fb526.pdf"

headers = {
    "User-Agent": "Mozilla/5.0"
}

resp = requests.get(url, headers=headers, timeout=30)

if resp.status_code == 200:
    with open("test.pdf", "wb") as f:
        f.write(resp.content)
    print("✅ PDF 下载成功")
else:
    print("❌ 请求失败，状态码：", resp.status_code)