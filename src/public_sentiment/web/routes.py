import asyncio
import json
import time
from pathlib import Path

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.security import HTTPBasic
from starlette.concurrency import run_in_threadpool

from ..collection.database import inspect_database
from .schemas import ForumHistoryRequest, GraphQueryRequest, SearchRequest


STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
router = APIRouter(dependencies=[Depends(HTTPBasic(auto_error=False))])


def page():
    return FileResponse(STATIC_ROOT / "index.html", media_type="text/html")


for page_path in ("/", "/search", "/forum", "/config", "/system", "/reports", "/graph-viewer", "/graph-viewer/{report_id}"):
    router.add_api_route(page_path, page, methods=["GET"], include_in_schema=False)


@router.get("/api/session", tags=["session"])
def session(request: Request):
    return {"role": request.state.role, "authentication_enabled": bool(request.app.state.tokens)}


@router.get("/api/status", tags=["system"])
@router.get("/api/system/status", tags=["system"])
def status(request: Request):
    return request.app.state.service.status()


@router.post("/api/system/start", tags=["system"])
def start_system(request: Request):
    return request.app.state.service.start_system()


@router.post("/api/system/shutdown", tags=["system"])
def shutdown_system(request: Request):
    return request.app.state.service.shutdown()


@router.get("/api/start/{name}", tags=["workers"])
def start_app(name: str, request: Request):
    return request.app.state.service.start_app(name)


@router.get("/api/stop/{name}", tags=["workers"])
def stop_app(name: str, request: Request):
    return request.app.state.service.stop_app(name)


@router.get("/api/output/{name}", tags=["workers"])
def output(name: str, request: Request):
    service = request.app.state.service
    service.manager.get(name)
    return {"app_name": name, "output_text": service.storage.read_text(f"outputs/{name}/latest.txt")}


@router.get("/api/test_log/{name}", tags=["workers"])
def app_log(name: str, request: Request):
    service = request.app.state.service
    service.manager.get(name)
    return {"app_name": name, "log": service.storage.tail_text(f"runtime/apps/{name}.log")}


@router.get("/api/forum/start", tags=["forum"])
def start_forum(request: Request):
    service = request.app.state.service
    with service.lock:
        service.require_online()
        return service.forum.start()


@router.get("/api/forum/stop", tags=["forum"])
def stop_forum(request: Request):
    service = request.app.state.service
    with service.lock:
        return service.forum.stop()


@router.get("/api/forum/log", tags=["forum"])
def forum_log(request: Request):
    service = request.app.state.service
    return {"status": service.forum.status, "log": service.storage.tail_text("runtime/forum/latest.log")}


@router.post("/api/forum/log/history", tags=["forum"])
def forum_history(body: ForumHistoryRequest, request: Request):
    return {"date": body.date, "records": request.app.state.service.forum.history(body.date)}


@router.get("/api/config", tags=["config"])
def get_config(request: Request):
    return request.app.state.service.storage.get_config()


@router.post("/api/config", tags=["config"])
def update_config(request: Request, body: dict = Body(...)):
    return request.app.state.service.update_config(body)


@router.get("/api/database/schema", tags=["database"])
def database_schema(request: Request):
    config = request.app.state.service.storage.get_config()
    return inspect_database(config["database"], config["system"]["request_timeout"])


@router.post("/api/search", tags=["analysis"])
def search(body: SearchRequest, request: Request):
    return request.app.state.service.search(body.model_dump())


@router.get("/api/graph/latest", tags=["graphs"])
def latest_graph(request: Request):
    return request.app.state.service.graph()


@router.get("/api/graph/{report_id}", tags=["graphs"])
def get_graph(report_id: str, request: Request):
    return request.app.state.service.graph(report_id)


@router.post("/api/graph/query", tags=["graphs"])
def query_graph(body: GraphQueryRequest, request: Request):
    return request.app.state.service.query_graph(body.model_dump())


@router.get("/api/reports", tags=["reports"])
def reports(request: Request):
    return {"reports": request.app.state.service.reports()}


@router.get("/api/reports/{report_id}/markdown", tags=["reports"])
def markdown(report_id: str, request: Request):
    result = request.app.state.service.get_report(report_id)
    return Response(result["markdown"], media_type="text/markdown", headers={
        "Content-Disposition": f'attachment; filename="{result["report_id"]}.md"',
    })


@router.get("/api/reports/{report_id}", tags=["reports"])
def get_report(report_id: str, request: Request):
    return request.app.state.service.get_report(report_id)


@router.get("/api/system/log", tags=["system"])
def system_log(request: Request):
    return {"log": request.app.state.service.storage.tail_text("runtime/system.log")}


class EventStreamResponse(StreamingResponse):
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            scope["app"].state.event_slots.release()


@router.get("/api/events", tags=["events"], response_class=StreamingResponse)
async def events(request: Request):
    state = request.app.state
    identifier = request.headers.get("last-event-id", "0")
    if not identifier.isdigit() or len(identifier) > 19:
        return JSONResponse({"error": "Last-Event-ID 须为非负整数"}, status_code=400)
    if state.event_slots.locked():
        return JSONResponse({"error": "实时连接数已达上限"}, status_code=503)
    await state.event_slots.acquire()

    async def stream():
        sequence = int(identifier)
        heartbeat = time.monotonic()
        yield ": connected\n\n"
        while not state.closing.is_set():
            if await request.is_disconnected():
                break
            updates = await run_in_threadpool(state.service.events.since, sequence, 0)
            for event in updates:
                data = json.dumps(event, ensure_ascii=False)
                yield f"id: {event['id']}\nevent: {event['type']}\ndata: {data}\n\n"
                sequence = event["id"]
            if time.monotonic() - heartbeat >= 15:
                yield ": heartbeat\n\n"
                heartbeat = time.monotonic()
            try:
                await asyncio.wait_for(state.closing.wait(), timeout=0.25)
            except TimeoutError:
                pass

    return EventStreamResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })
