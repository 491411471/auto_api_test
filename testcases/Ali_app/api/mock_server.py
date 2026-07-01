#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mock服务：模拟人脸核验、支付宝签约、支付回调、下单接口。

支持动态端口分配（自动检测可用端口，避免并发冲突）。
支持失败场景模拟（通过特殊请求参数触发），便于异常流程测试。

启动方式：
  1. 独立运行: python mock_server.py [--port 8888]
  2. 测试夹具集成: 通过 MockServerManager 类在测试中启停
"""
import json
import os
import socket
import threading
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any


# ==================== 端口工具 ====================
def _find_free_port(start_port: int = 8888, max_attempts: int = 100) -> int:
    """自动查找可用端口，避免并发执行时的端口冲突"""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"无法在范围 [{start_port}, {start_port + max_attempts}) 内找到可用端口")


# ==================== 环境变量控制（用于测试时注入端口） ====================
MOCK_PORT = int(os.environ.get('MOCK_SERVER_PORT', 0)) or _find_free_port()
MOCK_BASE_URL = f"http://localhost:{MOCK_PORT}"


# ==================== Mock 请求处理器 ====================
class MockHandler(BaseHTTPRequestHandler):
    """
    Mock HTTP 请求处理器。
    
    路由规则：
      POST /mock/face/verify         - 人脸核验（支持 fail_mode 参数触发失败）
      POST /mock/alipay/agreement/sign - 支付宝签约（支持 fail_mode 参数触发失败）
      POST /mock/alipay/callback     - 支付回调
      POST /mock/order/create        - 模拟下单（校验金额一致性）
    
    失败场景控制：
      在请求体中传入 "fail_mode": true，对应接口返回错误码。
      - 人脸核验失败: 返回 code="20000", msg="Face verification failed"
      - 签约失败:     返回 code="20000", msg="Agreement sign failed"
    """
    # 用于记录最近一次请求，便于测试断言
    _last_requests: Dict[str, Any] = {}

    def _read_body(self) -> dict:
        """读取并解析请求体 JSON"""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body.decode('utf-8'))

    def _send(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def do_POST(self):
        body = self._read_body()
        fail_mode = body.get('fail_mode', False)

        # 1. 模拟人脸识别接口
        if self.path == '/mock/face/verify':
            MockHandler._last_requests['face_verify'] = body
            if fail_mode:
                return self._send({
                    "code": "20000",
                    "msg": "Face verification failed",
                    "faceToken": None,
                    "verifyStatus": "FAIL",
                    "mock": True
                })
            face_token = f"MOCK_FACE_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
            return self._send({
                "code": "10000",
                "msg": "Success",
                "faceToken": face_token,
                "verifyStatus": "PASS",
                "mock": True
            })

        # 2. 模拟支付宝签约接口
        if self.path == '/mock/alipay/agreement/sign':
            MockHandler._last_requests['alipay_sign'] = body
            if fail_mode:
                return self._send({
                    "code": "20000",
                    "msg": "Agreement sign failed",
                    "agreement_no": None,
                    "status": "FAIL",
                    "mock": True
                })
            # 支持无效 face_token 检测（不含 MOCK_ 前缀视为无效）
            face_token = body.get('face_token', '')
            if face_token and not face_token.startswith('MOCK_'):
                return self._send({
                    "code": "20000",
                    "msg": "Invalid face token",
                    "agreement_no": None,
                    "status": "FAIL",
                    "mock": True
                })
            agreement_no = f"MOCK_AGREEMENT_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
            return self._send({
                "code": "10000",
                "msg": "Success",
                "agreement_no": agreement_no,
                "status": "NORMAL",
                "mock": True
            })

        # 3. 模拟支付宝支付回调接口
        if self.path == '/mock/alipay/callback':
            MockHandler._last_requests['payment_callback'] = body
            return self._send({
                "success": True,
                "msg": "Callback processed",
                "mock": True
            })

        # 4. 模拟下单接口（校验金额一致性）
        if self.path == '/mock/order/create':
            MockHandler._last_requests['create_order'] = body
            order_amount = body.get('amount', 0)
            order_id = f"MOCK_ORDER_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
            return self._send({
                "code": "10000",
                "msg": "Order created successfully",
                "order_id": order_id,
                "amount": order_amount,  # 原样返回传入金额
                "mock": True
            })

        self._send({"error": "Endpoint not found", "path": self.path}, 404)

    def do_OPTIONS(self):
        self._send({}, 200)

    def log_message(self, format, *args):
        """重写日志方法，避免测试时输出干扰"""
        pass  # 静默模式；调试时可改为 print(...)


# ==================== Mock 服务管理器（测试夹具用） ====================
class MockServerManager:
    """
    Mock 服务管理器，封装启停逻辑，支持作为 pytest fixture 使用。
    
    使用示例：
        manager = MockServerManager()
        manager.start()
        base_url = manager.base_url  # http://localhost:xxxxx
        # ... 执行测试 ...
        manager.stop()
    
    或作为上下文管理器：
        with MockServerManager() as manager:
            requests.post(f"{manager.base_url}/mock/face/verify", json={...})
    """

    def __init__(self, port: int = None):
        self.port = port or _find_free_port()
        self.base_url = f"http://localhost:{self.port}"
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def last_requests(self) -> Dict[str, Any]:
        """获取最近一次各接口的请求数据，用于测试断言"""
        return dict(MockHandler._last_requests)

    def clear_requests(self):
        """清空请求记录"""
        MockHandler._last_requests.clear()

    def start(self) -> "MockServerManager":
        """启动 Mock 服务（后台线程）"""
        if self._server is not None:
            return self
        self._server = HTTPServer(('127.0.0.1', self.port), MockHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        # 等待服务就绪
        time.sleep(0.1)
        return self

    def stop(self):
        """停止 Mock 服务"""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None
        MockHandler._last_requests.clear()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Mock服务 - 人脸核验/支付宝签约/支付回调')
    parser.add_argument('--port', type=int, default=8888, help='监听端口（默认8888）')
    args = parser.parse_args()

    port = _find_free_port(args.port) if args.port == 8888 else args.port
    server = HTTPServer(('0.0.0.0', port), MockHandler)
    print(f"Mock服务启动成功：http://localhost:{port}")
    print("支持接口：")
    print(f"  POST http://localhost:{port}/mock/face/verify         - 人脸核验")
    print(f"  POST http://localhost:{port}/mock/alipay/agreement/sign - 支付宝签约")
    print(f"  POST http://localhost:{port}/mock/alipay/callback     - 支付回调")
    print(f"  POST http://localhost:{port}/mock/order/create        - 模拟下单")
    print(f"\n失败场景：请求体中加入 \"fail_mode\": true 即可触发失败响应")
    server.serve_forever()