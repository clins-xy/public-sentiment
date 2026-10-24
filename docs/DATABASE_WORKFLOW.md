# media_crawler：从虚拟机数据库到一次完整分析

## 一、你需要先确认的四件事

在 Navicat 中右键连接→「编辑连接」，记录 **实际数据库类型、主机/IP、端口和用户名**，不要把密码发给别人。数据库名已设为 `media_crawler`。本项目当前实现 MySQL / MariaDB；若是 PostgreSQL、SQL Server 或 SQLite，请先告知，不要使用错误驱动连接。

请特别注意：Navicat 如果开了 SSH 隧道，其“能连上”不表示本程序直接能连。如果在 Windows 也通过本地转发连接，请将相同隧道保持运行，并将本程序 host/port 指向本地转发端口；本程序不自动读取 Navicat 保存的密码或复用其私有隧道。

你可以先把以下信息（不含密码）发给我继续精确接入：

```text
数据库类型/版本：
VM IP / 数据库端口：
是否使用 SSH 隧道：
SHOW TABLES 的结果：
需要分析的 1–2 张表的 SHOW CREATE TABLE 结果：
发布时间列的单位/时区：
数据里实际存在的一个主题词：
```

也可从 Navicat「转储 SQL 文件→仅结构」导出结构 SQL 到项目；请不要导出账号、密码或个人敏感数据。

## 二、配置虚拟机网络和只读账号

假设 Windows 跑本项目，虚拟机跑数据库。桥接/Host-only 网络用虚拟机 IP；NAT 网络通常需端口转发。先测试（把地址换为你的）：

```powershell
Test-NetConnection 192.168.56.101 -Port 3306
```

失败时检查数据库监听地址、VM 防火墙、NAT 转发和 MySQL 用户 host 授权。不要为了省事把数据库开放到公网；最好只允许 Windows 主机 IP 访问。

用现有管理员在 Navicat 查询窗口执行**按实际地址修改后的**示例（由你执行，本程序不会自动建账号）：

```sql
CREATE USER 'sentiment_reader'@'你的Windows主机IP' IDENTIFIED BY '请替换成长随机密码';
GRANT SELECT ON media_crawler.* TO 'sentiment_reader'@'你的Windows主机IP';
SHOW GRANTS FOR 'sentiment_reader'@'你的Windows主机IP';
```

已有只读账号可直接使用，不需要重建。不要使用 root。本程序还会开启 READ ONLY 事务，但真正权限边界仍应由数据库账号保证。

## 三、安装驱动并设置环境变量

在项目根目录打开 PowerShell：

```powershell
uv sync --extra mysql
```

此工作环境已安装 MySQL 驱动；新机器需执行上述命令。如果只想使用已有虚拟环境也可：

```powershell
uv pip install --python .venv/Scripts/python.exe 'PyMySQL[rsa]>=1.1.1,<2'
```

在**同一 PowerShell 窗口**设置连接，不要将以下占位 IP 当成真实地址：

```powershell
$env:MEDIA_CRAWLER_DB_HOST = '192.168.56.101' # 替换为VM IP或隧道本地地址
$env:MEDIA_CRAWLER_DB_PORT = '3306'          # 替换为实际监听/转发端口
$env:MEDIA_CRAWLER_DB_USER = 'sentiment_reader'
$secret = Read-Host '数据库密码' -AsSecureString
$credential = [pscredential]::new('sentiment_reader', $secret)
$env:MEDIA_CRAWLER_DB_PASSWORD = $credential.GetNetworkCredential().Password
```

密码进入当前进程环境，仅用于运行时连接，不写入配置、报告或日志。关闭窗口后需要重新设置。不要把密码粘贴到聊天或 Git。设置好后再启动服务；服务已启动则退出并重启。

## 四、发现你的真实表结构

```powershell
.\run.ps1 -InspectDatabase
```

成功会输出 connected=true、tables（真实列名/类型）、suggested_tables（建议映射）。此步骤只读取元数据，不导出正文，不写回数据库，也不自动修改 config.json。映射留空时 `configured_mappings_valid=false` 属正常情况。

如果错误为“执行脚本被禁止”，使用等效命令，不需要更改系统安全策略：

```powershell
$env:PYTHONPATH = "$PWD\src"
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe -m public_sentiment --inspect-database --data-dir .
```

如需把结构发给我，可将**仅包含表/列元数据的**诊断输出保存为 `database-schema.local.json`（已忽略提交）；注意 PowerShell 5.1 的重定向可能保存为 UTF-16，保存时用 `Out-File -Encoding utf8`。

## 五、确认并保存表映射

编辑 `config.json` 的 database.tables（或者先启动 Web，在配置页编辑保存）。推荐首轮选择一张正文表，确认成功后再加评论表和其他平台。将诊断的 suggested_tables 按实际 schema 逐项核对后复制；**不是直接用示例表名**。

