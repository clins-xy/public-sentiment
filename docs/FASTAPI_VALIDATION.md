# FastAPI + Uvicorn 改造与验证记录

验证日期：2026-10-23。此记录只描述本次实际完成的检查，不把模拟数据库当作真实数据库验收，也不把单条样本测试当作模型质量评估。

## 1. 改造了什么

| 位置 | 当前职责 |
| --- | --- |
| `src/public_sentiment/web/server.py` | `create_app()` 创建 FastAPI 应用；lifespan 创建并关闭业务资源；`ConsoleServer` 基于 Uvicorn 处理退出信号 |
| `src/public_sentiment/web/routes.py` | `APIRouter` 明确声明页面和 API；同步业务路由在线程池运行，SSE 使用异步生成器 |
| `src/public_sentiment/web/schemas.py` | Pydantic 请求模型，检查主题、来源类型、图查询和历史日期 |
| `src/public_sentiment/web/security.py` | 原生 ASGI 安全中间件，处理 Basic 角色、Host、同源控制、JSON 大小、安全响应头和访问日志 |
| `src/public_sentiment/cli.py` | 保留原命令行参数，Web 启动改为 Uvicorn；数据库检查和演示仍是独立分支 |
| `pyproject.toml`、`uv.lock` | 声明 Web 依赖并锁定安装版本 |

业务层、五个协程工作单元、模型输出协议、数据库适配器及原生前端保持原有职责，没有为了迁移 Web 框架重写分析算法，也没有删除已有报告。

## 2. 如何启动

在项目根目录安装依赖：

```powershell
uv sync --locked --extra mysql
```

继续使用已有启动脚本：

```powershell
.\run.ps1
```

或者启动 Python 命令行入口：

```powershell
.\.venv\Scripts\python.exe -m public_sentiment --data-dir . --port 8000
```

也支持 Uvicorn 工厂入口，模型/数据库凭据需提前写入本地环境或 `.env`：

```powershell
.\.venv\Scripts\uvicorn.exe public_sentiment.web.server:create_app --factory --host 127.0.0.1 --port 8000
```

启动后：

- 控制台：`http://127.0.0.1:8000/`。
- 交互式接口文档：`http://127.0.0.1:8000/docs`。
- OpenAPI JSON：`http://127.0.0.1:8000/openapi.json`。

本机本次启动使用 **8002**：8000 已由另一个项目占用，未停止或修改该服务。已实际确认 `http://127.0.0.1:8002/api/status`、`/openapi.json`、`/docs` 返回 200，OpenAPI 标题为 `Public Sentiment API`。业务系统初始为 offline，仍需启动业务并补齐数据库凭据后才能做实库分析。需要另行手动启动时可使用 `.\run.ps1 -Port 8002`，请先确认没有重复实例。

`/docs` 的 Swagger 脚本与样式来自 jsDelivr，需要浏览器能访问该 CDN；业务控制台本身的静态资源由本地提供。所有入口都保留访问控制，不是新增一个绕过鉴权的文档页面。

默认只监听本机。非本机监听须配置管理员令牌，工厂入口还应设置对应的 `PUBLIC_SENTIMENT_HOST`；公网部署仍需 HTTPS、受信反向代理及其他安全措施。当前文件存储与内存任务状态不支持多个 worker 共同管理同一数据目录。

## 3. HTTP 集成验证：116 项通过

验证使用真实启动的 Uvicorn HTTP 服务、独立临时数据目录和可控模型服务，不是只调用内部函数或只检查能否导入。

| 检查范围 | 实际覆盖 |
| --- | --- |
| 页面与资源 | 七类页面、指定图谱页面、JavaScript、CSS、安全响应头 |
| FastAPI 接口结构 | `/docs`、OpenAPI、请求模型和 HTTP Basic 安全定义 |
| 鉴权与权限 | 未登录/错误令牌拒绝、viewer/operator/admin 权限、非本机鉴权要求 |
| 请求安全 | Host、跨站控制、JSON 对象与格式、内容类型、1 MiB 限制、无效字段与类型 |
| 分析闭环 | 八条合成来源 → 并行采集 → 分批模型分析 → 报告/图谱 → 落盘和回查 |
| 事件循环响应 | 分析执行中状态接口可响应；重叠主题分析按现有规则拒绝 |
| 工作单元 | 五个岗位的状态、输出、日志、单独停止和重启 |
| 论坛 | 启停、轮询日志及按日期回查 |
| SSE | 建立连接、12 个连接上限、满额拒绝、断开释放、事件编号补发；SSE 期间普通接口可访问 |
| 模型异常 | 服务错误重试、无效结构纠正、最终失败返回错误、不生成伪成功报告 |
| 输出协议 | `json_object` 和 `json_schema` 两种模式 |
| 训练数据 | 默认未审核、拒绝未审核导出、审核后导出 3 条对话记录与 8 条语料 |
| 数据库适配 | 模拟连接下执行现有适配器，验证参数化 SQL、时间转换、定位信息、结构诊断与失败不回退 demo |
| 生命周期 | 系统停止/重启，lifespan 关闭业务，未遗留分析事件循环线程 |

