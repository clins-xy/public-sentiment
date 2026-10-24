# 项目详细导读：目录、文件与调用流程

> 依据本项目 2026-10-23 的代码编写。本文解释“代码在哪里、每个文件做什么、它们怎样配合”，适合初次阅读和面试复习。不把设计设想、历史测试记录当成当前已实现的能力。

## 1. 先用一句话理解项目

这是一个带网页控制台的舆情分析应用：**读取已有数据 → 筛选并统一格式 → 调用大语言模型分析 → 校验模型输出 → 生成可追溯的报告和图谱 → 保存结果并在网页展示。**

可以把它想成一间工作室：

| 部分 | 通俗比喻 | 实际工作 |
| --- | --- | --- |
| `web/` 与 `static/` | 接待窗口 | 接收用户操作、返回接口结果、展示页面 |
| `application/` | 项目经理 | 决定一次分析先做什么、后做什么 |
| `collection/` | 资料员 | 从已有数据库、文件或 RSS 中找资料 |
| `analysis/` | 分析员及质检员 | 请求模型分析，再检查答案是否满足约束 |
| `reporting/` | 编辑与制图员 | 整理报告、构造证据关系图 |
| `runtime/` 代码包 | 调度员 | 管理协程任务、状态和事件通知 |
| `infrastructure/` | 档案管理员 | 统一读写本地文件 |
| `config/` | 设置与检查清单 | 提供默认配置、加载环境变量、检查参数 |
| `core/` | 共用工具箱 | 提供来源类型、文本处理、时间和编号工具 |
| `training/` 代码目录 | 数据整理员 | 把人工审核过的候选记录导出为训练数据 |

**当前模型接入方式是调用兼容 Chat Completions 的 HTTP 服务，不是在项目里加载模型权重。** 训练目录提供的是数据准备功能，不是已经实现了模型微调。

## 2. 先分清目录、包和模块

- **目录**就是文件夹，可能装代码，也可能装报告、日志或配置。
- **Python 包**用于组织可导入的模块，通常有 `__init__.py`。
- **Python 模块**一般就是一个 `.py` 文件，例如 `analysis/client.py`。
- **`__init__.py`**用于包初始化；本项目多数此类文件仅说明包的职责，没有启动服务的行为。
- **`__main__.py`**是通过 `python -m 包名` 运行时的入口，与普通导入不是一回事。
- Python 也支持没有 `__init__.py` 的命名空间包。本项目的 `src/public_sentiment/training/` 就没有这个文件，但有实际导出模块和模块运行入口。

### 最容易混淆的两组同名目录

| 路径 | 装的是什么 | 不是什么 |
| --- | --- | --- |
| `src/public_sentiment/runtime/` | 协程调度和事件通知代码 | 运行日志目录 |
| 根目录 `runtime/` | 启停状态、日志、最新报告指针 | Python 调度包 |
| `src/public_sentiment/training/` | 训练数据导出代码 | 模型权重或训练样本库 |
| 根目录 `training/` | 候选数据和后续导出的数据集 | Python 业务包 |

后文写代码路径时，以 `src/public_sentiment/` 为起点；写数据目录时，会明确标注“根目录”。

## 3. 项目目录总览

下面列出项目自有源码和主要目录。重复生成的报告编号、日期目录只用模板表示，不逐份列举。

```text
public-sentiment/
├── README.md                       快速使用说明及文档入口
├── PROJECT_OVERVIEW.md              技术栈、设计取舍、面试讲解
├── 舆情分析.md                     原始需求和设计材料
├── pyproject.toml                   Python 版本、依赖、打包和启动命令
├── uv.lock                          已解析的依赖版本，用于复现安装
├── run.ps1                          Windows 启动与数据库检查脚本
├── config.json                      本地业务配置
├── .env                             本地密钥等环境配置，不应公开
├── .env.example                     环境配置填写模板
├── .gitignore                       版本控制忽略规则
├── docs/
│   ├── PROJECT_STRUCTURE.md         本文：目录与文件详细导读
│   ├── ARCHITECTURE.md              架构和模块边界
│   ├── API.md                       HTTP 接口说明
│   ├── FASTAPI_VALIDATION.md         FastAPI 改造范围与本次验证记录
│   ├── LLM.md                       模型接入、输出约束与数据导出
│   ├── DATABASE_WORKFLOW.md         数据库接入完整流程
│   └── LOCAL_DATABASE.md            本机数据库执行记录与注意事项
├── examples/
│   ├── sources.json                合成来源数据示例
│   └── database.tables.example.json 数据库表与字段映射示例
├── src/
│   └── public_sentiment/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── application/
│       │   ├── __init__.py
│       │   └── service.py
│       ├── collection/
│       │   ├── __init__.py
│       │   ├── collector.py
│       │   ├── database.py
│       │   ├── feeds.py
│       │   └── forum.py
│       ├── analysis/
│       │   ├── __init__.py
│       │   ├── client.py
│       │   ├── engine.py
│       │   ├── prompts.py
│       │   ├── schemas.py
│       │   └── validation.py
│       ├── reporting/
│       │   ├── __init__.py
│       │   ├── report.py
│       │   ├── graph.py
│       │   └── rendering.py
│       ├── runtime/
│       │   ├── __init__.py
│       │   ├── tasks.py
│       │   └── events.py
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   └── storage.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── defaults.py
│       │   ├── environment.py
│       │   ├── validation.py
│       │   ├── database.py
│       │   └── llm.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── constants.py
│       │   ├── sources.py
│       │   └── utils.py
│       ├── training/
│       │   ├── __main__.py
│       │   └── export.py
│       ├── web/
│       │   ├── __init__.py
│       │   ├── server.py
│       │   ├── routes.py
│       │   ├── schemas.py
│       │   └── security.py
│       └── static/
│           ├── index.html
│           ├── app.js
│           └── style.css
├── outputs/                        各工作单元最新输出
├── reports/                        按报告编号保存的分析档案
├── graphs/                         按报告编号保存的图谱 JSON
├── runtime/                        运行状态、事件相关日志、论坛记录
├── training/                       待审核训练候选及导出结果
├── .idea/                          本地 IDE 设置，不参与业务
└── .venv/                          本地 Python 环境，不是业务源码
```

`src/` 是源码的容器，真正导入的顶层包是 `public_sentiment`。采用这种布局可以把业务代码与根目录的数据、文档、环境文件分开。

## 4. 根目录文件逐个说明

| 文件 | 用简单的话说明 | 什么时候会用到 |
| --- | --- | --- |
| `README.md` | 项目的快速入门，告诉你怎么启动、配置和查文档 | 第一次运行项目 |
| `PROJECT_OVERVIEW.md` | 从技术栈、系统设计和面试角度解释项目 | 准备自我介绍和技术问答 |
| `舆情分析.md` | 最初想做什么、希望有哪些能力的需求材料 | 回顾需求；其中设想不能直接算作已实现功能 |
| `pyproject.toml` | 告诉 Python 工具项目名、版本、依赖及启动入口 | 安装、打包、查看技术栈 |
| `uv.lock` | 锁定已解析的依赖版本 | 使用 `uv sync --locked --extra mysql` 复现环境 |
| `run.ps1` | 把设置路径、加载环境、选解释器、启动程序串成一步 | Windows 下启动服务、演示或检查数据库 |
| `config.json` | 保存采集模式、表映射、模型参数、应用开关等非密钥设置 | 调整业务行为 |
| `.env` | 保存本机 API Key、模型地址、数据库密码等环境变量 | 接入自己的模型和数据库；不要提交或发给别人 |
| `.env.example` | 展示环境变量名称和填写方式，不是实际密钥 | 新机器初始化配置 |
| `.gitignore` | 告诉 Git 哪些文件不该默认跟踪 | 管理版本，避免提交环境和生成数据 |

