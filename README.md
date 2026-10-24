# 观潮 · 真实数据舆情分析平台

以虚拟机中的 **media_crawler** 数据库为事实来源：只读检索已爬取记录，完成主题分析、来源溯源、风险判断、Markdown 报告和证据图谱。默认配置已切换为 `database`，不再默认使用合成数据。

> 已实际连通本机 `127.0.0.1:3306` 上的 MySQL 8.0.26，并按真实结构配置抖音、微博及两张评论表。当前机器直接运行 `.\run.ps1`，按提示在本机输入数据库密码即可；本地接入与完整操作见 [本机执行指南](docs/LOCAL_DATABASE.md)。Navicat 是管理客户端，平台直接连接数据库，不经 Navicat 读取。

## 开始之前

- Python 3.12+；本机 Windows 运行平台，VM 运行数据库。
- 一个仅拥有 `SELECT` 权限的数据库账号。
- 确认数据库类型为 MySQL/MariaDB；其他引擎需调整适配器。
- 查明表结构，并配置 `database.tables`，不直接套用示例表名。

**建议按 [完整数据库执行手册](docs/DATABASE_WORKFLOW.md) 从头操作**，其中包括 VM 网络、只读账号、Navicat/SSH 隧道注意事项、时间单位、字段映射、一次分析的所有步骤和故障排查。

## 最短执行路径

```powershell
# 项目根目录，先安装依赖
uv sync --locked --extra mysql

# 请替换地址、端口、用户名；不要将密码提交或发到聊天中
$env:MEDIA_CRAWLER_DB_HOST = '你的虚拟机IP'
$env:MEDIA_CRAWLER_DB_PORT = '3306'
$env:MEDIA_CRAWLER_DB_USER = 'sentiment_reader'
$secret = Read-Host '数据库密码' -AsSecureString
$credential = [pscredential]::new('sentiment_reader', $secret)
$env:MEDIA_CRAWLER_DB_PASSWORD = $credential.GetNetworkCredential().Password

# 先查询真实表/字段，查看 suggested_tables
.\run.ps1 -InspectDatabase

# 人工确认后，将建议映射写到 config.json 的 database.tables
# 再次执行检查，应显示 configured_mappings_valid=true
.\run.ps1 -InspectDatabase

# 在同一终端启动
.\run.ps1
```

打开 **http://127.0.0.1:8000** → 配置页检查数据库 → 首页启动系统 → 主题检索输入实际存在的关键词 → 勾选已映射来源 → 开始分析 → 查看证据/报告 → 查看图谱 → 用 Navicat 按库/表/主键核对原记录 → 论坛监控 → 停止系统。

如果无法运行 PowerShell 脚本：

```powershell
$env:PYTHONPATH = "$PWD\src"
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe -m public_sentiment --inspect-database --data-dir .
.\.venv\Scripts\python.exe -m public_sentiment --data-dir . --port 8000
```

环境变量须在 Web 启动前设置；修改后需重启整个 Web，重新加载环境配置。自动读取数据目录下的 `.env`，已有进程环境变量优先。`config.json` 不存凭据。连接不成功时会明确失败，不回退示例。当前没有表映射时允许打开控制台配置，但不允许执行数据库检索。

## Web 服务：FastAPI + Uvicorn

原有 `run.ps1` 和 `python -m public_sentiment` 启动方式保持可用，内部已使用 FastAPI + Uvicorn。启动后控制台为 `http://127.0.0.1:8000`，交互式接口文档为 `/docs`，OpenAPI 描述为 `/openapi.json`，都遵守现有鉴权规则。

也可以在项目根目录直接启动 Uvicorn 工厂（先安装依赖，并在 `.env` 中补齐模型和数据库配置）：

```powershell
.\.venv\Scripts\uvicorn.exe public_sentiment.web.server:create_app --factory --host 127.0.0.1 --port 8000
```

工厂默认以当前目录为数据目录，可通过 `PUBLIC_SENTIMENT_DATA_DIR` 指定。外部监听时同时设置 `PUBLIC_SENTIMENT_HOST` 和管理员令牌。当前文件存储与任务状态只支持单实例，勿加多 worker。FastAPI lifespan 管理业务资源，阻塞型分析接口在线程池执行，SSE 使用异步长连接。直接运行 Uvicorn 不会弹出数据库密码输入框，需要提前配置环境变量。

本次迁移与验证边界见 [FastAPI 验证记录](docs/FASTAPI_VALIDATION.md)。

## 大语言模型配置

在项目根目录 `.env` 填写 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`，然后重启服务。`base_url` 填 API 根地址（通常以 `/v1` 结尾），程序追加 `/chat/completions`。密钥不要写进 `config.json`。本地无鉴权服务可把 Key 填为 `local`。

已用模型分析替换第一版词典、固定摘要及固定结论。输出经过 JSON 字段、标签、引用及原文摘录校验；无来源、模型调用或校验失败会报错。模型参数在 `config.json` 的 `llm` 部分，默认 JSON 模式，服务支持时可切换严格 `json_schema`。

每次成功分析保存待审核训练候选，可导出监督微调对话或领域续训文本。填写示例、约束协议、人工审核和导出命令见 [大语言模型与训练数据指南](docs/LLM.md)。

## 框架与能力

```text
你的爬虫 → VM 数据库 media_crawler
                   ↓ 只读查询 / 表映射 / 来源归一化
