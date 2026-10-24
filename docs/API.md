# HTTP API

默认 Base URL：`http://127.0.0.1:8000`。所有 JSON 均为 UTF-8；有请求体的 POST 必须 `Content-Type: application/json`，整体启停推荐传 `{}`，也接受空请求体。请求体上限 1 MiB。开启鉴权后使用 HTTP Basic，见 README。GET 启停接口按 spec 保留，仅接受同源 fetch 或命令行调用，跨站/浏览器地址栏导航控制被拒绝。

Web 已切换为 FastAPI + Uvicorn。`GET /docs` 提供交互式 Swagger UI，`GET /openapi.json` 提供接口结构，两者均受已有鉴权保护。Swagger UI 的脚本/样式需要访问 jsDelivr；业务页面静态资源仍由本地提供。HTTP 输入由 Pydantic 校验，保持参数错误返回 400，错误对象可能额外含 `details`，不回显密钥或原始输入。

## 接口清单

| 方法 | 路径 | 请求/返回 |
| --- | --- | --- |
| GET | `/api/status` | `system_status, apps, running_apps, forum_status, recent_errors, resources, report_count, mode, time` |
| GET | `/api/start/{app_name}` | 应用启动后状态（需系统 online） |
| GET | `/api/stop/{app_name}` | 应用停止后状态 |
| GET | `/api/output/{app_name}` | `{app_name, output_text}`；无结果时空字符串 |
| GET | `/api/test_log/{app_name}` | `{app_name, log}`；协程任务运行和错误日志，最近 64 KiB |
| POST | `/api/search` | `{query, source_types}` → 完整结构化分析结果 |
| GET | `/api/forum/start` | `{status: "running"}`（需系统 online） |
| GET | `/api/forum/stop` | `{status: "stopped"}` |
| GET | `/api/forum/log` | `{status, log}`；最近 64 KiB |
| POST | `/api/forum/log/history` | `{date: "2026-10-21"}` → `{date, records}` |
| GET | `/api/config` | 完整配置对象 |
| GET | `/api/database/schema` | 管理员只读连接检查：`connected, database, configured_mappings_valid, tables, suggested_tables, notice`；只返回元数据，不返回正文 |
| POST | `/api/config` | 支持部分字段递归更新 → 校验保存后的完整对象 |
| GET | `/api/system/status` | 同 `/api/status` |
| POST | `/api/system/start` | `{}` → 启动默认应用后的状态 |
| POST | `/api/system/shutdown` | `{}` → 停止分析服务后的状态，HTTP 仍在线 |
| GET | `/api/graph/latest` | 最新图谱 `{report_id, query, created_at, nodes, edges}` |
| GET | `/api/graph/{report_id}` | 指定报告图谱 |
| POST | `/api/graph/query` | `{report_id?, node?, node_type?, relation?}` → 匹配图谱及相邻节点 |
| GET | `/graph-viewer` | 最新图谱 Web 页面 |
| GET | `/graph-viewer/{report_id}` | 指定报告图谱 Web 页面 |
| GET | `/api/reports` | `{reports: [{report_id, query, executed_at, source_count, mode, risk_level}]}` |
| GET | `/api/reports/{report_id}` | 已保存完整结构化分析结果 |
| GET | `/api/reports/{report_id}/markdown` | Markdown 附件 |
| GET | `/api/system/log` | `{log}` 最近系统日志 |
| GET | `/api/session` | `{role, authentication_enabled}` |
| GET | `/api/events` | SSE 实时消息流，15 秒心跳，支持 Last-Event-ID |

app_name：`search / multimedia / insight / report / graph`。source_types：`news / image / video / forum_post / internal_data`。query 必须 1–200 字符，source_types 不传默认全部，传入时必须非空。默认 `collection.mode=database`，查询已配置数据库映射；未配置时 409，不回退 demo。`GET /api/reports` 和最新图谱仅列出当前数据模式结果，指定 report_id 可明确回查旧模式结果。