### 4.1 `pyproject.toml` 中的真实技术栈

- Python 要求为 **3.12 及以上**，项目版本为 `0.1.0`。
- Web 使用 **FastAPI + Uvicorn**：FastAPI 提供 ASGI 应用与路由，Uvicorn 负责监听和服务连接。
- HTTP 请求模型由 Pydantic 校验；模型生成内容仍用项目自有 Schema 和证据校验器约束。
- 协程调度使用标准库 `asyncio`；阻塞任务通过线程池衔接。
- HTTP 模型调用和 RSS 读取使用标准库 `urllib`，JSON 使用 `json`。
- MySQL 连接使用可选依赖 `PyMySQL[rsa]`；数据库模式需要安装 `mysql` 这组额外依赖。
- 前端是原生 HTML、CSS、JavaScript，没有 React/Vue 构建链。
- 打包后提供 `public-sentiment` 命令，指向 `public_sentiment.cli:main`；构建后端是 `uv_build`。

### 4.2 `config.json` 各部分管什么

| 配置段 | 管理内容 | 通俗理解 |
| --- | --- | --- |
| `system` | 系统名称、自动启动、结果数量和请求超时等 | 整个系统的总开关和基本限制 |
| `collection` | `database` / `demo` / `live` 模式、RSS、内部文件、论坛间隔 | 去哪里找资料 |
| `database` | 数据库名、环境变量名、时区、TLS 和表字段映射 | 数据库里哪些表、哪些列代表标题和正文 |
| `llm` | 模型地址/名称的配置及环境变量名、输出格式、超时、重试、分批大小等 | 怎样给模型发请求、最多发多少资料 |
| `apps` | 五个工作单元的启用状态 | 哪些处理环节允许运行 |

**配置文件写“规则”，环境变量保存“凭据”。** `config/database.py` 和 `collection/database.py` 职责不同，前者检查规则，后者才真正连接数据库。

### 4.3 API Key 和模型地址到底填写在哪里

在项目根目录 `.env` 中填写，以下仅为格式示意，不是真实凭据：

```dotenv
LLM_API_KEY=replace-with-your-api-key
LLM_BASE_URL=http://127.0.0.1:8001/v1
LLM_MODEL=replace-with-your-served-model-name
```

- `LLM_API_KEY`：模型服务密钥；当前客户端要求提供。自建无鉴权服务也需要填入服务允许的占位值。
- `LLM_BASE_URL`：API 根地址。客户端会追加 `/chat/completions`，不要把完整接口地址重复写进去。
- `LLM_MODEL`：服务端实际提供的模型标识，不是随意填写的显示名称。
- `config.json` 的 `llm.api_key_env` 等字段指定“到哪个环境变量里找值”，不是让你把密钥写进这些字段。
- 对模型地址和名称，客户端优先使用对应环境变量，未设置时读取配置值；API Key 从指定环境变量读取。
- `.env` 不覆盖已存在的进程环境变量。修改后应重启整个 Web 服务，而不只是刷新页面。

`run.ps1` 会优先使用 `.venv` 的 Python，并设置源码搜索路径。数据库模式下脚本会处理连接变量，缺少密码时可交互输入，不会替你把密码写回配置文件。实际部署应使用只读、最小权限数据库账户，不要把本地启动脚本的便利默认值当作生产安全配置。

## 5. 顶层 Python 包：程序从哪里启动

### `src/public_sentiment/__init__.py`

它是顶层包的入口说明文件，还提供一个很薄的 `main()` 包装函数：需要启动时，才导入并调用 `cli.main()`。**单纯 `import public_sentiment` 不会自动启动网页服务。**

### `src/public_sentiment/__main__.py`

它负责响应 `python -m public_sentiment` 这类运行方式，再转交给 `cli.main()`。可以理解成“模块运行方式的门铃”，真正处理启动工作的是下一个文件。

### `src/public_sentiment/cli.py`

这是总启动入口，`main()` 主要做这些事：

1. 读取命令行参数，例如监听地址、端口、数据目录、演示和数据库检查模式。
2. 加载环境变量；若是数据库检查模式，就检查结构、输出结果，而不启动完整 Web 服务。
3. 处理管理员、操作员、只读用户的访问令牌；非本机监听要求开启鉴权。
4. 通过 `create_app()` 创建 FastAPI 应用，用 Uvicorn 配置启动 `ConsoleServer`。
5. ASGI lifespan 在启动时创建 `Service`，退出时关闭工作单元和相关资源；服务端负责信号与连接收尾。

默认地址是 `127.0.0.1`、端口 `8000`；`--data-dir` 决定配置和结果保存到哪个目录。`--demo` 是演示数据模式入口，**不是用固定回复代替模型**，分析仍需要可用的模型配置。

它不写分析算法，不负责拼 SQL，也不直接编排报告细节，只负责“把整个应用启动起来”。

## 6. `application/`：一次业务的总协调者

### `src/public_sentiment/application/service.py`

核心类是 `Service`。把它当作“项目经理”：网页告诉它用户想分析什么，它再把工作分给资料员、分析员和报告编辑。

| 主要方法 | 作用 |
| --- | --- |
| `start_system()` / `shutdown()` | 启停系统和工作单元 |
| `start_app()` / `stop_app()` | 单独启停某个工作单元 |
| `status()` | 汇总系统、工作单元和论坛状态 |
| `update_config()` | 检查并保存新的业务配置 |
| `search()` | 执行一次完整的主题分析，是核心业务入口 |
| `get_report()` / `reports()` | 读取某份报告、列出历史报告 |
| `graph()` / `query_graph()` | 读取图谱，按节点或关系筛选 |
| `record_error()` | 记录错误，方便界面展示和排查 |

`search()` 接收主题词和来源类型，先检查系统状态、工作单元、模型配置，再执行“采集 → 分析 → 报告与图谱 → 保存”。当前通过锁限制为**同一时间一个完整主题分析**，并不是所有用户的分析都无限并发。

它还把同一次任务使用的配置保存为快照，防止以后修改设置后不知道旧报告当时用了什么参数。报告列表默认按当前数据模式过滤，避免把旧演示结果误当作真实数据分析。

**输入**：页面提交的主题和来源类型。**输出**：含报告编号、来源、分析、报告正文、图谱路径等信息的结果字典。它调用其他包完成工作，不代替那些包的专业职责。

## 7. `collection/`：资料从哪里来

这个包的目标是“拿到已有资料”，不是训练模型，也不是运行上游爬虫。

### `src/public_sentiment/collection/collector.py`

`collect(payload)` 是采集总入口，按 `collection.mode` 选择路线：

| 模式 | 读取位置 | 重要区别 |
| --- | --- | --- |
| `database` | 配置映射的 MySQL 表 | 不读取示例或 RSS，失败不悄悄切换演示数据 |
| `demo` | 配置的示例/内部文件 | 允许使用带演示标记的合成来源 |
| `live` | 内部文件与配置的 RSS | 不等于自动运行上游爬虫 |

