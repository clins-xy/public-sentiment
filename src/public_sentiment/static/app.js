"use strict";

const labels = {home:"控制台总览",search:"主题检索",forum:"论坛监控",graph:"关系图谱",reports:"分析报告",config:"配置管理",system:"系统状态"};
const appInfo = {
  search:{title:"主题检索",icon:"⌕",description:"聚合公开资讯与内部数据，捕捉主题相关信息。"},
  multimedia:{title:"多媒体检索",icon:"▷",description:"汇集图片说明与视频字幕，补充多维信息线索。"},
  insight:{title:"洞察分析",icon:"◈",description:"识别主要观点与情绪倾向，提取潜在风险。"},
  report:{title:"报告生成",icon:"▤",description:"汇总结构化舆情报告，让每一条结论有据可查。"},
  graph:{title:"关系图谱",icon:"⌘",description:"关联主题、渠道、证据与风险，串联信息脉络。"}
};
const sourceLabels = {news:"新闻资讯",image:"图片说明",video:"视频字幕",forum_post:"论坛帖子",internal_data:"内部数据"};
const modeLabels = {database:"数据库 · media_crawler",demo:"合成示例",live:"RSS / 内部文件"};
const stateLabels = {online:"运行中",offline:"已离线",starting:"启动中",shutting_down:"关闭中",running:"运行中",stopped:"已停止",stopping:"停止中",failed:"异常",idle:"待机",positive:"正向",neutral:"中性",negative:"负向",high:"高风险",medium:"需关注",low:"低风险",unknown:"证据不足"};
const state = {page:"home",status:null,reports:[],role:"viewer",result:null,graph:null,graphReport:"",searching:false,outputApp:null,outputMode:"output",configDirty:false,refreshing:false};
const main = document.querySelector("#main");
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[character]));
const badge = value => `<span class="badge ${escapeHtml(value)}">${escapeHtml(stateLabels[value] || value)}</span>`;
const dateText = value => value ? new Date(value).toLocaleString("zh-CN",{hour12:false}) : "—";
const canOperate = () => state.role !== "viewer";
const canAdmin = () => state.role === "admin";
const disabled = permission => permission ? "" : "disabled";
const empty = (message,icon="◈") => `<div class="empty"><div class="empty-icon">${icon}</div>${escapeHtml(message)}</div>`;

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `请求失败：${response.status}`);
  return data;
}

let toastTimer;
function toast(message) {
  const element = document.querySelector("#toast");
  element.textContent = message;
  element.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("visible"),4000);
}

