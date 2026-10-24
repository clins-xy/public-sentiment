import argparse
import json
import os
from pathlib import Path

import uvicorn

from .application.service import Service
from .collection.database import inspect_database
from .config.environment import load_env
from .infrastructure.storage import Storage
from .web.server import ConsoleServer, create_app

def main():
    parser = argparse.ArgumentParser(description="观潮舆情分析平台")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", type=Path, default=Path.cwd())
    parser.add_argument("--demo", action="store_true", help="生成低空物流完整示例并退出（不监听端口）")
    parser.add_argument("--inspect-database", action="store_true", help="只读检查数据库连接并输出表结构和建议映射，不启动 Web 或分析任务")
    arguments = parser.parse_args()
    load_env(arguments.data_dir.resolve())
    if arguments.inspect_database:
        config = Storage(arguments.data_dir).get_config()
        try:
            result = inspect_database(config["database"], config["system"]["request_timeout"])
        except (ValueError, RuntimeError) as error:
            parser.exit(1, f"数据库检查失败：{error}\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    tokens = {role: os.environ[f"PUBLIC_SENTIMENT_{role.upper()}_TOKEN"] for role in ("admin", "operator", "viewer") if os.environ.get(f"PUBLIC_SENTIMENT_{role.upper()}_TOKEN")}
    if tokens and "admin" not in tokens:
        parser.error("开启鉴权时必须设置 PUBLIC_SENTIMENT_ADMIN_TOKEN")
    if arguments.host not in ("127.0.0.1", "localhost") and not tokens:
        parser.error("非本机监听必须设置 PUBLIC_SENTIMENT_ADMIN_TOKEN；公网部署还须通过 HTTPS 反向代理")
    if arguments.demo:
        service = Service(arguments.data_dir)
        if service.storage.get_config()["collection"]["mode"] != "demo":
            parser.error("--demo 只允许在 demo 配置下运行，避免误用真实采集配置")
        try:
            service.start_system()
            result = service.search({"query": "低空物流"}, report_id="demo-low-altitude-logistics")
            print(f"示例完成：reports/{result['report_id']}/report.md（{result['source_count']} 条来源）")
        finally:
            service.shutdown()
        return
    app = create_app(arguments.data_dir, tokens=tokens, host=arguments.host, port=arguments.port)
    config = uvicorn.Config(
        app, host=arguments.host, port=arguments.port, workers=1,
        proxy_headers=False, access_log=False, timeout_graceful_shutdown=30,
    )
    print(f"观潮控制台：http://{arguments.host}:{arguments.port} · {'角色鉴权已启用' if tokens else '本机开发模式，无鉴权'}", flush=True)
    ConsoleServer(config).run()

if __name__ == "__main__":
    main()
