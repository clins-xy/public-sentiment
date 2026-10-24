import hashlib


from ..core.constants import TYPE_LABELS


from ..analysis.client import LLMClient


from ..analysis.schemas import REPORT_SCHEMA


from ..analysis.validation import validate_report


def markdown_text(value: str) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    for character in ("\\", "`", "*", "_", "{", "}", "[", "]", "<", ">", "|", "#", "!"):
        text = text.replace(character, "\\" + character)
    return text


def cited(record: dict) -> str:
    return markdown_text(record["text"]) + " " + " ".join(f"[{reference}]" for reference in record["references"])


def build_report(payload: dict) -> dict:
    result = payload["result"]
    sources = result["sources"]
    evidence = [{key: source[key] for key in ("reference", "source_type", "title", "summary", "opinion", "sentiment",
                                             "sentiment_reason", "evidence_quotes", "risk_level", "risks", "analysis_truncated")} for source in sources]
    client = LLMClient(payload["config"]["llm"])
    narrative = client.generate("report", result["query"], evidence, REPORT_SCHEMA, validate_report)
    sentiment = result["sentiment"]
    lines = [f"# {markdown_text(result['query'])} · 舆情分析报告", "", f"报告编号：{result['report_id']}",
             f"生成时间：{result['executed_at']}", f"数据模式：{result['mode']}", "", "## 事件概况", cited(narrative["overview"]),
             "", "## 时间线"]
    for source in sorted(sources, key=lambda item: item["published_at"]):
        lines.append(f"- {markdown_text(source['published_at'] or '时间未知')} · {markdown_text(source['title'])} [{source['reference']}]")
    lines.extend(["", "## 传播渠道", "| 渠道 | 样本数 |", "| --- | ---: |"])
    for source_type, count in result["channels"].items():
        references = " ".join(f"[{source['reference']}]" for source in sources if source["source_type"] == source_type)
        lines.append(f"| {TYPE_LABELS[source_type]} | {count} {references} |")
    lines.extend(["", "## 主要观点"])
    lines.extend(f"- {markdown_text(opinion['author'])}：{cited(opinion)}" for opinion in result["opinions"])
    lines.extend(["", "## 情绪倾向", f"正向 {sentiment['positive']} / 中性 {sentiment['neutral']} / 负向 {sentiment['negative']} / 无法判断 {sentiment['unknown']}。",
                  result["method"], "", "## 风险判断", f"模型等级：{narrative['risk_level']}。样本负向占比 {result['negative_ratio']:.1%}。",
                  cited(narrative["risk_reason"])])
    for risk in result["risks"]:
        lines.append(f"- {cited(risk)}；原文：{'；'.join(markdown_text(quote) for quote in risk['evidence_quotes'])}")
    lines.extend(["", "## 重点证据"])
    for source in sources:
        lines.extend([f"### [{source['reference']}] {markdown_text(source['title'])}",
                      f"- 来源：{TYPE_LABELS[source['source_type']]} / {markdown_text(source['author'])}",
                      f"- 链接：{markdown_text(source['url']) if source['url'] else '内部数据（无公开链接）'}",
                      f"- 摘要：{markdown_text(source['summary'])}", f"- 情绪判断理由：{markdown_text(source['sentiment_reason'])}",
                      f"- 原文摘录：{'；'.join(markdown_text(quote) for quote in source['evidence_quotes'])}",
                      f"- 图谱引用：source-{source['reference']}"])
        if source.get("locator"):
            locator = source["locator"]
            lines.extend([f"- 数据溯源：{markdown_text(locator['database'])}.{markdown_text(locator['table'])} / {markdown_text(locator['primary_key_column'])}={markdown_text(locator['primary_key'])}",
                          f"- 平台：{markdown_text(source.get('platform', ''))}"])
        if source.get("source_keyword"):
            lines.append(f"- 上游采集主题词：{markdown_text(source['source_keyword'])}（采集元数据，不代表正文提及）")
        lines.append("")
    lines.extend(["## 结论摘要", cited(narrative["conclusion"]), "", "## 建议"])
    lines.extend(f"- {cited(recommendation)}" for recommendation in narrative["recommendations"])
    lines.extend(["", "## 方法与局限", markdown_text(narrative["limitations"]), result["method"],
                  "系统仅提供来源文字；不执行 OCR、语音识别或视频理解。报告由模型基于逐条分析归纳，统计由程序计算。"])
    lines.extend(f"- 采集提示：{markdown_text(warning)}" for warning in result["warnings"])
    return {"markdown": "\n".join(lines) + "\n", "conclusion": narrative["conclusion"]["text"],
            "risk_level": narrative["risk_level"], "narrative": narrative, "_training_samples": client.samples}