function heading(title,description,actions="",eyebrow="PUBLIC SENTIMENT INTELLIGENCE") {
  return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div><div class="actions">${actions}</div></div>`;
}

function metric(label,value,foot,icon="◈",unit="") {
  return `<div class="metric"><div class="metric-label">${label}<span class="metric-icon">${icon}</span></div><div class="metric-number">${value}<small>${unit}</small></div><div class="metric-foot">${foot}</div></div>`;
}

function systemActions() {
  const online = state.status?.system_status === "online";
  return `<button class="button ${online ? "danger" : ""}" data-action="${online ? "shutdown" : "start-system"}" ${disabled(canAdmin())}>${online ? "◼ 停止系统" : "▷ 启动系统"}</button>`;
}

function appCard(name,app) {
  const info = appInfo[name];
  return `<article class="app-card"><div class="app-top"><span class="app-icon">${info.icon}</span>${badge(app.status)}</div><h3>${info.title}</h3><p>${info.description}</p><div class="app-meta"><span>${name.toUpperCase()} ENGINE</span><span>${escapeHtml(app.execution || "ASYNC TASK")}</span></div><p class="app-output" title="${escapeHtml(app.output_summary)}">${escapeHtml(app.output_summary)}</p><div class="app-bottom"><div class="actions"><button class="button small ${app.status === "running" ? "secondary" : ""}" data-action="${app.status === "running" ? "stop-app" : "start-app"}" data-app="${name}" ${disabled(canOperate() && (app.status === "running" || state.status.system_status === "online"))}>${app.status === "running" ? "◼ 停止" : "▷ 启动"}</button><button class="button ghost small" data-action="output" data-app="${name}">查看输出 ↗</button></div></div></article>`;
}

function reportRows(reports) {
  if (!reports.length) return empty("暂无分析报告，发起一次主题检索开始探索","▤");
  return reports.map(report => `<div class="report-row"><span class="file-icon">▤</span><div class="report-info"><strong>${escapeHtml(report.query)}</strong><small>${dateText(report.executed_at)} · ${report.source_count} 条来源 · ${modeLabels[report.mode] || report.mode}</small></div>${badge(report.risk_level)}<button class="button ghost small" data-action="view-report" data-id="${escapeHtml(report.report_id)}">查看报告 →</button></div>`).join("");
}

function homePage() {
  const status = state.status;
  const online = status.system_status === "online";
  return heading("信息汇聚，洞见先行","从多源信息到可追溯洞察，在一个工作空间掌握舆情全貌。",`<a class="button secondary" href="/search">＋ 新建主题分析</a>${systemActions()}`)
    + `<div class="banner"><div class="banner-icon">◉</div><div><strong>${online ? "分析引擎已就绪" : "开启你的舆情分析工作空间"}</strong><p>${online ? "各功能应用可独立控制。新任务使用最新配置，已生成的报告与日志持续保留。" : "启动系统后，即可进行多源检索、洞察分析与报告生成。"}</p></div><span class="badge ${online ? "online" : "stopped"}">${online ? "系统在线" : "等待启动"}</span></div>`
    + `<div class="metrics">${metric("系统运行状态",online ? "在线" : "离线",`<span class="live-dot"></span>${online ? "服务正常运行" : "控制台保持可访问"}`,"◴")}${metric("运行中应用",status.running_apps.length,"独立协程 · 独立日志","▦",`/ ${Object.keys(appInfo).length}`)}${metric("分析报告",status.report_count,"完整报告与图谱按编号归档","▤","份")}${metric("论坛采集",stateLabels[status.forum_status],"支持实时日志与历史回查","≋")}</div>`
    + `<div class="section-head"><div><h2>分析应用</h2><p>模块化工作流，自由掌控每一步分析</p></div><span class="muted"><small>${Object.keys(appInfo).length} 个应用</small></span></div><div class="app-grid">${Object.entries(status.apps).map(([name,app]) => appCard(name,app)).join("")}</div>`
    + `<div class="columns"><section class="panel"><div class="section-head"><div><h2>最近分析报告</h2><p>从主题出发，让洞察沉淀</p></div><a href="/reports">全部报告 →</a></div>${reportRows(state.reports.slice(0,3))}</section><section class="panel"><div class="section-head"><h2>运行概况</h2><a href="/system">详细状态 ↗</a></div><div class="health-row"><span>数据模式</span><strong>${modeLabels[status.mode] || status.mode}</strong></div><div class="health-row"><span>运行时长</span><strong>${Math.floor(status.resources.uptime_seconds / 60)} 分钟</strong></div><div class="health-row"><span>可用磁盘空间</span><strong>${(status.resources.disk_free_bytes / 1073741824).toFixed(1)} GB</strong></div><div class="health-row"><span>最近错误</span><strong>${status.recent_errors.length ? status.recent_errors.length + " 条记录" : "暂无异常记录"}</strong></div><div class="hint">所有分析结果保存在本地数据目录。</div></section></div>`;
}

function searchPage() {
  return heading("主题检索","多源并行检索，生成包含情绪、风险与来源证据的结构化报告。","","TOPIC EXPLORER")
    + `<section class="panel"><div class="section-head"><h2>想了解什么主题？</h2><span class="badge demo">${modeLabels[state.status.mode]}</span></div><form id="search-form"><div class="search-bar"><input type="text" id="query" name="query" aria-label="主题关键词" placeholder="输入主题或关键词，多个词以空格分隔" maxlength="200" value="${escapeHtml(state.result?.query || "")}" required><button class="button" type="submit" ${disabled(canOperate() && !state.searching)}>⌕ ${state.searching ? "正在分析…" : "开始分析"}</button></div><div class="source-options">${Object.entries(sourceLabels).map(([value,label]) => `<label><input type="checkbox" name="source" value="${value}" checked> ${label}</label>`).join("")}</div><p class="hint">每次分析实时读取已配置数据源；连续文字按完整短语匹配，多个关键词请用空格分隔（任意词命中）。数据库同时检索可用的上游采集主题词，主题词命中需核验原文；评论不自动关联原帖。图片与视频仅分析已提供的说明和字幕；情绪、观点、风险和报告由大语言模型生成；输出经过结构及证据校验，仍需人工复核。请先填写根目录 .env 的 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL。</p><div id="search-error" class="inline-error"></div></form></section><div id="search-result">${state.searching ? '<div class="panel loading"><span class="spinner"></span>多源采集 → 洞察分析 → 报告与图谱生成，请稍候…</div>' : state.result ? resultView(state.result) : `<section class="panel">${empty("先在配置页检查数据库并确认表映射，再输入数据库中实际存在的关键词。","⌕")}</section>`}</div>`;
}

function resultView(result) {
  const total = result.source_count || 1;
  return `<section class="panel"><div class="section-head"><div><div class="eyebrow">ANALYSIS RESULT</div><h2>${escapeHtml(result.query)} · 分析结果</h2><p>${escapeHtml(result.report_id)} · ${dateText(result.executed_at)}</p></div><div class="actions">${badge(result.risk_level)}<a class="button secondary small" href="/api/reports/${encodeURIComponent(result.report_id)}/markdown">↓ 下载报告</a><a class="button small" href="/graph-viewer/${encodeURIComponent(result.report_id)}">查看图谱 ↗</a></div></div>${result.mode === "demo" ? '<div class="warning">合成示例数据，仅用于功能演示；example.com 链接为占位地址，不是真实新闻或事件证据。</div>' : ""}${result.warnings.map(warning => `<div class="warning">${escapeHtml(warning)}</div>`).join("")}<p class="hint">${escapeHtml(result.analysis_backend === "llm" ? result.method : "历史规则报告：此结果生成于模型接入前，请重新分析以获取模型结果。")}</p><p class="result-summary">${escapeHtml(result.conclusion)}</p><div class="columns"><div><h3>情绪倾向</h3>${Object.entries(result.sentiment).map(([key,count]) => `<div class="bar-row"><span>${stateLabels[key]}</span><div class="bar-track"><div class="bar-fill ${key}" style="width:${count / total * 100}%"></div></div><span>${count}</span></div>`).join("")}</div><div><h3>传播渠道</h3>${Object.entries(result.channels).map(([key,count]) => `<div class="bar-row"><span>${sourceLabels[key]}</span><div class="bar-track"><div class="bar-fill" style="width:${count / total * 100}%"></div></div><span>${count}</span></div>`).join("")}</div></div><div class="tabs"><button class="tab active" data-action="result-tab" data-tab="evidence">来源证据 (${result.source_count})</button><button class="tab" data-action="result-tab" data-tab="report">完整报告</button><button class="tab" data-action="result-tab" data-tab="risk">风险线索 (${result.risks.length})</button></div><div id="result-evidence">${result.sources.map(source => `<article class="source-card"><div class="actions"><span class="badge">${escapeHtml(source.reference)}</span><span class="badge">${sourceLabels[source.source_type]}</span>${badge(source.sentiment)}</div><h3>${escapeHtml(source.title)}</h3><p>${escapeHtml(source.summary)}</p><small>${escapeHtml(source.author)} · ${escapeHtml(source.published_at || "时间未知")}</small>${source.locator ? `<small>数据库证据：${escapeHtml(source.locator.database)}.${escapeHtml(source.locator.table)} / ${escapeHtml(source.locator.primary_key_column)}=${escapeHtml(source.locator.primary_key)} · ${escapeHtml(source.platform)}</small>` : ""}${source.source_keyword ? `<small>上游采集主题词：${escapeHtml(source.source_keyword)}（采集元数据，不代表正文提及）</small>` : ""}${safeLink(source.url,source.demo ? "示例占位链接 ↗" : "查看原始来源 ↗")}</article>`).join("") || empty("未检索到匹配来源，请调整关键词或配置数据源")}</div><div id="result-report" hidden><pre class="report-text">${escapeHtml(result.markdown)}</pre></div><div id="result-risk" hidden>${result.risks.map(risk => `<article class="source-card"><span class="badge medium">${escapeHtml(risk.references.join(", "))}</span><p>${escapeHtml(risk.text)}</p><small>原文证据：${escapeHtml((risk.evidence_quotes || []).join("；"))} · 请人工核验</small></article>`).join("") || empty("模型未提取到风险线索")}</div></section>`;
}

function safeLink(url,label) {
  try {
    const parsed = new URL(url);
    if (["http:","https:"].includes(parsed.protocol)) return `<a href="${escapeHtml(parsed.href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
  } catch {}
  return '<small>本地数据，无公开链接</small>';
}