它会调用来源归一化工具、筛选主题、按编号去重、按时间排序并限制数量，再返回 `sources` 和 `warnings`。内部 JSON 文件还会检查路径和大小，避免随意读取项目外文件或一次读入过大的内容。

非数据库采集中，多个 RSS 可通过小型线程池并行读取。这个局部实现与协程调度并不矛盾：调度管理任务，具体处理函数仍可能使用线程完成阻塞读取。

### `src/public_sentiment/collection/database.py`

这是**真正访问数据库**的适配器。它把“不同网站、不同表结构”的记录变成系统认识的统一来源。

- `connection_options()` / `connect()`：从配置和环境变量取得连接信息，建立 MySQL 连接；需要时启用 TLS。
- `inspect_database()`：读取数据库元信息，查看实际表和列。
- `suggest_mapping()`：根据字段候选名称给出映射建议；建议不会自动写进你的配置。
- `validate_mappings()`：核对映射指向的表、列是否真实存在。
- `query_table()`：构造受限制的查询，关键词值使用参数传递，不直接拼接用户输入。
- `parse_time()`：处理日期、秒/毫秒/微秒时间戳，并统一时间表示。
- `collect_database()`：汇总映射表的来源，交给后面的分析流程。

通俗例子：某张表的正文列叫 `content`，另一张叫 `desc`。通过映射，两者对外都变成来源对象的 `content`，模型分析层就不用知道上游用了哪种列名。

每条数据库来源还带 `locator`，记录数据库名、表名、主键列和主键值。这样报告中的证据能回查到原记录。它是定位信息，不代表系统把原表复制成了自己的业务数据库。

这里采用只读查询，不负责建表、迁移、写回原始数据；实际权限仍应由数据库只读账户约束。标题、正文及可选的上游主题字段可用于匹配，但“采集主题词命中”不等于“正文提及”，报告需要保留这种区别。

### `src/public_sentiment/collection/feeds.py`

`read_feed()` 读取 RSS/Atom，使用 XML 解析提取标题、链接、时间和描述等，再交给统一来源格式处理。

`validate_public_url()` 和重定向处理器会检查访问目标，限制直接访问不合适的内网等地址，并重新检查重定向。它们是网络访问的防护措施，不应夸大为完全消除所有网络风险。

这个文件不下载图片做识别，也不提取视频语音；只能使用数据里已有的文字信息。

### `src/public_sentiment/collection/forum.py`

核心类 `ForumMonitor` 是论坛监控器：启动后按间隔读取论坛类型来源，比较记录编号和正文指纹，把本轮发现的变化保存为状态、日志和按日期划分的历史记录，并发布通知。

它使用独立轮询线程，**不是五个协程工作单元之一**。它不会因为每次轮询发现帖子就自动调用模型生成完整报告，也不是数据库 CDC 或保证不遗漏的全量增量同步系统。

**输入**：采集配置及轮询间隔。**输出**：论坛状态、发现记录、监控日志和通知事件。

## 8. `analysis/`：模型分析与答案检查

最容易记的关系是：**`engine` 组织资料，`prompts` 说明要求，`schemas` 提供表格，`client` 发给模型，`validation` 检查回填答案。**

### `src/public_sentiment/analysis/engine.py`

`analyze()` 是分析阶段的业务函数。它给来源分配 `S1`、`S2` 等引用编号，按配置分批整理证据，调用 `LLMClient`，再合并逐条情绪、摘要、观点和风险。

模型并不负责随意报统计数：情绪数量、渠道数量、负向比例等由程序根据校验通过的逐条结果计算。这样能减少“模型文字说有十条，实际只有八条”的不一致。

默认每批 5 条、每条最多送入 6000 字符，这些是可调整的默认值，不是固定规则。各批当前顺序执行，不是同时发出大量模型请求。超出的内容会截取并标记；采集归一化本身也有长度上限，因此不能声称模型分析了数据库中无限长度的完整原文。

**输入**：统一来源、主题和配置。**输出**：带逐条分析的来源列表、观点、风险、统计信息，以及启用采集时的训练候选记录。

### `src/public_sentiment/analysis/client.py`

`LLMClient` 是项目与模型服务之间的“电话”：读取模型配置和密钥，通过 `urllib` 发出 HTTP 请求，解析返回的 JSON。它不决定网页布局，也不连接业务数据库。

`generate()` 组织系统要求、证据和输出 Schema；`request()` 负责网络请求。文件还提供 `task_timeout()`，按分析规模估算阶段等待时间。

主要行为包括：

- 在根地址后追加 `/chat/completions`；环境变量可覆盖模型地址与名称。
- 支持 `json_object`，服务端支持时可选严格 `json_schema`。
- 对部分网络异常、限流和服务端错误做有限重试，而非无限等待。
- 输出不是合法 JSON 或不满足约束时，可进行有限次数的纠正请求。
- 最终仍不合法则明确失败，不用固定“分析成功”文本掩盖错误。
- 开启训练候选采集时，记录提示词、证据、输出、Schema、版本、模型及用量等，并默认标记未审核。

**这里是找 API Key 与 `base_url` 实际使用位置时最关键的文件。** 它实现的是兼容接口调用，不是某家模型 SDK，也不是训练引擎。

### `src/public_sentiment/analysis/prompts.py`

保存 `SYSTEM_PROMPT` 和 `PROMPT_VERSION`。可以把它理解成“给模型的工作说明”：只依据给定证据、信息不足时承认未知、资料中的指令不应被当成系统指令、只返回约定 JSON、摘录要来自原文。

想改变分析角度或表达要求，先看这里；但只改提示词不能替代程序校验。提示词版本还用于判断训练候选是否适合当前导出协议。

### `src/public_sentiment/analysis/schemas.py`

用字典定义模型必须填写的结构，例如 `ANALYSIS_SCHEMA`、`REPORT_SCHEMA`，以及风险、单条来源、带引用文本等子结构。

它规定字段名、必填项、类型、数量/长度、情绪与风险的允许取值，限制额外字段。把它想成“设计好的空白表格”，不是填写结果，也不是数据库建表文件。

### `src/public_sentiment/analysis/validation.py`

它是“质检员”：`validate_shape()` 检查结构，`validate_analysis()` 检查逐条分析，`validate_report()` 检查报告叙述。

- 字段、类型、长度和枚举值必须符合定义，不能随意增加字段。
- 来源分析要与输入引用对应，不能漏掉或重复某条来源。
- 原文摘录必须能在给定标题或正文中找到；报告引用必须指向已有来源。
- 对中高风险要求相应风险证据；限制模型自行生成链接和内嵌伪引用。

**Schema 是表格设计，validation 是检查填表是否合格，两者不是重复工作。** 校验能约束格式和部分证据一致性，不能证明所有推断都正确，也不能彻底消除幻觉或提示注入，需要保留人工审核。

## 9. `reporting/`：报告与证据图谱

### `src/public_sentiment/reporting/report.py`

`build_report()` 接收逐条分析和程序统计，再调用模型生成报告层面的概况、风险理由、结论和建议。它使用的是已经整理的分析证据，不是把每条完整原始正文再次无差别提交。

模型叙述通过 `REPORT_SCHEMA` 校验后，程序把它与时间线、渠道计数、逐条证据、数据库定位信息组合为 Markdown，追加规范的 `[S1]` 引用，并进行文本转义。

