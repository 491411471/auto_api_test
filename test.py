import requests

data={"status":["PENDING_DEAL"],"pageNumber":1,"pageSize":10,"overDueQueryFlag":False,"channelIdList":["008"],"statusList":["04"],"uid":"5c26fd969129a46b14a4c01f91e6b4ee56611ba9f6o5yw9l47p9"}

headers={
    "Content-Type":"application/json",
    "token":"mxqucr00n7bd60mrm60hydre4rjt9k4c",
    "channelid":"008"
}

res = requests.post("https://test.llxzu.com/llxz-api-web/hzsx/api/order/userOrderList", json=data, headers=headers)
print(res.json())