function forumPage() {
  return heading("论坛监控","持续收集论坛线索，保留每一次采集的时间、来源与任务状态。",`<span id="forum-state">${badge(state.status.forum_status)}</span><button class="button" data-action="forum-start" ${disabled(canOperate() && state.status.system_status === "online")}>▷ 启动采集</button><button class="button secondary" data-action="forum-stop" ${disabled(canOperate())}>◼ 停止采集</button>`,"COMMUNITY MONITOR")
    + `<div class="banner"><div class="banner-icon">≋</div><div><strong>${state.status.mode === "database" ? "数据库论坛记录监控" : state.status.mode === "demo" ? "示例论坛监控" : "RSS 论坛监控"}</strong><p>读取已映射为 forum_post 的表，按来源与内容指纹去重，滚动查看最近 N 条新增或变更。不替代上游爬虫，非完整增量同步。</p></div></div><section class="panel"><div class="section-head"><h2>实时采集日志</h2><button class="button secondary small" data-action="forum-refresh">刷新 ↻</button></div><pre id="forum-log" class="terminal">正在加载日志…</pre></section><section class="panel"><div class="section-head"><h2>历史日志</h2><span class="muted"><small>按本地日期归档</small></span></div><form id="history-form" class="toolbar"><input type="date" id="history-date" aria-label="历史日志日期" required value="${localDate()}"><button class="button secondary" type="submit">查询记录</button></form><div id="history-results">${empty("选择日期，回查历史采集记录")}</div></section>`;
}