主要章节包括事件概况、时间线、传播渠道、主要观点、情绪倾向、风险判断、重点证据、结论摘要、建议和方法局限。**报告中的统计由程序计算，综合文字由模型归纳，排版由程序完成。**

**输入**：分析结果与配置。**输出**：Markdown 正文、综合风险等级、结论、结构化叙述及可能的训练候选。

### `src/public_sentiment/reporting/graph.py`

`build_graph()` 从已校验的逐条分析构造节点和关系，例如：

```text
主题 → 来源渠道 → 来源记录 → 相关风险
                       └─ 引用编号、原始记录定位
```

它用程序规则构图，不再调用一次模型。节点和关系保存成 JSON，由网页读取和展示。图谱可以与报告生成并行，因为它依赖来源分析，不需要等待报告层的综合风险判断。

这不是 Neo4j 数据库，也没有自动实现 GraphRAG；这里“图谱”主要指可追溯的证据关系结构。

### `src/public_sentiment/reporting/rendering.py`

包含 `markdown_text()` 和 `cited()` 两个辅助函数，用于转义 Markdown 文本和拼接引用。

**当前代码中，它没有接入报告主调用链。** `report.py` 内部还定义了同名的本地函数，实际报告调用的是那一份。因此这个文件应理解为尚未复用的辅助代码，不能写成“报告生成时必经的渲染模块”。本文仅如实说明，不在文档任务中顺带删除或重构它。

## 10. `runtime/` 代码包：协程怎样安排工作

### `src/public_sentiment/runtime/tasks.py`

这是协程执行框架。先看工作单元与实际业务函数的对应关系：

| 工作单元 | 实际执行的函数 | 职责 |
| --- | --- | --- |
| `search` | `collection.collector.collect()` | 检索非图片/视频类型资料 |
| `multimedia` | `collection.collector.collect()` | 检索图片/视频记录中已有的文字资料 |
| `insight` | `analysis.engine.analyze()` | 调用模型完成逐条分析与汇总 |
| `report` | `reporting.report.build_report()` | 调用模型归纳并整理报告 |
| `graph` | `reporting.graph.build_graph()` | 通过程序规则构造证据图谱 |

注意：`search` 在这里指一个采集工作单元；`Service.search()` 则是一次完整业务流程的入口，名字相似但职责不同。`multimedia` 也不是多模态识别模型，它只负责已有文字。

三个核心类可这样理解：

| 类 | 通俗比喻 | 负责什么 |
| --- | --- | --- |
| `AsyncRuntime` | 共用工作场地 | 在后台线程维护一个事件循环，为同步 HTTP 代码提供提交协程的桥梁 |
| `CoroutineWorker` | 单个工作岗位 | 管理自己的队列、运行状态、结果、日志、超时和启停 |
| `CoroutineManager` | 岗位管理员 | 创建五个工作单元，提交单组/多组任务，统一停止 |

具体过程是：先把任务放进该工作单元的 `asyncio.Queue`，消费者取出任务，再通过 `asyncio.to_thread()` 执行现有同步处理函数，把结果交回等待者。队列容量为 32，表示等待队列的容量限制，不等于允许 32 个完整主题分析同时执行。

任务提交时会深拷贝输入，避免调用方后来改动字典影响排队任务。多个独立阶段通过 `asyncio.gather()` 一起等待；同组出现失败时会处理其他等待任务的取消。

超时和停止也有边界：过期的排队任务会跳过，已启动的同步网络/数据库处理不能靠取消协程强制杀掉，仍需等待底层调用按超时返回。停止时会清理待处理请求并处理正在执行的任务。

**当前架构是“协程调度 + 必要的线程”，不是纯异步、零线程。** Uvicorn 使用 ASGI 事件循环接收连接，同步路由由线程池执行；分析运行时另有后台事件循环线程，阻塞调用使用线程池，论坛也有轮询线程；不应在面试中说成五个独立进程或所有 I/O 都已原生异步化。

### `src/public_sentiment/runtime/events.py`

核心类 `EventBus` 是本进程内的通知板。其他模块通过 `publish()` 写入“状态变化、任务输出、图谱就绪”等事件，Web 端通过 `since()` 读取某个编号之后的通知。

内部使用带条件变量的内存队列，最多保留最近 500 条事件。没有新事件时可以等一会儿，减少无意义查询。进程重启后这段事件历史不保留。

它不是 Redis、RabbitMQ 或跨进程消息系统。网页通过 SSE 收到的是这些状态事件，不是模型逐字生成的 token 流。

## 11. `infrastructure/`：统一文件读写

### `src/public_sentiment/infrastructure/storage.py`

`Storage` 集中管理“从哪个目录读、怎样安全地写”，避免业务文件到处自行打开路径。

- `path()`：把相对路径解析到数据根目录，并检查是否越界。
- `get_config()` / `update_config()`：读取、合并、检查和保存配置。
- `read_json()` / `write_json()`：统一 JSON 文件读写，缺失文件可使用指定默认值。
- `read_text()` / `write_text()`：读写文本；写入时使用临时文件替换，减少单文件写了一半的风险。
- `append()` / `tail_text()`：追加日志、读取日志尾部，避免界面直接加载巨大日志。
- `reports()`：读取已归档报告的摘要，并支持按数据模式筛选。

它同时为配置、报告、图谱、论坛记录、训练候选提供存储服务。虽然名字叫“存储”，当前实现是本地文件，不是 ORM、数据库连接池或对象存储。

单个文件的原子替换也不等于整份报告的多个文件拥有数据库事务；部署时还需要考虑磁盘权限、备份与中途失败处理。

## 12. `config/`：读配置和查配置，不做业务请求

### `src/public_sentiment/config/defaults.py`

`DEFAULT_CONFIG` 提供程序出厂设置，例如默认数据库采集模式、样本数上限、论坛轮询间隔、模型超时和批次大小，以及五个工作单元开关。

它是“默认设置说明书”，不应放真实密钥。最终生效配置还会结合本地 `config.json`，模型客户端另外读取指定环境变量。

### `src/public_sentiment/config/environment.py`

`load_env(root)` 从数据目录下读取 `.env`，支持空行、整行注释、`NAME=value` 和成对引号，检查变量名和引号是否有效。

使用 `os.environ.setdefault()`，因此系统/进程已经设置的变量优先。它不是完整 Shell，不会执行命令，也不支持把任意脚本写进去自动运行。排查“改了 `.env` 仍没生效”时，除了重启，还应检查已有环境变量是否覆盖了它。

### `src/public_sentiment/config/validation.py`

`merge_config()` 把用户配置合并到默认配置，拒绝不认识的配置项；`validate_config()` 检查整体结构、开关、采集模式、数量限制等，再调用数据库和模型的专门校验。

可以理解成“检查设置表是否填对”，而不是测试远端服务真的可连。参数合法与数据库/模型在线，是两件不同的事。

### `src/public_sentiment/config/database.py`

`identifier()` 和 `validate_database()` 约束数据库、表、字段映射等配置格式，检查允许的字段名、环境变量名及时间设置。

**它不会连接 MySQL。** 真正读取元信息和查询记录的是 `collection/database.py`。前者偏“配置检查”，后者偏“访问数据”，同名不意味着重复实现。

### `src/public_sentiment/config/llm.py`

`validate_llm_config()` 检查模型参数、输出格式、批次大小、重试、超时和环境变量名；`validate_base_url()` 检查服务根地址格式，限制不合适的凭据、查询串或片段等。