`apps` 中的应用状态含 `execution="asyncio coroutine"`、`pending_tasks`、`started_at` 和 `last_error`；为兼容旧响应结构，应用级 `pid` 保留为 `null`，实际主进程 PID 在 `resources.pid`。停止接口会等待当前同步 I/O 收尾。`POST /api/search` 保持同步 HTTP 响应，同时只接受一个主题分析；SSE 推送运行事件，不流式传输模型 token。

## 请求示例（PowerShell）

```powershell
$base = 'http://127.0.0.1:8000'
Invoke-RestMethod "$base/api/system/start" -Method Post -ContentType 'application/json' -Body '{}'
$body = @{query='低空物流'; source_types=@('news','image','video','forum_post','internal_data')} | ConvertTo-Json
$result = Invoke-RestMethod "$base/api/search" -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
$result.report_id
Invoke-RestMethod "$base/api/graph/$($result.report_id)"
```

结果主要字段：`report_id, query, executed_at, source_types, source_count, mode, warnings, sources, sentiment, channels, negative_ratio, risk_level, method, opinions, risks, markdown, conclusion, graph_path`。

每条 source 含 `id, source_type, title, content, url, published_at, author, demo, sentiment, reference, summary, opinion, sentiment_reason, evidence_quotes, risk_level, risks, analysis_input_chars, analysis_truncated`。数据库来源额外有 `origin=database, platform, locator`；locator 为 `{database, table, primary_key_column, primary_key}`，不包含连接地址/账号/密码。数据库图谱来源节点同样保留 locator。结果额外有 provenance `{mode, database, tables, sample_limit}`。opinions / risks 通过 references 指向 source.reference；图谱节点含 `id, type, label, source_refs`，关系含 `source, target, type, source_refs`。关系类型：`propagated_via / contains / mentions_risk`。图查询的 node 对节点 ID 和 label 做不区分大小写子串匹配；node_type 精确过滤；返回相邻边及端点。

历史日志记录包含 `time, event_type, message_text, task_status`，collected 事件额外含完整 source。不存在的日期返回空 records。

模型结果额外包含 `analysis_backend=llm`、`llm={model,prompt_version}` 和 `narrative`（overview、conclusion、risk_level、risk_reason、recommendations、limitations）。情绪统计包含 `unknown`；风险项包含 `text, references, evidence_quotes`，不再包含 `matched_words`。`llm` 配置说明和训练数据导出见 `docs/LLM.md`。模型调用/校验失败返回 HTTP 409，缺少配置或没有来源返回 HTTP 400。

## 实时事件

前端使用 `EventSource('/api/events')`，按 SSE event 名监听。最近 500 条事件支持内存内回放，重启不保留；最大 12 个并发 SSE 连接。每条消息额外含 `id, type, time`。

| event | 字段 |
| --- | --- |
| app_status | app_name, status |
| app_output | app_name, output_text, stream（日志消息时） |
| forum_log | message_text, task_status, event_type，采集事件含 source |
| system_status | system_status, running_apps |
| graph_ready | report_id, graph_path |
| error | module_name, error_message |

## 状态与错误

- 应用：stopped → starting → running → stopping → stopped；异常退出为 failed，可再次启动。
- 系统：offline → starting → online → shutting_down → offline；启动失败回滚已启动应用。
- 论坛：idle / running / stopped / failed。
- 风险：high / medium / low / unknown；最后一项表示模型无法判断；没有匹配来源时分析会报错。
- 错误结构：`{"error": "可读错误信息"}`。
- HTTP 400：参数、路径标识、日期、JSON 或配置无效；401：未登录；403：角色不足或跨站控制；404：资源不存在；409：服务/应用未运行、分析忙或执行失败；500：未预期错误；503：实时连接已满。

配置不接受未知字段；数值范围：max_results 1–500、request_timeout 1–60 秒、forum_interval 2–3600 秒、llm.timeout 1–600 秒、llm.batch_size 1–20、llm.max_retries 0–2。更新只在完整校验通过后原子保存，失败不改变原配置。apps 默认开关在下次整体启动时使用，其他配置在新任务/下一轮论坛采集时使用。