function localDate() {
  const current = new Date();
  return `${current.getFullYear()}-${String(current.getMonth()+1).padStart(2,"0")}-${String(current.getDate()).padStart(2,"0")}`;
}

function reportsPage() {
  return heading("分析报告","每一份报告都是一次完整的信息沉淀，可按编号回查报告、证据与图谱。",'<a class="button" href="/search">＋ 新建分析</a>',"REPORT LIBRARY") + `<section class="panel"><div class="section-head"><h2>全部报告</h2><span class="badge">${state.reports.length} 份报告</span></div>${reportRows(state.reports)}</section><div id="report-detail"></div>`;
}

function configPage() {
  return heading("配置管理","维护系统、采集与分析参数；保存后新任务立即使用最新配置。",`<button class="button secondary" data-action="config-reload">重新读取</button><button class="button" data-action="config-save" ${disabled(canAdmin())}>保存配置</button>`,"CONFIGURATION")
    + `<div class="banner"><div class="banner-icon">⚙</div><div><strong>安全的热更新，无需重启控制台</strong><p>运行中的分析保留启动时配置快照；论坛于下一轮使用新配置。apps 开关决定下次系统启动的默认应用，不强制停止当前应用。</p></div></div><section class="panel"><div class="section-head"><h2>config.json</h2><div class="actions"><button class="button secondary small" data-action="database-inspect" ${disabled(canAdmin())}>检查数据库 / 表结构</button></div><span class="badge">${canAdmin() ? "管理员可编辑" : "只读模式"}</span></div><div class="config-summary"><span class="badge">数据库优先 · 只读接入</span><span class="badge">校验后原子保存</span></div><textarea id="config-editor" class="config-editor" aria-label="JSON 系统配置" spellcheck="false" ${canAdmin() ? "" : "readonly"}></textarea><div id="config-error" class="inline-error"></div><pre id="database-schema" class="report-text" hidden></pre><p class="hint">database 模式仅查询 media_crawler，不回退示例。数据库凭据来自 MEDIA_CRAWLER_DB_*。模型请填写根目录 .env：LLM_API_KEY、LLM_BASE_URL、LLM_MODEL；不要把密钥填入 config.json。环境变量优先于 .env，修改后须重启整个服务。先保存配置，再检查表结构，将确认后的 suggested_tables 复制到 database.tables 并保存。</p></section>`;
}

function systemPage() {
  const status = state.status;
  return heading("系统状态","从整体服务到单功能协程，运行情况一目了然。",systemActions(),"SYSTEM OBSERVABILITY")
    + `<div class="metrics">${metric("整体服务",stateLabels[status.system_status],"控制台独立于分析服务运行","◴")}${metric("运行时长",Math.floor(status.resources.uptime_seconds/60),"控制台进程存活时间","◷","分钟")}${metric("活动线程",status.resources.active_threads,`CPU 逻辑核心 ${status.resources.cpu_count}`,"▥")}${metric("磁盘可用",(status.resources.disk_free_bytes/1073741824).toFixed(1),"当前数据目录所在磁盘","▦","GB")}</div><section class="panel"><div class="section-head"><h2>应用协程</h2><span class="badge">主进程 ${status.resources.pid}</span></div><div class="table-wrap"><table><thead><tr><th>应用</th><th>运行状态</th><th>执行方式</th><th>启动时间</th><th>待完成任务</th><th>最近错误</th></tr></thead><tbody>${Object.entries(status.apps).map(([name,app]) => `<tr><td>${appInfo[name].title}</td><td>${badge(app.status)}</td><td>${escapeHtml(app.execution || "asyncio coroutine")}</td><td>${dateText(app.started_at)}</td><td>${app.pending_tasks}</td><td>${escapeHtml(app.last_error || "—")}</td></tr>`).join("")}</tbody></table></div></section><div class="status-grid"><section class="panel"><div class="section-head"><h2>最近错误</h2><span class="badge">${status.recent_errors.length} 条</span></div>${status.recent_errors.length ? status.recent_errors.slice().reverse().map(error => `<div class="error-box"><strong>${escapeHtml(error.module_name)}</strong> · ${dateText(error.time)}<p>${escapeHtml(error.error_message)}</p></div>`).join("") : empty("暂无异常记录","✓")}</section><section class="panel"><div class="section-head"><h2>系统运行日志</h2><button class="button secondary small" data-action="system-log">刷新</button></div><pre id="system-log" class="terminal">正在读取…</pre></section></div><div class="hint">资源指标为真实进程、线程与磁盘数据；不伪造 CPU / 内存利用率。停止系统只关闭分析应用与论坛采集，控制台继续提供历史回查。</div>`;
}