它负责发现“填错格式”，不是调用模型进行连通性测试。真正发出请求的是 `analysis/client.py`。

## 13. `core/`：所有模块共用的小工具

这个包尽量只提供共同概念和轻量处理，不承担 Web、模型和数据库业务。

### `src/public_sentiment/core/constants.py`

保存统一名称和允许值，包括五个工作单元名称、来源类型、中文标签、情绪与风险标签。

当前来源类型为 `news`、`image`、`video`、`forum_post`、`internal_data`。集中定义后，页面/API/分析就不会各写一套拼写不同的名字。

### `src/public_sentiment/core/sources.py`

- `plain_text()`：把 HTML 等原始文本整理成较干净的纯文本。
- `matches()`：判断资料是否匹配主题关键词。
- `normalize_source()`：把输入记录整理成统一的编号、类型、标题、正文、链接、作者和发布时间等字段。

标题与正文有长度保护，归一化正文最多保留 10000 字符；模型输入还可能按 `llm.max_chars_per_source` 进一步截取。缺少可用编号时，可用稳定哈希产生编号，方便后续去重和追溯。

因此，“采集保存的来源文本”和“模型实际看到的片段”要分清，也不能把归一化后的文本等同于数据库无限长的原始字段。

### `src/public_sentiment/core/utils.py`

`now()` 提供统一时间字符串；`safe_id()` 只允许符合约束的编号，用于报告、图谱等路径处理。

例如读取 `reports/{report_id}/result.json` 前先检查编号，就能阻止把任意路径直接当成报告编号使用。这是路径防护的一环，不是普通字符串美化。

## 14. `training/` 代码目录：为后续微调和续训准备数据

### `src/public_sentiment/training/export.py`

`export_training()` 读取根目录 `training/candidates/`，把人工审核通过的候选导出为数据集。

导出前不是只检查一个开关，而是会做这些事：

1. 候选文件的 `reviewed` 必须为 `true`，被选中的 sample 也必须标为已审核。
2. 核对提示词版本、消息格式、Schema 和模型输出，重新检查证据约束。
3. 对重复内容进行去重。
4. 按归一化主题的哈希划分训练集/验证集，减少同主题样本跨集合出现的机会；默认验证比例为 10%，不是保证小数据集恰好每十条抽一条。
5. 保存训练集、验证集和带来源信息的清单。

支持两类导出：

| `--format` | 导出内容 | 对应后续用途 |
| --- | --- | --- |
| `chat` | system/user/assistant 对话，assistant 是审核通过的 JSON 输出 | 为监督微调准备输入与标准答案 |
| `corpus` | 分析阶段使用的证据标题与正文，不把报告叙述当原始语料 | 为领域文本续训准备候选语料 |

导出的语料受采集和模型输入截取影响，不是自动导出全量数据库。`manifest.json` 记录来源和哈希等追溯信息，不是训练后的模型配置。

`main()` 提供命令行参数，比如数据目录、输出目录、数据格式和验证集比例。没有审核通过的数据会报错，不会把未审核模型回答直接当作训练标准答案。

### `src/public_sentiment/training/__main__.py`

把 `python -m public_sentiment.training` 转交给 `export.main()`。这是一条数据导出命令，不会启动 GPU 训练。

示例调用如下，前提是已安装项目或设置好 `PYTHONPATH`，并完成候选数据审核：

```powershell
.\.venv\Scripts\python.exe -m public_sentiment.training --data-dir . --format chat
.\.venv\Scripts\python.exe -m public_sentiment.training --data-dir . --format corpus --output-dir training/corpus-export
```

该目录当前没有 `__init__.py`，属于可用的隐式命名空间子包，不需要为解释目录结构而虚构一个文件。

**当前已实现的是候选采集、审核门槛和导出。** 真正的 LoRA/全参数训练、训练框架、GPU 调度、评测与模型部署不在这两个文件中。

## 15. `web/`：把网页请求交给业务层

### `src/public_sentiment/web/server.py`

`create_app()` 是 FastAPI 应用工厂：组合路由、静态资源、安全中间件和异常处理。它通过 ASGI lifespan 在启动时创建 `Service`，退出时在线程池中关闭业务资源，避免导入模块就启动业务。

`ConsoleServer` 现在继承 `uvicorn.Server`，不再是标准库 HTTP 服务器。它在收到退出信号时先通知 SSE 结束，再由 Uvicorn 完成关闭，避免长连接拖住正常退出。

### `src/public_sentiment/web/routes.py`

这里使用 `APIRouter` 明确定义接口，相当于“接待窗口的业务目录”。页面、主题分析、报告、图谱、配置、工作单元、论坛和 SSE 分别有对应函数；普通同步接口由 FastAPI 在线程池执行，避免把 `Service.search()` 等阻塞调用直接放进 Web 事件循环。

SSE 使用异步生成器和 `StreamingResponse`，定期检查事件与连接状态；连接结束会释放名额。它仍推送状态通知，不是模型 token 流。

### `src/public_sentiment/web/schemas.py`

这里是 Pydantic 请求模型：`SearchRequest` 约束主题与来源类型，`GraphQueryRequest` 约束图查询字段，`ForumHistoryRequest` 约束日期格式。输入字段会出现在 OpenAPI 文档里，不认识的字段和不合适的类型会被拒绝。

它校验的是“用户发来的请求”，不要与 `analysis/schemas.py` 的“模型必须返回的答案结构”混淆。配置更新仍交给既有配置校验器把关。

### `src/public_sentiment/web/security.py`

`load_tokens()` 检查令牌与监听要求，`authenticate()` 检查 Basic 凭据，`ConsoleMiddleware` 统一检查 Host、角色、同源控制、JSON 请求类型和 1 MiB 大小限制，并追加安全响应头、写访问日志。

它使用原生 ASGI 中间件，不把长连接封装成一次性 JSON 请求。密钥仍留在服务端环境变量，不会因为换成 FastAPI 就传到前端。

### 四个文件怎样配合

`server.py` 组装应用，`security.py` 先检查访问条件，`schemas.py` 校验请求参数，`routes.py` 再把业务交给 `Service`。前端 URL 和主要返回字段保持兼容；新增 `/docs` 与 `/openapi.json`，也受到访问控制。

主要工作包括：

- 返回页面外壳及 `static/` 中的 JavaScript、CSS。
- 处理主题分析、报告查询、图谱读取/筛选、配置、系统启停、论坛记录和日志等接口。
- 根据 viewer/operator/admin 角色限制操作，并检查请求来源等。
- 把参数错误、找不到资源、运行状态冲突及内部异常转换为相应响应。
- 通过 `/api/events` 建立 SSE 连接，将 `EventBus` 通知推给网页。

常用接口与调用方向：

| 接口示例 | 交给谁 | 用途 |
| --- | --- | --- |
| `POST /api/search` | `Service.search()` | 提交一次完整主题分析 |
| `GET /api/status` | `Service.status()` | 页面查询运行情况 |
| `GET /api/reports` | `Service.reports()` | 列出历史报告 |
| `GET /api/reports/{id}` | `Service.get_report()` | 读取具体报告 |
| `GET /api/graph/latest` | `Service.graph()` | 读取当前模式最新图谱 |
| `POST /api/graph/query` | `Service.query_graph()` | 筛选图谱节点和关系 |
| `GET /api/database/schema` | 数据库检查函数 | 管理员查看结构与映射建议 |
| `GET /api/events` | `EventBus.since()` | 持续接收状态事件 |