“116 项”是该验证脚本的断言数量，不是性能基准、并发能力承诺或模型准确率。修正请求拒绝时的连接收尾后，该脚本完整通过，并连续复跑两轮，每轮均为 116 项通过。数据库适配部分替换了连接与元信息响应，**没有声称已经连接真实 MySQL**。

## 4. 两种真实启动入口验证

除了进程内启动 ASGI 服务，还分别创建了两个独立程序来验证：

| 启动入口 | 分析与归档 | 退出验证 |
| --- | --- | --- |
| `python -m public_sentiment` | 八条合成来源完整流程通过 | 保持 SSE 连接时发送 Windows 退出信号，状态落为 offline，五个岗位均 stopped |
| `python -m uvicorn ... --factory` | 八条合成来源完整流程通过 | 发送退出信号后完成业务关闭 |

项目命令行入口的退出验证包含活动 SSE；原生 Uvicorn 工厂入口在无活动 SSE 时验证退出。两者均检查状态文件和无异常堆栈，而不是把 Windows 信号终止时的退出码简单解释成业务失败。这里使用的模型仍是可控模型服务。

## 5. 真实模型验证

已使用本地现有配置连接真实模型服务，对一条合成来源完成逐条分析，结构与证据校验通过；未打印 API Key，也未把该次单条检查写入原有报告目录。

随后使用真实模型，通过实际运行的 FastAPI + Uvicorn 完成了整条 HTTP 链路：启动系统 → 提交一条合成来源 → 逐条分析 → 报告与图谱 → JSON/Markdown 归档 → HTTP 回查。结果为成功，图谱含 5 个节点，报告 1700 字符，生成 2 条待审核候选（分析与报告各一条）。所有产物均在独立临时数据目录，未改动既有报告。

这次完整调用约耗时 205 秒。首轮验证客户端使用 60 秒总等待上限而提前中断；复验采用覆盖多个模型阶段与重试的等待预算后通过。因此不能把固定 60 秒当作完整分析预算，也不把本次耗时当作性能承诺。实际延迟受模型服务、生成长度、批次数及重试影响，后续需要单独评估。

上述“真实”指模型 API 实际可调用；输入资料仍是明确标记的合成示例，**不是从真实 MySQL 获取的业务数据，也不是模型效果评测**。

## 6. 真实 MySQL：尚未通过验收

当前进程与项目 `.env` 没有提供以下连接变量，本次实际数据库检查在发起连接前即明确报错：

```dotenv
MEDIA_CRAWLER_DB_HOST=你的数据库地址
MEDIA_CRAWLER_DB_PORT=3306
MEDIA_CRAWLER_DB_USER=你的只读账号
MEDIA_CRAWLER_DB_PASSWORD=你的密码
```

请只在本地填写真实值，不要把密码提交、截图或发送到聊天。已有 `.env` 时追加缺少的变量，不要覆盖现有模型密钥；格式也见根目录 `.env.example`。

配置后按以下顺序补做验收：

1. 重启终端中的服务，执行 `.\run.ps1 -InspectDatabase`，确认连通和字段映射。
2. 启动 Web、启动系统，选择真实存在的主题和已映射来源。
3. 完成分析，读取报告与图谱，并按 locator 核对数据库原始记录。
4. 验证论坛轮询、停止/重启，以及结果保留。

**当前结论：Web 改造、可控环境完整流程、真实模型的完整 HTTP 分析归档流程均已通过；真实数据库闭环仍待本地凭据补齐，不能写成整套真实环境全部验收成功。**

## 7. 其他检查与范围

- Python 源码编译与前端 JavaScript 语法检查通过。
- 42 个 Python 文件均已解析，40 个非 `__main__` 模块导入成功；逐文件导读无遗漏，9 份 Markdown 的本地文档链接有效。
- 补充验证了本机无鉴权访问、空请求体启停、分块 JSON、内部异常脱敏和错误后的恢复；同一应用的两个 lifespan 周期均完成关闭。
- `uv sync --locked --extra mysql --offline` 检查通过，当前安装与锁定依赖一致。
- 文档同步更新了技术栈、逐文件导读、API、架构和启动方法。
- 测试产物位于独立临时目录，未覆盖原有报告、图谱或训练候选。
- 未进行浏览器自动化、生产压测、模型质量评分或训练效果评估。
- 未修改本地 `.env` 中的真实密钥和密码。

可重复的基础检查：

```powershell
uv sync --locked --extra mysql
.\.venv\Scripts\python.exe -m compileall -q src
node --check src/public_sentiment/static/app.js
```

目录说明见 [项目详细导读](PROJECT_STRUCTURE.md)，接口使用见 [API](API.md)，真实数据库步骤见 [数据库手册](DATABASE_WORKFLOW.md)。