function graphPage() {
  return heading("关系图谱","沿着主题、传播渠道与来源证据，探索信息之间的关联。","","EVIDENCE GRAPH")
    + `<section class="panel"><form id="graph-form" class="toolbar"><select id="graph-report" class="report-select" aria-label="选择报告"><option value="">最新报告</option>${state.reports.map(report => `<option value="${escapeHtml(report.report_id)}" ${state.graphReport === report.report_id ? "selected" : ""}>${escapeHtml(report.query)} · ${escapeHtml(report.report_id)}</option>`).join("")}</select><input id="graph-node" type="text" aria-label="节点关键词" placeholder="节点名称或 ID"><select id="graph-relation" aria-label="关系类型"><option value="">全部关系</option><option value="propagated_via">传播渠道</option><option value="contains">包含来源</option><option value="mentions_risk">提及风险</option></select><button class="button" type="submit">查询图谱</button></form><div class="graph-layout"><div id="graph-stage" class="graph-stage">${empty("正在加载图谱…")}</div><aside id="graph-details" class="graph-details"><h3>图谱信息</h3><p>点击节点查看来源引用与关联关系。</p></aside></div><div class="legend"><span><i style="background:#5276e4"></i>主题</span><span><i style="background:#8c9fd4"></i>渠道</span><span><i style="background:#6db6a2"></i>来源</span><span><i style="background:#d9949c"></i>风险词</span></div></section>`;
}

function graphColor(node) {
  return node.type === "topic" ? "#5276e4" : node.type === "channel" ? "#8c9fd4" : node.type === "risk" ? "#d9949c" : "#6db6a2";
}

function drawGraph(graph) {
  state.graph = graph;
  const stage = document.querySelector("#graph-stage");
  if (!stage) return;
  if (!graph.nodes.length) { stage.innerHTML = empty("没有匹配的节点或关系"); return; }
  const coordinates = new Map();
  const width = 880, height = 560;
  const categories = [graph.nodes.filter(node => node.type === "topic"), graph.nodes.filter(node => node.type === "channel"), graph.nodes.filter(node => !["topic","channel","risk"].includes(node.type)), graph.nodes.filter(node => node.type === "risk")];
  categories.forEach((nodes,category) => nodes.forEach((node,index) => {
    if (category === 0) coordinates.set(node.id,{x:width/2,y:height/2});
    else {
      const angle = index / Math.max(nodes.length,1) * Math.PI * 2 - Math.PI / 2 + category * .25;
      const radius = [0,125,220,295][category];
      coordinates.set(node.id,{x:width/2+Math.cos(angle)*radius*1.12,y:height/2+Math.sin(angle)*Math.min(radius,245)});
    }
  }));
  const edges = graph.edges.map(edge => {
    const start = coordinates.get(edge.source), end = coordinates.get(edge.target);
    return start && end ? `<line x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}"><title>${escapeHtml(edge.type)} · ${escapeHtml(edge.source_refs.join(", "))}</title></line>` : "";
  }).join("");
  const nodes = graph.nodes.map((node,index) => {
    const position = coordinates.get(node.id);
    const radius = node.type === "topic" ? 22 : node.type === "channel" ? 15 : 9;
    const title = node.label.length > 12 ? node.label.slice(0,12)+"…" : node.label;
    return `<g data-node-index="${index}" tabindex="0" role="button" aria-label="${escapeHtml(node.label)}"><circle cx="${position.x}" cy="${position.y}" r="${radius}" fill="${graphColor(node)}"><title>${escapeHtml(node.label)}</title></circle><text x="${position.x}" y="${position.y+radius+17}" text-anchor="middle">${escapeHtml(title)}</text></g>`;
  }).join("");
  stage.innerHTML = `<svg viewBox="0 0 ${width} ${height}" aria-label="${escapeHtml(graph.query)}的证据关系图">${edges}${nodes}</svg>`;
  document.querySelector("#graph-details").innerHTML = `<h3>${escapeHtml(graph.query)}</h3><p>${graph.nodes.length} 个节点 · ${graph.edges.length} 条关系</p><p>报告编号<br>${escapeHtml(graph.report_id)}</p><p>点击节点查看来源引用与相邻关系。鼠标悬停连线可查看关系类型。</p><a href="/api/reports/${encodeURIComponent(graph.report_id)}/markdown">下载关联报告 ↗</a>`;
}