部分启停接口保留现有 GET 形式；完整方法、参数和权限以 [API 文档](API.md) 及路由代码为准，不要只凭接口名称推断。

SSE 最多同时开放 12 个连接，使用心跳和事件编号处理连接维持及有限历史补发。主题分析接口本身等待分析完成后返回，并不是一个已经实现流式 token 输出的聊天接口。

## 16. `static/`：浏览器里的界面

它是静态资源目录，不是 Python 包，也不需要 `__init__.py`。

### `src/public_sentiment/static/index.html`

提供页面基础结构，例如侧边导航、顶部区域、主内容区和弹窗容器，并加载 `app.js` 与 `style.css`。可以把它理解成“房子的框架”。

### `src/public_sentiment/static/app.js`

用原生 JavaScript 负责交互和页面内容，是“让房子能用起来的电路和操作按钮”。

| 主要函数/部分 | 作用 |
| --- | --- |
| `api()` | 统一发送后端请求、读取返回值和处理错误 |
| `state` | 保存当前页面、用户角色、状态、报告和图谱等前端数据 |
| `homePage()` / `searchPage()` | 显示控制台和主题分析页 |
| `forumPage()` / `reportsPage()` | 显示论坛监控和报告列表 |
| `configPage()` / `systemPage()` / `graphPage()` | 显示配置、系统和图谱页 |
| `drawGraph()` / `showNode()` | 使用 SVG 绘制节点关系、查看节点详情 |
| `navigate()` / `pageFromPath()` | 在不同页面间导航并对应浏览器地址 |
| `connectEvents()` | 通过 `EventSource` 接收 SSE 通知 |
| `escapeHtml()` / `safeLink()` | 对展示内容和链接做处理，避免直接信任来源文本 |
| `boot()` | 初始化会话、状态、页面及实时连接 |

它负责展示和发请求，不直接连接 MySQL，也不持有应当放在服务端的模型 API Key。前端按钮禁用只是交互提示，真正权限检查仍在后端。

### `src/public_sentiment/static/style.css`

负责颜色、字体、布局、表格、状态标识、弹窗和不同屏幕宽度的适配。它不调用模型、不执行数据库查询，也不承担业务状态机。

## 17. 每个子包的 `__init__.py` 也有明确位置

下面这些文件目前主要是包职责说明，不是漏掉的业务实现。统一列出，避免误以为每个初始化文件都要写启动代码。

| 完整源码路径 | 当前作用 |
| --- | --- |
| `src/public_sentiment/application/__init__.py` | 标记应用编排包，说明业务协调层职责 |
| `src/public_sentiment/collection/__init__.py` | 标记资料采集包，说明数据读取职责 |
| `src/public_sentiment/analysis/__init__.py` | 标记模型分析包，说明分析与约束职责 |
| `src/public_sentiment/reporting/__init__.py` | 标记报告与图谱包 |
| `src/public_sentiment/runtime/__init__.py` | 标记运行调度包，区别根目录运行数据 |
| `src/public_sentiment/infrastructure/__init__.py` | 标记基础设施包 |
| `src/public_sentiment/config/__init__.py` | 标记配置包 |
| `src/public_sentiment/core/__init__.py` | 标记共用基础工具包 |
| `src/public_sentiment/web/__init__.py` | 标记 Web 服务包 |

顶层的 `src/public_sentiment/__init__.py` 还带延迟调用 `cli.main()` 的包装，已在第 5 节单独解释。训练子目录和静态目录没有对应文件，不能把这张表当作所有目录都必须新增初始化文件的清单。

## 18. `docs/` 与 `examples/`：说明材料和参考数据

### `docs/` 中每份文档的用途

| 文件 | 主要回答的问题 | 阅读提醒 |
| --- | --- | --- |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | 每个目录和文件做什么，怎样一起工作？ | 本文，适合按代码位置逐步阅读 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 为什么这样分层，模块之间的边界是什么？ | 从系统设计角度看整体 |
| [API.md](API.md) | 前端如何请求后端，参数和权限是什么？ | 调试接口时查阅 |
| [FASTAPI_VALIDATION.md](FASTAPI_VALIDATION.md) | 这次框架改造验证了什么，还有什么待验收？ | 区分模拟验证和真实外部服务验证 |
| [LLM.md](LLM.md) | 模型怎么接，输出怎么限制，训练数据怎么审核导出？ | 修改模型和准备微调时查阅 |
| [DATABASE_WORKFLOW.md](DATABASE_WORKFLOW.md) | 如何检查数据库连通性、真实字段和映射？ | 不要跳过真实字段核对 |
| [LOCAL_DATABASE.md](LOCAL_DATABASE.md) | 本机曾怎样接库和验证，遇到了什么问题？ | 是历史执行记录，不是数据库当前行数或模型质量保证 |

根目录 [PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md) 偏技术栈和面试表达；[README.md](../README.md) 偏快速运行。三份文档各有重点，不需要把其中一份移动或覆盖成另一份。

### `examples/sources.json`

包含围绕“低空物流”的合成来源示例，覆盖新闻、图片、视频、论坛和内部数据，供理解来源格式和演示流程。

它不是实际线上爬取的数据，也不代表真实舆情结论。默认数据库模式不会因为查不到数据就自动读取它。

### `examples/database.tables.example.json`

展示怎样填写数据库表和字段映射，例如哪列表示主键、标题、正文、发布时间。它是“填写样板”，不是保证与你的数据库一致的配置，更不是自动建表脚本。

正确用法是先检查真实数据库结构，再照格式填写已确认的表与列。

## 19. 根目录的数据目录：生成后放在哪里

下面是按文件用途整理的结构。`{report_id}` 和 `{app}` 是位置占位符，不是字面文件名；日期和编号目录会不断增加，不需要把每份历史结果当成不同代码模块。

### 19.1 `reports/`：每次完整分析的档案

| 路径模板 | 保存什么 | 用简单的话说明 |
| --- | --- | --- |
| `reports/{report_id}/report.md` | 带章节、统计与引用的 Markdown | 给人阅读的报告 |
| `reports/{report_id}/result.json` | 来源、逐条分析、统计、综合结论、溯源等 | 给程序和页面读取的结构化档案 |
| `reports/{report_id}/config.snapshot.json` | 任务使用的非凭据业务配置 | 说明当时是按什么设置运行的 |

例如以后把模型或批次大小改了，旧报告仍能通过快照追溯当时的设置。历史报告可能来自旧版本或演示模式，不应拿它们反推当前实现一定使用旧算法。

### 19.2 `graphs/`：图谱数据，不是图数据库安装目录

`graphs/{report_id}/graph.json` 保存节点、边、引用和来源定位信息。编号与报告对应，网页读取后绘图。

节点是“主题、渠道、来源、风险”等对象，边表示“经由某渠道传播、包含某来源、提及某风险”等关系。这里没有 Neo4j 服务、Cypher 查询或模型权重。

### 19.3 `outputs/`：各岗位最近一次输出

根目录下有 `search/`、`multimedia/`、`insight/`、`report/`、`graph/` 五个子目录，各自包含 `latest.txt`。

这些文件用于控制台展示某个工作单元最近的处理结果，内容是 JSON 序列化文本，扩展名虽然是 `.txt`，也不是手写固定回复。它们会被下一次成功输出覆盖，不能代替按报告编号保存的历史档案。

