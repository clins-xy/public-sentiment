import asyncio
import base64
import hmac
import ipaddress
import json
import os
import socket

from starlette.concurrency import run_in_threadpool
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..core.utils import now


BODY_LIMIT = 1024 * 1024
CONTENT_POLICY = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"


def loopback(host):
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def load_tokens(host, tokens=None):
    if tokens is None:
        tokens = {
            role: os.environ[f"PUBLIC_SENTIMENT_{role.upper()}_TOKEN"]
            for role in ("admin", "operator", "viewer")
            if os.environ.get(f"PUBLIC_SENTIMENT_{role.upper()}_TOKEN")
        }
    tokens = dict(tokens)
    if set(tokens) - {"admin", "operator", "viewer"} or any(not isinstance(value, str) or not value for value in tokens.values()):
        raise ValueError("访问令牌配置无效")
    if tokens and "admin" not in tokens:
        raise ValueError("开启鉴权时必须设置 PUBLIC_SENTIMENT_ADMIN_TOKEN")
    if not loopback(host) and not tokens:
        raise ValueError("非本机监听必须设置 PUBLIC_SENTIMENT_ADMIN_TOKEN")
    return tokens


def authenticate(headers, tokens):
    if not tokens:
        return "admin"
    try:
        scheme, encoded = headers.get("Authorization", "").split(" ", 1)
        if scheme.lower() != "basic":
            return None
        username, password = base64.b64decode(encoded, validate=True).decode("utf-8").split(":", 1)
        expected = tokens.get(username)
        if expected and hmac.compare_digest(password.encode(), expected.encode()):
            return username
    except (ValueError, UnicodeError):
        pass
    return None


class ConsoleMiddleware:
    def __init__(self, app, tokens, host, port):
        self.app = app
        self.tokens = tokens
        self.host = host
        self.port = port

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        body_finished = False

        async def receive_body():
            nonlocal body_finished
            message = await receive()
            if message["type"] == "http.disconnect" or (message["type"] == "http.request" and not message.get("more_body", False)):
                body_finished = True
            return message

        request = Request(scope, receive_body)
        headers = request.headers
        path = scope["path"].rstrip("/") or "/"
        response_status = 500
        response_started = False

        async def send_headers(message):
            nonlocal response_status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                response_status = message["status"]
                outgoing = MutableHeaders(scope=message)
                outgoing.setdefault("Cache-Control", "no-store")
                outgoing["X-Content-Type-Options"] = "nosniff"
                outgoing["X-Frame-Options"] = "DENY"
                outgoing["Referrer-Policy"] = "same-origin"
                policy = CONTENT_POLICY
                if path == "/docs":
                    policy = policy.replace("script-src 'self'", "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'")
                    policy = policy.replace("style-src 'self'", "style-src 'self' https://cdn.jsdelivr.net")
                outgoing["Content-Security-Policy"] = policy
            await send(message)

        async def reject(message, status, extra_headers=None):
            if scope["method"] == "POST" and not body_finished:
                remaining = 65536
                try:
                    async with asyncio.timeout(1):
                        while not body_finished and remaining > 0:
                            pending = await receive_body()
                            remaining -= len(pending.get("body", b""))
                except TimeoutError:
                    pass
            await JSONResponse({"error": message}, status_code=status, headers=extra_headers)(scope, receive, send_headers)

        try:
            server_host, server_port = scope.get("server") or (self.host, self.port)
            names = {"localhost", "127.0.0.1", "::1", self.host, server_host, socket.gethostname()}
            names = {f"[{name}]" if ":" in name else name for name in names}
            allowed = {f"{name}:{server_port}" for name in names}
            if server_port == (443 if scope["scheme"] == "https" else 80):
                allowed.update(names)
            host = headers.get("host", "")
            if len(headers.getlist("host")) != 1 or host not in allowed:
                await reject("Host 不在允许列表中", 403)
                return
            if not self.tokens and not loopback(server_host):
                await reject("非本机监听必须开启鉴权", 403)
                return
            role = authenticate(headers, self.tokens)
            if role is None:
                await reject("请使用 viewer、operator 或 admin 账号和对应令牌登录", 401,
                             {"WWW-Authenticate": 'Basic realm="Public Sentiment", charset="UTF-8"'})
                return
            scope.setdefault("state", {})["role"] = role
            if path.startswith("/api/database/") and role != "admin":
                await reject("数据库诊断仅管理员可用", 403)
                return
            mutating = scope["method"] == "POST" and path not in ("/api/graph/query", "/api/forum/log/history")
            mutating = mutating or path.startswith(("/api/start/", "/api/stop/")) or path in ("/api/forum/start", "/api/forum/stop")
            if mutating:
                origin = headers.get("origin")
                if headers.get("sec-fetch-site") == "cross-site" or headers.get("sec-fetch-mode") == "navigate" or (origin and origin != f"{scope['scheme']}://{host}"):
                    await reject("拒绝跨站控制请求", 403)
                    return
                admin_only = path in ("/api/config", "/api/system/start", "/api/system/shutdown")
                if role == "viewer" or (admin_only and role != "admin"):
                    await reject("当前角色无权执行此操作", 403)
                    return
            if scope["method"] == "POST" and path.startswith("/api/"):
                declared = headers.get("content-length")
                if declared is not None and not declared.isdigit():
                    await reject("Content-Length 必须为非负整数", 400)
                    return
                body = bytearray()
                async with asyncio.timeout(15):
                    async for chunk in request.stream():
                        if len(body) + len(chunk) > BODY_LIMIT:
                            await reject("JSON 请求体不能超过 1 MiB", 400)
                            return
                        body.extend(chunk)
                if body:
                    if headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                        await reject("Content-Type 须为 application/json", 400)
                        return
                    parsed = json.loads(body.decode("utf-8"))
                    if not isinstance(parsed, dict):
                        await reject("请求体必须为 JSON 对象", 400)
                        return
                delivered = False

                async def replay():
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await receive()

                await self.app(scope, replay, send_headers)
            else:
                await self.app(scope, receive, send_headers)
        except (ValueError, UnicodeError, TimeoutError) as error:
            if response_started:
                raise
            await reject(str(error) or "请求体读取超时", 400)
        except Exception as error:
            if response_started:
                raise
            service = getattr(scope["app"].state, "service", None)
            if service is not None:
                await run_in_threadpool(service.record_error, "http", str(error))
            await reject("服务器内部错误，请查看系统日志", 500)
        finally:
            service = getattr(scope["app"].state, "service", None)
            if service is not None:
                await run_in_threadpool(service.storage.append, "runtime/http.log", f"{now()} {scope['method']} {path!r} {response_status}")