function showNode(index) {
  const graph = state.graph;
  const node = graph?.nodes[index];
  if (!node) return;
  const relations = graph.edges.filter(edge => edge.source === node.id || edge.target === node.id);
  document.querySelector("#graph-details").innerHTML = `<span class="badge">${escapeHtml(node.type)}</span><h3>${escapeHtml(node.label)}</h3><p>节点 ID<br>${escapeHtml(node.id)}</p><p>证据引用<br>${escapeHtml(node.source_refs.join(", ")) || "无"}</p>${node.locator ? `<p>数据库溯源<br>${escapeHtml(node.locator.database)}.${escapeHtml(node.locator.table)}<br>${escapeHtml(node.locator.primary_key_column)}=${escapeHtml(node.locator.primary_key)}</p>` : ""}${node.url ? safeLink(node.url,"原始来源 ↗") : ""}<h3>关联关系 (${relations.length})</h3><div class="node-relations">${relations.map(edge => `<div>${escapeHtml(edge.source)}<br>↓ ${escapeHtml(edge.type)}<br>${escapeHtml(edge.target)}<br><small>${escapeHtml(edge.source_refs.join(", "))}</small></div>`).join("")}</div><button class="button secondary small" data-action="view-report" data-id="${escapeHtml(graph.report_id)}">查看证据报告</button>`;
}

async function loadGraph() {
  const reportId = document.querySelector("#graph-report")?.value || state.graphReport;
  state.graphReport = reportId;
  try {
    const graph = await api("/api/graph/query",{report_id:reportId,node:document.querySelector("#graph-node")?.value || "",relation:document.querySelector("#graph-relation")?.value || ""});
    if (state.page === "graph") drawGraph(graph);
  } catch (error) {
    const stage = document.querySelector("#graph-stage");
    if (stage) stage.innerHTML = empty(error.message);
  }
}

async function render() {
  document.querySelector("#breadcrumb").textContent = labels[state.page];
  document.querySelectorAll("[data-page]").forEach(link => link.classList.toggle("active",link.dataset.page === state.page));
  const pages = {home:homePage,search:searchPage,forum:forumPage,reports:reportsPage,config:configPage,system:systemPage,graph:graphPage};
  main.innerHTML = pages[state.page]();
  try {
    if (state.page === "forum") await loadForum();
    if (state.page === "system") await loadSystemLog();
    if (state.page === "config") await loadConfig();
    if (state.page === "graph") await loadGraph();
  } catch (error) { toast(error.message); }
}

async function refresh(renderPage=false) {
  if (state.refreshing) return;
  state.refreshing = true;
  try {
    const [status,reports] = await Promise.all([api("/api/status"),api("/api/reports")]);
    state.status = status;
    state.reports = reports.reports;
    const modeBadge = document.querySelector("#mode-badge");
    modeBadge.textContent = modeLabels[status.mode] || status.mode;
    modeBadge.className = `badge ${status.mode === "demo" ? "demo" : "online"}`;
    if (renderPage || ["home","system"].includes(state.page)) await render();
    document.querySelector("#forum-state")?.replaceChildren();
    const forumState = document.querySelector("#forum-state");
    if (forumState) forumState.innerHTML = badge(status.forum_status);
  } finally { state.refreshing = false; }
}

async function loadForum() {
  const result = await api("/api/forum/log");
  const output = document.querySelector("#forum-log");
  if (output) {output.textContent = result.log || "暂无日志。启动论坛采集后，记录将显示在这里。"; output.scrollTop = output.scrollHeight;}
}

async function loadSystemLog() {
  const result = await api("/api/system/log");
  const output = document.querySelector("#system-log");
  if (output) {output.textContent = result.log || "暂无系统日志";output.scrollTop = output.scrollHeight;}
}

async function loadConfig() {
  const config = await api("/api/config");
  const editor = document.querySelector("#config-editor");
  if (editor) editor.value = JSON.stringify(config,null,2);
  state.configDirty = false;
}