### 19.4 `runtime/`：运行状态和监控记录

| 路径 | 用途 |
| --- | --- |
| `runtime/system.json` | 系统运行/离线等状态信息 |
| `runtime/system.log` | 系统启停、配置更新及相关运行记录 |
| `runtime/http.log` | HTTP 请求访问记录 |
| `runtime/uvicorn-{启动时间}.out.log` / `.err.log` | 后台启动时重定向的服务启动与错误日志；不是业务源码 |
| `runtime/errors.json` | 供排错和界面读取的错误记录 |
| `runtime/latest_report.json` | 最近成功报告的编号指针，不是报告全文 |
| `runtime/apps/{app}.json` | 工作单元状态快照 |
| `runtime/apps/{app}.log` | 工作单元日志 |
| `runtime/forum/status.json` | 论坛轮询状态 |
| `runtime/forum/seen.json` | 已见记录及正文指纹，用于识别变化 |
| `runtime/forum/latest.log` | 论坛监控的近期日志 |
| `runtime/forum/history/{YYYY-MM-DD}.json` | 某一天的论坛发现记录 |

`{app}` 对应前述五个工作单元，所以 `runtime/apps/` 中会看到 `search.json`、`search.log` 等成对文件。它们是状态/日志，不是五个业务源码文件。

删除论坛 `seen.json` 会改变去重基线，删除历史文件会失去回查资料，不能因为“都是生成文件”就认为可以随意清理。本文不执行数据删除。

### 19.5 根目录 `training/`：候选与导出数据

| 路径模板 | 用途 | 何时产生 |
| --- | --- | --- |
| `training/candidates/{report_id}.json` | 本次调用的提示、证据、输出、版本与审核状态 | 成功分析并开启候选采集时 |
| `training/export/train.jsonl` | 训练集，一行一个 JSON 对象 | 审核后执行默认导出命令 |
| `training/export/validation.jsonl` | 验证集，格式与训练集对应 | 执行导出后；样本很少时允许为空 |
| `training/export/manifest.json` | 数据条目、报告来源、集合、版本和哈希等清单 | 执行导出后 |

当前已有候选目录；`export/` 是默认导出目标，运行导出后才会生成，不应把它当成初始必备文件夹。指定其他输出目录时，上述三个导出文件会放到指定位置。

候选未经审核不能直接拿去训练；标记 `reviewed=true` 应代表确实核对过证据和答案，而不是为了让导出命令通过随手修改。

### 19.6 数据目录与源码目录可以不同

应用的数据根目录由 `--data-dir` 指定，默认是启动时的当前目录；`run.ps1` 会显式使用本项目根目录。换成其他数据目录时，配置、报告、日志和候选数据跟着该目录走，但 Python 源码和前端静态文件仍来自安装/源码位置。

**隐私提醒**：来源正文、模型提示词、报告、训练候选及日志可能含敏感信息。`.gitignore` 已忽略 `.env`、`runtime/`、`outputs/`、根目录 `training/` 等，但当前规则没有默认忽略所有 `reports/` 和 `graphs/`，不能假定报告不会进入版本库。忽略规则也不是权限控制或备份方案。

## 20. 开发环境目录与缓存：不是业务模块

### 20.1 `.idea/`

这是 IDE 的本地工程配置，删除或换编辑器不会自动删除业务代码，但会影响个人开发设置。

| 当前文件/子目录 | 作用 |
| --- | --- |
| `.idea/misc.xml` | IDE 项目级设置，例如解释器关联等 |
| `.idea/public-sentiment.iml` | IDE 模块定义，帮助识别源码与内容根目录 |
| `.idea/workspace.xml` | 工作区和个人界面状态，不是运行时配置 |
| `.idea/claudeCodeTabState.xml` | 编辑器相关工具的页签状态，不是本项目模型服务配置 |
| `.idea/.gitignore` | IDE 自己的忽略规则 |
| `.idea/inspectionProfiles/` | 代码检查配置的容器 |
| `.idea/inspectionProfiles/profiles_settings.xml` | IDE 选择/管理检查配置的设置 |
| `.idea/inspectionProfiles/Project_Default.xml` | 项目默认检查规则 |

不需要在这些 XML 文件里填写模型 API Key。IDE 自动记录的状态文件也不能拿来代表项目架构。

### 20.2 `.venv/`

这是本地 Python 运行环境，不是你亲自实现的业务包。本目录下可能有大量第三方 `.py`，逐个解释它们既不能帮助理解本项目，也容易把依赖能力误算成项目代码。

| 文件/目录 | 作用 |
| --- | --- |
| `.venv/Scripts/` | Python 解释器、环境激活和已安装工具的入口 |
| `.venv/Lib/site-packages/` | 已安装的第三方库及包元信息，例如数据库驱动 |
| `.venv/pyvenv.cfg` | 虚拟环境与基础解释器信息 |
| `.venv/.gitignore` | 避免把环境内容纳入版本管理 |
| `.venv/.lock` | 环境管理工具使用的锁文件，不是业务任务队列 |
| `.venv/CACHEDIR.TAG` | 缓存目录标记，不包含业务逻辑 |

环境应按 `pyproject.toml` 中声明的依赖安装或重建，而不是修改 `site-packages` 来增加项目功能。依赖安装方法见 README，例如安装 MySQL 额外依赖。

### 20.3 `__pycache__/` 与 `.pyc`

它们是 Python 自动生成的字节码缓存，不是新的源码包。重构后可能还残留旧文件名对应的缓存，不能据此断定旧的多进程模块仍在主流程中。看当前实现应以实际 `.py` 和导入关系为准。

## 21. 一次分析究竟经过哪些文件

### 21.1 启动流程

```text
run.ps1 或安装后的命令
  → public_sentiment/__main__.py / cli.py
  → 加载环境、检查配置与访问令牌
  → 创建 Storage、Service、协程调度器、论坛监控器
  → web/server.py 创建 FastAPI 应用，Uvicorn 开始接受请求
  → static/index.html + app.js + style.css 在浏览器展示
```

是否自动启动工作单元由配置控制。打开页面不等于所有业务岗位一定已运行，分析前还要满足系统和相关工作单元已启动等条件。

### 21.2 用户点击“分析”后的调用链

```text
浏览器 app.js：提交主题词与来源类型
                 ↓ POST /api/search
web/security.py：检查权限与请求来源
                 ↓
web/routes.py + schemas.py：匹配接口、校验请求
                 ↓
application/service.py：检查状态，确定本次配置
                 ↓ runtime/tasks.py 调度
    ┌───────────────────┬────────────────────┐
    │ search            │ multimedia         │
    │ 非图片/视频资料    │ 图片/视频的文字资料 │
    └───────────────────┴────────────────────┘
              都调用 collection/collector.py
                 ↓ 按模式选择数据库/文件/RSS
          core/sources.py 统一来源格式
                 ↓ 合并、排序、限制样本数
        insight → analysis/engine.py
                 ↓ 整理证据、分批
        analysis/client.py → 外部模型服务
                 ↓ schemas.py + validation.py 约束和校验
        合并逐条结果，由程序计算统计
                 ↓
    ┌───────────────────┬────────────────────┐
    │ report            │ graph              │
    │ report.py         │ graph.py           │
    │ 模型归纳后排版     │ 按证据规则构图     │
    └───────────────────┴────────────────────┘
                 ↓
         infrastructure/storage.py
                 ↓
 reports/ + graphs/ + 可选 training/candidates/
                 ↓
 返回分析结果，并通过 EventBus / SSE 通知页面
```

