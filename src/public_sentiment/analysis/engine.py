from collections import Counter

from ..core.constants import SENTIMENTS
from .client import LLMClient
from .prompts import PROMPT_VERSION
from .schemas import ANALYSIS_SCHEMA
from .validation import validate_analysis

def analyze(payload: dict) -> dict:
    config = payload["config"]["llm"]
    sources = [dict(source, reference=f"S{index + 1}") for index, source in enumerate(payload["sources"])]
    if not sources:
        raise ValueError("没有匹配来源，无法执行有证据的模型分析；请调整主题或数据源")
    client = LLMClient(config)
    for offset in range(0, len(sources), config["batch_size"]):
        batch = sources[offset:offset + config["batch_size"]]
        evidence = [{"reference": source["reference"], "source_type": source["source_type"],
                     "title": source["title"], "content": source["content"][:config["max_chars_per_source"]],
                     "content_truncated": len(source["content"]) > config["max_chars_per_source"]} for source in batch]
        output = client.generate("analysis", payload.get("query", ""), evidence, ANALYSIS_SCHEMA, validate_analysis)
        mapped = {item["reference"]: item for item in output["items"]}
        for source, supplied in zip(batch, evidence):
            source.update(mapped[source["reference"]])
            source["analysis_input_chars"] = len(supplied["content"])
            source["analysis_truncated"] = supplied["content_truncated"]
    counts = Counter({sentiment: 0 for sentiment in SENTIMENTS})
    counts.update(source["sentiment"] for source in sources)
    return {
        "sources": sources, "sentiment": dict(counts), "channels": dict(Counter(source["source_type"] for source in sources)),
        "negative_ratio": round(counts["negative"] / len(sources), 4), "risk_level": "unknown",
        "method": f"大语言模型分析；模型 {client.model}；提示词 {PROMPT_VERSION}；结构、引用和原文摘录校验通过不代表事实或推断已经核实。",
        "llm": {"model": client.model, "prompt_version": PROMPT_VERSION},
        "opinions": [{"source_type": source["source_type"], "author": source["author"], "text": source["opinion"], "references": [source["reference"]]} for source in sources],
        "risks": [{**risk, "references": [source["reference"]]} for source in sources for risk in source["risks"]],
        "_training_samples": client.samples,
    }