async function loadOutput() {
  if (!state.outputApp) return;
  const result = await api(`/api/${state.outputMode === "log" ? "test_log" : "output"}/${state.outputApp}`);
  const output = document.querySelector("#output-content");
  output.textContent = result.output_text || result.log || "暂无输出，执行主题分析后可查看结果。";
  if (document.querySelector("#auto-scroll").checked) output.scrollTop = output.scrollHeight;
}

function pageFromPath() {
  const parts = location.pathname.split("/").filter(Boolean);
  state.page = parts[0] === "graph-viewer" ? "graph" : labels[parts[0]] ? parts[0] : "home";
  state.graphReport = parts[0] === "graph-viewer" && parts[1] ? decodeURIComponent(parts[1]) : "";
}

async function navigate(path) {
  if (state.configDirty && !confirm("配置尚未保存，确定离开？")) return;
  state.configDirty = false;
  history.pushState({},"",path);
  pageFromPath();
  await render();
  window.scrollTo(0,0);
}

document.addEventListener("click", async event => {
  const anchor = event.target.closest("a");
  if (anchor && anchor.origin === location.origin && !anchor.pathname.startsWith("/api/") && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
    event.preventDefault();
    await navigate(anchor.pathname);
    return;
  }
  const node = event.target.closest("[data-node-index]");
  if (node) {showNode(Number(node.dataset.nodeIndex));return;}
  const button = event.target.closest("[data-action]");
  if (!button || button.disabled) return;
  const action = button.dataset.action;
  try {
    if (action === "start-system" || action === "shutdown") {
      if (action === "shutdown" && !confirm("停止全部分析应用与论坛采集？历史报告和日志将保留。")) return;
      button.disabled = true;
      button.textContent = action === "shutdown" ? "正在停止…" : "正在启动…";
      await api(`/api/system/${action === "shutdown" ? "shutdown" : "start"}`,{});
      toast(action === "shutdown" ? "系统已停止，历史结果保留" : "分析系统已启动");
      await refresh(true);
    } else if (["start-app","stop-app"].includes(action)) {
      button.disabled = true;
      await api(`/api/${action === "start-app" ? "start" : "stop"}/${button.dataset.app}`);
      await refresh(true);
    } else if (action === "output") {
      state.outputApp = button.dataset.app;
      state.outputMode = "output";
      document.querySelector("#output-title").textContent = `${appInfo[state.outputApp].title} · 输出与日志`;
      document.querySelector("#output-dialog").showModal();
      await loadOutput();
    } else if (["forum-start","forum-stop"].includes(action)) {
      button.disabled = true;
      await api(`/api/forum/${action === "forum-start" ? "start" : "stop"}`);
      await refresh(true);
    } else if (action === "forum-refresh") await loadForum();
    else if (action === "system-log") await loadSystemLog();
    else if (action === "config-reload") {
      if (!state.configDirty || confirm("丢弃未保存的修改并重新读取？")) await loadConfig();
    } else if (action === "config-save") {
      const errorBox = document.querySelector("#config-error");
      errorBox.textContent = "";
      try {
        await api("/api/config",JSON.parse(document.querySelector("#config-editor").value));
        state.configDirty = false;
        toast("配置已保存，新任务即时生效");
        await refresh();
      } catch (error) {errorBox.textContent = error.message;}
    } else if (action === "database-inspect") {
      button.disabled = true;
      const output = document.querySelector("#database-schema");
      output.hidden = false;
      output.textContent = "正在只读检查数据库与表结构，请稍候…";
      try {
        const schema = await api("/api/database/schema");
        output.textContent = JSON.stringify(schema,null,2);
        toast("连接成功；请确认建议映射后手动保存 database.tables");
      } catch (error) {output.textContent = error.message;toast(error.message);}
    } else if (action === "view-report") {
      const result = await api(`/api/reports/${encodeURIComponent(button.dataset.id)}`);
      if (state.page !== "reports") await navigate("/reports");
      document.querySelector("#report-detail").innerHTML = resultView(result);
      document.querySelector("#report-detail").scrollIntoView({behavior:"smooth"});
    } else if (action === "result-tab") {
      const panel = button.closest(".panel");
      panel.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("active",tab === button));
      for (const key of ["evidence","report","risk"]) panel.querySelector(`#result-${key}`).hidden = key !== button.dataset.tab;
    }
  } catch (error) {toast(error.message); if (["start-system","shutdown","start-app","stop-app","forum-start","forum-stop"].includes(action)) await refresh(true);}
  finally {if (button.isConnected) button.disabled = false;}
});

