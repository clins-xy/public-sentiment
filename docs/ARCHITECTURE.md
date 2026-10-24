# 项目框架与数据库接入设计

## 1. 系统边界

本平台消费你已爬取到 `media_crawler` 的数据，不接管或修改上游爬虫，不通过 Navicat 本身读数据。Navicat 是数据库客户端，真实服务可能是 MySQL、MariaDB、PostgreSQL 等。本次实现 **MySQL/MariaDB** 只读适配器；数据库类型尚需你确认。数据库名不能推断 IP、端口、认证方式或表结构，这些值不应猜测。

```text
互联网平台 → 你的爬虫 → 虚拟机 MySQL/MariaDB media_crawler
                                      ↑ 只读 SELECT / 元数据
Windows 浏览器 → Uvicorn / FastAPI → web.routes → application.Service
                                   ├─ collection：RSS / database / forum
                                   ├─ analysis：LLM client / prompt / schema / validation
                                   ├─ reporting：Markdown / evidence graph
                                   ├─ runtime：CoroutineManager → asyncio task workers
                                   └─ infrastructure.storage：reports / graphs / runtime

                         config / core → 配置与领域函数
                         runtime.EventBus → SSE 状态与日志
```

外部数据库是事实来源；文件存储是本平台分析快照、日志和结果，不回写爬虫表。默认模式 `database`，读取失败会明确失败，不会使用 demo 冒充真实数据。旧 demo 文件保留以免破坏已有结果，但当前模式列表与最新图谱不展示旧 demo。通过旧编号仍可回查原合成报告。

## 2. 代码职责

| 模块 | 责任 |
| --- | --- |
| `public_sentiment.cli` / `public_sentiment.web.server` | 命令行、FastAPI 应用工厂、Uvicorn 启动及 lifespan 资源收尾 |
| `public_sentiment.web.routes` / `schemas` / `security` | APIRouter、Pydantic 输入、ASGI 鉴权与同源检查、SSE 和静态页面 |
| `public_sentiment.application.service` | 生命周期管理、检索编排、报告落盘与回查 |
| `public_sentiment.collection` | 来源归一化、RSS/数据库采集、论坛监控 |
| `public_sentiment.analysis` | 模型客户端、提示词、Schema、输出校验与分析引擎 |
| `public_sentiment.reporting` | Markdown 报告、引用渲染与证据图谱 |
| `public_sentiment.runtime` | asyncio 事件循环、协程任务队列、状态管理与事件广播 |
| `public_sentiment.config`、`public_sentiment.core` | 配置加载/校验与共享领域函数 |
| `public_sentiment.infrastructure.storage` | 文件存储、路径限制与报告索引 |
| `public_sentiment.training` | 人工审核数据集导出 CLI |

## 3. 连接与表映射

连接参数通过 `MEDIA_CRAWLER_DB_HOST / PORT / USER / PASSWORD` 环境变量传递，`config.json` 仅存环境变量名称，不存凭据。启动时读取数据目录 `.env`，进程环境变量优先；配置会被新的协程任务读取，修改凭据后须重启 Web。不要将凭据写入 JSON 或截图/聊天。TLS 可通过 `database.ssl_ca` 配置 CA 文件启用证书与主机名校验。

先通过 `--inspect-database` 或管理员接口 `/api/database/schema` 查询 information_schema，仅返回表和字段元数据，不抽样导出正文。基于常见列名生成 **建议** 映射，人工确认后才使用；不假设你的库一定来自某个特定 MediaCrawler 版本。

一个表映射固定一个 `source_type`，通过 fields 统一到以下协议：

```text
id            ← 稳定唯一记录 ID（必选）
title/content ← 标题/正文（至少选一个；缺标题时由正文截取）
url           ← 原始网页链接（可选；绝不编造缺失链接）
author        ← 作者/昵称（可选）
published_at  ← 发布时间（可选，注意秒/毫秒/日期）
```

`id` 须在表内唯一且稳定，不要将 parent_note_id 当作评论 ID。不同表的同一 ID 不冲突：source ID 根据库名、表名和原始主键哈希生成，并保留 locator 原值。表名和列名经过标识符白名单校验；关键词参数化且转义 LIKE 通配符；只读事务 + 推荐数据库 SELECT-only 账号。程序没有数据库写入/建表/迁移代码。

source_type 为 `news / image / video / forum_post / internal_data`，平台单独保存在 platform。小红书、微博、贴吧等不能一概叫 news。某些表用 type 区分图文/视频，当前映射不支持行级类型条件，应先用只读数据库视图拆分，或明确选择统一的文字帖子分类；不要虚构未采集的媒体类型。没有的来源不必凑齐五种。

时间：支持 auto/s/ms/us/datetime；epoch 时间统一 UTC，datetime 没有时区时按 database.timezone（默认中国时区）处理。优先选真实发布时间，不要把爬取/更新时间伪装为发布时间。无法解析则保留时间未知并报告提示。