完整格式示例见 `examples/database.tables.example.json`，只说明格式，不保证你的库存在这些表。示例：

```json
{
  "table": "你的真实帖子表",
  "platform": "实际平台",
  "source_type": "forum_post",
  "time_unit": "ms",
  "fields": {
    "id": "真实唯一记录ID列",
    "title": "真实标题列",
    "content": "真实正文列",
    "url": "真实原帖URL列",
    "author": "真实昵称列",
    "published_at": "真实发布时间列"
  }
}
```

上述中文列名仅为占位说明，实际标识符须为你的英文/数字/下划线列名。不存在的可选字段**删除映射项**，不要写一个不存在的空字段。id 必需，title/content 至少一个。评论表 id 必须为评论自己的 ID，不能用所属帖子 ID；不含标题时只映射 content 即可。

- 时间为 `1720000000` 一般为 s，`1720000000000` 一般为 ms；auto 可按数量级判断，但需人工确认。
- DATETIME 用 datetime，timezone 默认为 +08:00；数据实际 UTC 则改 +00:00。
- 真实缺少 news/image 等类型无需补齐，不能拿演示资料凑来源。
- database 模式下 RSS 与 examples/sources.json 不参与检索。

保存后再次执行 `-InspectDatabase`，确认 `configured_mappings_valid=true`。它会校验映射的表和列是否存在，语义正确性仍须人工确认。

## 六、启动并完整跑一遍

```powershell
.\run.ps1
```

1. 打开 **http://127.0.0.1:8000**，右上角应显示「数据库 · media_crawler」。
2. 进入「配置管理」→「检查数据库 / 表结构」，再次确认连接与字段；仅管理员可操作。
3. 首页点击「启动系统」，五个分析应用应 running。启动 asyncio 应用单元成功**不等于数据库连接已成功**，数据库在实际查询/诊断时连接。
4. 进入「主题检索」，输入数据库中你确知存在的品牌、事件或关键词；首轮尽量用简单短词。
5. 仅勾选已映射的来源类型（例如小红书帖子对应论坛帖子，抖音说明对应视频字幕）。
6. 点击「开始分析」→ 查看来源证据、实际平台、原始 URL、库/表/主键、模型情绪判断和风险提示。
7. 检查完整报告并下载；结论引用 `[S1]` 等，在证据卡中可以找到同一引用。
8. 点击「查看图谱」，选择本次 report_id，点击来源节点查看关系与数据库 locator。
9. 在 Navicat 按报告给出的主键查询对应原记录，核对正文、发布时间和来源链接。
10. 若映射了 forum_post 表，进入「论坛监控」启动监控；上游爬虫继续写库时，这里按轮询窗口发现记录。可按日期回查日志。
11. 首页可查看每个应用的最近输出和标准/错误日志；停止单应用后再提交分析会明确提示，不伪装成功。
12. 完成后停止系统；报告/图谱仍可查看。终端 Ctrl+C 退出 Web。

本次产物：`reports/{report_id}/report.md`、`result.json`、`config.snapshot.json`、`graphs/{report_id}/graph.json`。result.json 保存本次读取的文本快照与 locator，不保存连接凭据；请视为可能含敏感真实数据，控制目录访问和分享范围。

## 七、常见问题

| 现象 | 优先检查 |
| --- | --- |
| 缺少数据库环境变量 | 是否在启动 run.ps1 的同一个终端设置；设置后是否重启 Web |
| MySQL 2003 | VM IP、监听端口、NAT 转发、防火墙、SSH 隧道 |
| MySQL 1045 | 账号密码、用户 host 限制、认证方式；不要改用 root 绕过 |
| MySQL 1049 | 数据库名/大小写是否为 media_crawler |
| 映射字段不存在 | SHOW CREATE TABLE 与 fields 一一核对，不照搬示例 |
| 查不到记录 | 关键词是否出现在标题/正文、来源是否勾选、映射是否正确；不默认匹配 search_keyword 列 |
| 时间全是未知/年份错误 | s/ms/us/datetime 与 timezone，避免把爬取时间当发布时间 |
| 数据量比 Navicat 少 | 每表、每分支、全局都有样本上限；有关键词过滤和来源过滤 |
| 论坛没有新增 | 仅论坛类型；去重或窗口内无新数据；本平台不会自己启动你的爬虫 |
| 查询超时 | 先仅映射一两张表，降低样本量；LIKE 不保证走索引，检查执行计划 |
| 找不到旧低空物流报告 | 数据库模式自动隔离 demo；旧报告文件未删除，可用旧编号明确回查 |

此文档提供完整可执行流程，但在实际连接资料和表结构提供前，不能宣称已经连通你的虚拟机或完成真实数据验收。