document.addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.target;
  if (form.id === "search-form") {
    if (state.searching) return;
    const query = document.querySelector("#query").value.trim();
    const sourceTypes = [...form.querySelectorAll("input[name=source]:checked")].map(input => input.value);
    const errorBox = document.querySelector("#search-error");
    errorBox.textContent = "";
    if (!sourceTypes.length) {errorBox.textContent = "请至少选择一种来源类型";return;}
    const button = form.querySelector("button[type=submit]");
    state.searching = true;
    button.disabled = true;
    button.textContent = "正在分析…";
    document.querySelector("#search-result").innerHTML = '<div class="panel loading"><span class="spinner"></span>正在采集来源并生成报告与图谱…</div>';
    try {
      state.result = await api("/api/search",{query,source_types:sourceTypes});
      toast("分析完成，报告与图谱已归档");
      if (state.page === "search") document.querySelector("#search-result").innerHTML = resultView(state.result);
      await refresh();
    } catch (error) {
      if (errorBox.isConnected) errorBox.textContent = error.message;
      if (state.page === "search") document.querySelector("#search-result").innerHTML = empty("分析未完成，请检查应用状态后重试");
      toast(error.message);
    } finally {
      state.searching = false;
      if (button.isConnected) {button.disabled = false;button.textContent = "⌕ 开始分析";}
    }
  } else if (form.id === "history-form") {
    try {
      const result = await api("/api/forum/log/history",{date:document.querySelector("#history-date").value});
      const container = document.querySelector("#history-results");
      if (container) container.innerHTML = result.records.length ? `<div class="table-wrap"><table><thead><tr><th>时间</th><th>事件</th><th>消息</th><th>状态</th></tr></thead><tbody>${result.records.map(record => `<tr><td>${dateText(record.time)}</td><td>${escapeHtml(record.event_type)}</td><td>${escapeHtml(record.message_text)}</td><td>${badge(record.task_status)}</td></tr>`).join("")}</tbody></table></div>` : empty("该日期暂无采集记录");
    } catch (error) {toast(error.message);}
  } else if (form.id === "graph-form") await loadGraph();
});

document.addEventListener("keydown",event => {
  const node = event.target.closest("[data-node-index]");
  if (node && ["Enter"," "].includes(event.key)) {event.preventDefault();showNode(Number(node.dataset.nodeIndex));}
});
document.addEventListener("input",event => {if (event.target.id === "config-editor") state.configDirty = true;});
document.querySelector("#close-dialog").addEventListener("click",() => document.querySelector("#output-dialog").close());
document.querySelector("#show-output").addEventListener("click",() => {state.outputMode = "output";loadOutput().catch(error => toast(error.message));});
document.querySelector("#show-log").addEventListener("click",() => {state.outputMode = "log";loadOutput().catch(error => toast(error.message));});
document.querySelector("#refresh-output").addEventListener("click",() => loadOutput().catch(error => toast(error.message)));
window.addEventListener("popstate",() => {pageFromPath();render();});
window.addEventListener("beforeunload",event => {if (state.configDirty) {event.preventDefault();event.returnValue = "";}});

let refreshTimer;
function scheduleRefresh() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => refresh().catch(error => toast(error.message)),400);
}

function connectEvents() {
  const events = new EventSource("/api/events");
  events.onopen = () => {document.querySelector("#connection").textContent = "实时连接已建立";};
  events.onerror = () => {document.querySelector("#connection").textContent = "连接恢复中…";};
  for (const type of ["app_status","system_status","graph_ready"]) events.addEventListener(type,scheduleRefresh);
  events.addEventListener("forum_log",() => {
    if (state.page === "forum") loadForum().catch(() => {});
    scheduleRefresh();
  });
  events.addEventListener("app_output",event => {
    const data = JSON.parse(event.data);
    if (document.querySelector("#output-dialog").open && state.outputApp === data.app_name) loadOutput().catch(() => {});
  });
  events.addEventListener("error",event => {
    if (event.data) {toast(JSON.parse(event.data).error_message);scheduleRefresh();}
  });
}

async function boot() {
  pageFromPath();
  try {
    const session = await api("/api/session");
    state.role = session.role;
    document.querySelector("#role-badge").textContent = {admin:"管",operator:"操",viewer:"阅"}[state.role];
    document.querySelector("#role-badge").title = `${state.role}${session.authentication_enabled ? " · 已鉴权" : " · 本机开发模式"}`;
    await refresh(true);
    connectEvents();
    setInterval(() => {if (!document.hidden) refresh().catch(() => {});},12000);
  } catch (error) {
    main.innerHTML = `<div class="panel">${empty(`连接失败：${error.message}。请刷新页面重试。`)}</div>`;
  }
}
setInterval(() => {document.querySelector("#clock").textContent = new Date().toLocaleString("zh-CN",{hour12:false});},1000);
boot();