Web 控制台 → Service → 文本检索 ∥ 多媒体文字检索
                               ↓
                         情绪 / 风险 / 观点
                               ↓
                      报告生成 ∥ 证据图谱
                               ↓
                    本地归档 + SSE 实时展示
```

- 七个页面：控制台、主题检索、论坛监控、图谱、报告库、配置、系统状态。
- 五个独立 asyncio 协程工作单元：search / multimedia / insight / report / graph，支持启停、独立日志和任务状态。
- 只读数据库诊断、真实字段发现、建议映射、参数化关键词 SQL、时间归一化。
- 来源保留平台、URL、数据库名、表名、原始记录 ID；报告和图谱都可定位回原记录。
- 论坛窗口轮询及指纹去重：读取已有库，不自动启动上游爬虫，不是 CDC 全量增量同步。
- 配置热更新、报告配置快照、状态与日志实时推送、历史回查。
- 默认数据库报告列表隔离旧 demo，原有示例文件不删除，按旧编号仍可明确回查。

详细分层、模块职责、标准数据协议、权限、样本上限、部署边界和未来扩展见 [项目架构](docs/ARCHITECTURE.md)。

## 数据与方法边界

默认数据库模式只读映射表，**不会读取 examples/sources.json 或 RSS**。demo/live 作为兼容模式保留，需显式修改 collection.mode 才启用。已有示例是合成，不算真实数据验收。

数据库实际有什么类型就分析什么类型，不强行凑齐五类。图片/视频仅分析现有文字说明/字幕，不执行 OCR/ASR/视频理解。情绪、观点、风险和报告由大语言模型生成；程序限制输出字段、标签、引用和原文摘录，校验失败会终止任务。不应将小样本结果解释为总体民意。旧报告保留并标记为历史规则报告。

按标题/正文匹配空格/逗号/分号分割的任意关键词；记录按库/表/ID 去重。每表/每分支/全局有样本上限，默认 100，最大 500，截断会提示；不是全库统计。并发采集任务不是同一数据库一致性快照。建议首轮只映射 1–2 张表，小样本完成闭环后再扩展。

## 结果存储

| 位置 | 内容 |
| --- | --- |
| `config.json` | 系统、模型输出参数、表字段映射，不含凭据 |
| `runtime/apps/{app_name}.log` | 协程任务运行和错误日志 |
| `runtime/forum/latest.log` | 论坛最新日志 |
| `runtime/forum/history/{date}.json` | 逐日采集记录，包含来源定位 |
| `outputs/{app_name}/latest.txt` | 最近应用输出 |
| `reports/{report_id}/report.md` | 结构化分析报告与引用 |
| `reports/{report_id}/result.json` | 本次来源文本、分析结果与数据库 locator |
| `reports/{report_id}/config.snapshot.json` | 无凭据的配置快照 |
| `graphs/{report_id}/graph.json` | 节点、关系、引用与数据库定位 |

真实正文可能含个人信息，报告/日志目录应受文件权限保护。系统停止不删除结果；Ctrl+C 退出 Web。原始库由你的爬虫和数据库备份方案维护，本平台不建表、不迁移、不修改库数据。

## 角色与部署

默认监听 127.0.0.1，本机开发模式为管理员。可在启动前设置 `PUBLIC_SENTIMENT_ADMIN_TOKEN`、`PUBLIC_SENTIMENT_OPERATOR_TOKEN`、`PUBLIC_SENTIMENT_VIEWER_TOKEN`，浏览器使用 admin/operator/viewer 作为 Basic 登录用户名，对应令牌作密码。开启鉴权必须设置管理员令牌。

viewer 只读结果/日志/图谱；operator 可分析、单应用启停和论坛控制；admin 额外可改配置、整体启停和检查数据库结构。非本机监听必须鉴权；生产还需 HTTPS、限流、审计、备份、账号最小权限及网络隔离。适合单实例本地验证，不支持多个 Web 实例共享同一结果目录。

接口见 [API 文档](docs/API.md)。运行前可用 `node --check src/public_sentiment/static/app.js` 和 `python -m compileall -q src` 做语法检查；数据库适配器可使用模拟连接验证，真实连通性仍必须用你自己的 VM 和字段映射验收。

验证包括第一版的 19 项模拟数据库 HTTP 检查、参数化查询/时间转换/权限/不回退 demo 检查，以及当前 **HTTP + 五个 asyncio 协程工作单元 + 本地模拟模型服务** 的完整模拟分析测试，覆盖 8 条来源、报告/图谱回查、JSON 输出约束、失败重试、训练数据审核与导出、启停重启。该模拟测试未连接实际 MySQL 或真实模型服务。第一版曾用「高考」生成 100 条来源报告与图谱，并逐条回查数据库原记录，论坛实际轮询与停止后保留检查通过。Python 编译、JavaScript 语法检查通过。浏览器自动化尚未验收；第一版词典在当时样本未命中情绪词，其默认中性/低风险不构成真实情绪或风险判断，详见本机执行指南。

项目技术栈、系统设计、面试讲解提纲见 [项目技术说明与面试准备](PROJECT_OVERVIEW.md)。

逐个目录、Python 包、源码文件的职责，以及一次分析的完整调用关系，见 [项目详细导读：目录、文件与调用流程](docs/PROJECT_STRUCTURE.md)。
