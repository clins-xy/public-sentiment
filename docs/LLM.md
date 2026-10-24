# 大语言模型接入与训练数据准备

## 填写 API Key、Base URL 和模型名

项目根目录已有 `.env`，直接填写前三个变量：

```dotenv
LLM_API_KEY=你的模型服务密钥
LLM_BASE_URL=http://127.0.0.1:8001/v1
LLM_MODEL=你的服务实际提供的模型名称
```

`LLM_BASE_URL` 填 API 根地址，程序自动追加 `/chat/completions`。不要把 `/chat/completions` 再写进地址。本地无鉴权服务的 Key 可以填写 `local`。模型名必须与服务实际提供的名称一致；没有默认猜测模型。

`.env` 在启动时自动读取；已有进程环境变量优先。支持 `NAME=value` 和整行注释，可用成对单引号或双引号包裹值，不执行变量展开、不解析行尾注释。修改后重启整个服务，让新的协程任务使用新配置。密钥不进入 `config.json`、报告配置快照或训练样本；`.env` 已在 `.gitignore` 中忽略。

```powershell
.\run.ps1
```

也可以在同一个 PowerShell 终端设置环境变量，再启动程序：

```powershell
$env:LLM_API_KEY = '你的密钥'
$env:LLM_BASE_URL = 'http://127.0.0.1:8001/v1'
$env:LLM_MODEL = '你的模型名'
.\run.ps1
```

不需要新增模型 SDK 依赖，客户端使用 Python 标准库发送兼容 Chat Completions 的 HTTP 请求。模型服务须接受 `messages`、`temperature`、`max_tokens`、`response_format`，并返回 `choices[0].message.content` 和 `finish_reason=stop`。供应商的原生非兼容协议需要单独适配。

## 配置及输出约束

`config.json` 的 `llm` 部分维护非敏感参数：

| 字段 | 默认值 | 用途 |
| --- | --- | --- |
| `base_url` / `model` | 本地根地址 / 空 | 环境变量未填写时使用；模型必须配置 |
| `response_format` | `json_object` | 通用 JSON 模式；服务支持时可改为 `json_schema` 开启严格结构输出 |
| `temperature` | 0.2 | 生成温度 |
| `max_tokens` | 6000 | 每次调用的输出上限 |
| `timeout` / `max_retries` | 120 秒 / 1 | 单次请求超时和重试次数 |
| `batch_size` | 5 | 逐条分析每批来源数，1–20 |
| `max_chars_per_source` | 6000 | 单条正文送入模型的字符上限，截断会在报告提示 |
| `capture_training` | true | 归档通过校验的输入、模型输出、Schema、版本和用量 |

程序删除了旧版正负词词典、按负向比例判定风险、正文截断充当摘要、固定结论回复。`analysis` 旧配置读取时会被忽略；新配置使用 `llm`。旧历史文件保留，前端明确标记为历史规则报告。

现在的分析路径为：采集原文 → 分批模型分析 → 本地校验 → 模型报告归纳 → 本地校验 → Markdown 展示及证据图谱。

- 每条来源必须恰好出现一次；未知字段、漏字段、错误类型和超长输出会被拒绝。
- 情绪限定为 `positive/neutral/negative/unknown`；风险限定为 `high/medium/low/unknown`。
- 摘要、观点、情绪理由和风险由模型生成；原文摘录必须是输入标题或正文的连续子串。
- 报告的概况、结论、风险说明和建议必须给出真实存在的来源编号；禁止模型生成 URL 和内嵌来源编号，引用与链接由程序组装。
- 结构或证据校验失败会有限重试，最终失败则终止任务，不返回旧词典结果。不匹配任何来源也会明确报错。
- 原始正文、URL、发布时间、作者、数据库 locator、数量统计由程序保留或计算。Markdown 的章节和表格只是展示层，分析性内容由模型给出。
- 图谱以已经校验的来源和模型风险说明构造，避免让模型自由生成不存在的节点或关系。

相关实现均位于 `src/public_sentiment/` 包内：提示词为 `analysis/prompts.py`，Schema 为 `analysis/schemas.py`，输出校验为 `analysis/validation.py`，HTTP 客户端为 `analysis/client.py`，逐条分析入口为 `analysis/engine.py:analyze()`，报告入口为 `reporting/report.py:build_report()`。修改协议或提示词时须升级 `PROMPT_VERSION`。

报告阶段使用逐条分析结果，不会再次发送全部原文。大样本、长原文和复杂风险会增加上下文与费用；遇到服务上下文长度错误，先降低 `system.max_results` 或 `llm.batch_size`。JSON 模式和严格结构模式均会执行相同的本地校验。校验只能证明结构、引用存在和摘录匹配，不能证明模型推断正确或抵御全部提示注入，仍需人工核验。

## 为微调和续训积累数据

每次完整分析成功后，生成 `training/candidates/{report_id}.json`。其中记录两个任务：逐条分析 `analysis`、报告归纳 `report`。保留完整输入消息、输出 JSON、输出 Schema、模型名、提示词版本、用量和审核状态。可通过 `capture_training=false` 关闭。

默认所有候选文件及样本均为 `reviewed=false`。人工核对原文、修改错误标签/摘要/风险后，将文件顶层以及选中的 `samples` 项的 `reviewed` 都改为 `true`。导出会重新校验修订后的输出；未审核的内容不会进入训练集。不要改动原始输入和 Schema 来让错误答案通过校验。

监督微调对话导出：

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m public_sentiment.training --data-dir . --format chat --output-dir training/sft
```

输出 `train.jsonl`、`validation.jsonl` 和 `manifest.json`。每行格式为 `{"messages":[{"role":"system","content":"..."},{"role":"user","content":"..."},{"role":"assistant","content":"...JSON..."}]}`；修正重试的额外用户约束也会保留。实际训练前按训练框架的 chat template、分词器和数据格式要求转换。

领域继续预训练文本导出：

```powershell
.\.venv\Scripts\python.exe -m public_sentiment.training --data-dir . --format corpus --output-dir training/corpus
```

此模式从人工审核的分析样本提取输入标题和正文，输出每行 `{"text":"..."}`，不把模型回答当作原始语料。该语料是实际送入模型的截取文本；如果续训需要完整库语料，应另外建立经过清洗和授权的全量语料管线。

两种导出均对完全相同的记录去重，并按规范化主题的 SHA-256 分组划分训练/验证集，默认验证比例 10%，可设置 `--validation-percent 0..50`。同一规范化主题不会跨集合；小样本可能得到空验证集，需要积累更多不同主题。主题的同义写法和同一来源跨主题的近重复仍需在训练前进一步清洗。manifest 记录来源报告、任务、版本、集合和哈希。训练目录已加入 `.gitignore`。

本次准备的是推理入口、受约束的任务协议和人工审核的数据导出，没有执行训练。后续训练需要明确基座模型、许可证、训练框架、显存及评估集。训练并部署成兼容服务后，修改 `.env` 的 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY` 即可使用新模型。