## 4. 一次分析的执行链

1. 用户提交关键词和来源；服务校验系统/应用状态和请求。
2. 固化此次完整配置（不包含环境变量值），两类检索协程并发读取匹配表。
3. 每条 SQL 按标题/正文匹配任意关键词，按发布时间/ID 降序，每表最多 N 条。
4. 各采集分支独立只读事务；并发查询**不是**全库同一时刻的一致性快照。若要严格复现，应暂停上游写入或使用数据库备份快照。
5. 归一化来源、去重，合并后全局最多 N 条，明确记录截断提示。
6. 洞察协程分批调用模型生成摘要、观点、情绪及理由、风险与原文摘录；阻塞型模型请求通过 `asyncio.to_thread()` 执行，随后校验字段、标签、来源覆盖和摘录匹配。
7. 报告和图谱并行生成，引用对应 source.reference 和 source.locator。
8. 落盘原始本次文本快照、配置、报告与图谱，归档待人工审核的训练候选并发布 graph_ready。
9. 页面展示结果，用户通过报告编号回查；可用 Navicat 按 locator 验证原记录。

max_results 为 1–500，当前为有界交互样本分析，不是全历史数仓聚合。LIKE `%词%` 在大表上可能全表扫描；上线前按实际规模增加全文检索索引或检索服务，并分析 EXPLAIN。初次可只启用 1–2 张表，将 request_timeout 设为 30，max_results 设为 50，确认查询耗时后再扩大。协程任务默认等待 120 秒；模型任务按批次数、llm.timeout 和重试次数计算等待预算。过多慢表或超大模型上下文仍可能超时，应先小样本验证。

## 5. 论坛监控与边界

forum_post 表按轮询间隔读取最近 N 条，不重复爬网。指纹由 source ID 和正文哈希构成，支持识别同一条记录的正文变化。日志保留采集来源及原始定位。高吞吐场景中，两个轮询之间超过 N 条写入可能漏掉旧项；这不是可靠 CDC/全量增量同步，也未实现跨内容/评论的父子关联推断。生产阶段可引入持久化游标、分页补偿、队列和 CDC。

现有图谱表达主题→渠道→证据→模型提取的风险说明，由程序从校验后的结果构造。媒体只分析标题、说明、字幕等已有文本；不识别图片像素或视频音轨。结构、引用存在和原文匹配校验不能证明模型推断正确，风险与结论须人工核验。模型配置、协议和微调/续训数据导出详见 [LLM 指南](LLM.md)。

## 6. 后续演进（设计，不宣称已实现）

- 存储：分析结果迁移 PostgreSQL/MySQL 元数据库，原文快照对象存储，保留数据版本与审计。
- 调度：当前已有进程内协程队列；后续增加持久化外部队列、任务进度/取消、幂等键、多主题并发和任务级失败重试。
- 检索：按平台、时间、作者过滤；全文检索或 OpenSearch；评论-帖子关系显式建模。
- 分析：已接入兼容 Chat Completions 的模型服务，保留提示词版本、原文和证据。后续使用人工审核样本评估和微调；模型返回的链接和伪引用会被拒绝。
- 多媒体：取得合法媒体文件后，再新增 OCR、ASR 与图像理解流水线。
- 运维：HTTPS、身份系统、数据库最小权限、出站网络限制、服务守护、备份和敏感字段脱敏。

本项目当前保持一个 Web 实例 + 一个 asyncio 运行时中的五个协程工作单元 + 一论坛轮询线程，适合本地验证真实数据闭环，不应直接等同于生产级分布式平台。采集、模型和报告函数仍是同步实现，运行时使用 `asyncio.to_thread()` 将阻塞调用移出事件循环；因此这是协程编排改造，不是把所有底层 I/O 都改成原生异步库。

运行时入口为 `runtime/tasks.py`。采集分支和报告/图谱分支通过 `asyncio.gather()` 编排，每个工作单元使用最多缓存 32 项的 `asyncio.Queue`。提交时深拷贝输入，避免共享可变数据；超时或取消后的迟到结果不会发布。FastAPI 同步路由由线程池执行，再通过 `run_coroutine_threadsafe()` 进入分析后台事件循环，保留现有 HTTP 接口。SSE 使用异步 `StreamingResponse`，不占用一个长期阻塞的 HTTP 请求线程。

停止工作单元时会拒绝未完成请求并清空队列，等待当前阻塞调用收尾后关闭消费者。`to_thread()` 无法强制结束运行中的线程，停止耗时受数据库/模型超时、批次与重试预算影响。整个系统关闭时还会回收事件循环的默认线程池；停止后可以重新启动。论坛轮询与 HTTP 处理仍使用线程，主题分析仍限制为同时一个请求。
