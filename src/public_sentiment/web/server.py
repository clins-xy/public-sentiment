import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from ..application.service import Service
from ..config.environment import load_env
from .routes import STATIC_ROOT, router
from .security import ConsoleMiddleware, load_tokens


def create_app(data_dir=None, tokens=None, host=None, port=None) -> FastAPI:
    root = Path(data_dir or os.environ.get("PUBLIC_SENTIMENT_DATA_DIR", Path.cwd())).resolve()
    load_env(root)
    host = host or os.environ.get("PUBLIC_SENTIMENT_HOST", "127.0.0.1")
    port = port if port is not None else int(os.environ.get("PUBLIC_SENTIMENT_PORT", "8000"))
    tokens = load_tokens(host, tokens)

    @asynccontextmanager
    async def lifespan(app):
        app.state.closing = asyncio.Event()
        app.state.event_slots = asyncio.Semaphore(12)
        service = await run_in_threadpool(Service, root)
        app.state.service = service
        try:
            yield
        finally:
            app.state.closing.set()
            await run_in_threadpool(service.shutdown)

    app = FastAPI(
        title="Public Sentiment API", version="0.1.0", lifespan=lifespan,
        docs_url=None, redoc_url=None,
    )
    app.state.tokens = tokens
    app.state.closing = asyncio.Event()
    app.add_middleware(ConsoleMiddleware, tokens=tokens, host=host, port=port)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")

    @app.get("/docs", include_in_schema=False)
    async def docs():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url, title="Public Sentiment API",
            swagger_favicon_url="data:,",
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error):
        details = [{"location": list(item["loc"]), "message": item["msg"]} for item in error.errors()]
        return JSONResponse({"error": "请求参数无效", "details": details}, status_code=400)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error):
        return JSONResponse({"error": str(error.detail)}, status_code=error.status_code, headers=error.headers)

    async def business_error(request: Request, error):
        status = 404 if isinstance(error, KeyError) else 409 if isinstance(error, RuntimeError) else 400
        message = str(error.args[0]) if isinstance(error, KeyError) and error.args else str(error)
        return JSONResponse({"error": message}, status_code=status)

    for error_type in (KeyError, ValueError, TypeError, UnicodeError, RuntimeError):
        app.add_exception_handler(error_type, business_error)
    return app


class ConsoleServer(uvicorn.Server):
    def handle_exit(self, sig, frame):
        self.config.app.state.closing.set()
        super().handle_exit(sig, frame)