图中两个横向分支可以并行；上下游依赖仍须顺序满足。当前不是“每一步同时运行”，也不是“对每条来源创建一个进程”。

### 21.3 用一个小例子理解

假设用户输入“低空物流”，并选择新闻和论坛：

1. 前端把选择传给后端，业务层确认系统在线、相关工作单元可用。
2. 采集层从当前模式的来源中找匹配记录，统一成系统认识的字段。
3. 程序给记录分配 `S1`、`S2` 等编号，把有限长度证据交给模型。
4. 模型给出情绪、摘要和风险，程序检查结构、引用、原文摘录。
5. 校验通过后，一路整理报告，另一路构造图谱；失败则报错，不伪造成功报告。
6. 结果归档后，前端展示内容；以后能沿引用和数据库定位信息查回来源。

如果当前是数据库模式但没有匹配来源，这次分析会失败并提示调整主题或数据源，不会悄悄用合成示例补齐。

## 22. 包之间为什么能互相导入

例如 `application/service.py` 中可以看到类似：

```python
from ..runtime.tasks import CoroutineManager
from ..infrastructure.storage import Storage
```

这里的 `..` 表示回到上一级包 `public_sentiment`，再找到同级的 `runtime` 或 `infrastructure`。同一包内使用 `.client` 则表示当前包的 `client.py`。这是 Python 的相对导入，不是按当前工作目录随意找文件。

整体职责方向可以记为：

```text
入口 cli → Web 接口 → Service 业务协调 → 各处理阶段
                                       ↓
                            共用配置、存储、工具与事件
```

其中调度器把业务函数登记到 `HANDLERS`，只处理执行和状态，不把分析细节写进队列代码。前端通过 HTTP 调用后端，不会直接导入 Python 文件。

源码布局需要安装项目或设置 `PYTHONPATH=项目的 src 目录`；不要直接运行深层文件再通过到处修改 `sys.path` 修补导入。Windows 启动脚本已经替启动过程处理了这一点。

## 23. 想改某个功能，应该先看哪里

| 你要做的事 | 优先位置 | 常见注意事项 |
| --- | --- | --- |
| 换模型服务、密钥或模型名 | 根目录 `.env`；`analysis/client.py` | 配置根地址，改后重启，不把密钥放进前端 |
| 调整模型分析要求 | `analysis/prompts.py` | 同时考虑版本和旧训练候选的兼容性 |
| 增加输出字段/标签 | `analysis/schemas.py`、`validation.py`、`engine.py` | 需要同步消费者、报告和页面，不能只改提示词 |
| 改数据库表与字段 | `config.json` 的 `database.tables` | 先检查实际结构，别直接套用示例 |
| 改数据库读取方式 | `collection/database.py` | 保留只读、参数化查询及来源定位 |
| 增加新的资料入口 | `collection/collector.py` 与对应适配器 | 最终仍应输出统一来源格式 |
| 改论坛轮询与去重 | `collection/forum.py` | 注意历史记录和已见指纹的连续性 |
| 改报告章节和排版 | `reporting/report.py` | 不要误改尚未接入的 `rendering.py` 后以为已生效 |
| 改图谱结构 | `reporting/graph.py` 与 `static/app.js` | 后端节点/边格式与前端绘图要一致 |
| 改任务排队、并行、启停 | `runtime/tasks.py` | 区分协程取消和底层同步调用停止 |
| 改一次业务的阶段顺序 | `application/service.py` | 保持数据依赖及归档一致性 |
| 增加接口或请求字段 | `web/routes.py`、`web/schemas.py` | 同步 API 文档，不把阻塞函数直接放进异步路由 |
| 修改鉴权与同源策略 | `web/security.py` | 后端必须检查权限，不能仅依赖前端按钮 |
| 修改 Web 启停与装配 | `web/server.py`、`cli.py` | 保持 lifespan 清理与 SSE 退出行为 |
| 改页面交互或样式 | `static/app.js`、`index.html`、`style.css` | 页面不是保存模型密钥的地方 |
| 改默认参数或配置校验 | `config/defaults.py` 与相应校验文件 | 别把配置检查当作远端服务连通检查 |
| 改文件保存方式 | `infrastructure/storage.py` | 留意数据根目录、路径限制和写入中断 |
| 改训练导出或划分策略 | `training/export.py` 代码模块 | 保留审核、证据校验、去重和追溯 |

表中缩写的源码路径均相对于 `src/public_sentiment/`，除非明确写“根目录”。

## 24. 初学者阅读顺序与面试表达

### 推荐阅读顺序

1. 先看 `README.md` 和根目录 `PROJECT_OVERVIEW.md`，知道项目解决什么问题。
2. 看 `core/constants.py`、`core/sources.py`，理解一条来源长什么样。
3. 看 `application/service.py` 的 `search()`，先掌握完整业务顺序，不急着研究所有锁和队列。
4. 看 `collection/collector.py` 和 `collection/database.py`，理解资料如何进入系统。
5. 按 `engine.py → prompts.py / schemas.py → client.py → validation.py` 阅读模型分析。
6. 看 `reporting/report.py` 与 `graph.py`，理解产物怎样形成。
7. 再看 `runtime/tasks.py`、`events.py`，理解执行机制与通知，而不是把它们当作舆情算法。
8. 最后结合 `web/server.py`、`web/routes.py`、`web/security.py`、`static/app.js` 和 `training/export.py` 看网页与后续训练准备。

### 面试中可以这样介绍

> 我做的是一个可追溯的舆情分析控制台。数据侧适配已有 MySQL、RSS 和内部文件，先统一来源格式；业务层编排采集、模型分析、报告和图谱；调度层用 asyncio 队列管理五个工作单元，并通过线程池承接现有阻塞调用。模型通过兼容 Chat Completions 的服务调用，输出要通过结构、引用和原文摘录检查，统计由程序计算。结果按报告编号保存，并保留数据库记录定位；Web 服务使用 FastAPI + Uvicorn，网页使用原生 JavaScript，通过 HTTP 操作和 SSE 接收状态。为后续微调，我还准备了候选记录采集、人工审核和训练数据导出，但项目本身没有执行模型训练。

这段表述区分了“业务流程”“调度方式”“模型服务”和“训练准备”，比直接把项目称为多智能体或训练平台更贴合当前实现。

### 不应夸大的能力

- 不把图片/视频记录的文字分析说成已经实现 OCR、ASR 或视频理解。
- 不把 JSON 证据图谱说成已有图数据库、向量检索或 GraphRAG。
- 不把五个协程岗位说成五个独立进程，也不声称完全没有线程。
- 不把格式校验等同于事实核查完成，不说模型幻觉已彻底解决。
- 不把训练数据导出说成已经完成微调、部署训练后模型或证明模型效果提升。
- 不把受数量和时间窗口限制的来源样本当作全网、全库或总体民意统计。
- 不用本说明文档推导压测成绩或真实服务可用性；这些需要单独的实际环境验收。

**本文范围**：覆盖项目自有源码、根目录文件、文档/示例及运行数据目录的用途。第三方环境与自动生成缓存按类别说明，不逐个列举依赖库内部文件；本文不替代真实数据库、真实模型和生产部署的验收记录。
