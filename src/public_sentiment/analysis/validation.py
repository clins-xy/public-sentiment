import re

from .schemas import ANALYSIS_SCHEMA, REPORT_SCHEMA

def validate_shape(value, schema: dict, path="output") -> None:
    kind = schema["type"]
    if kind == "object":
        if not isinstance(value, dict) or set(value) != set(schema["properties"]):
            raise ValueError(f"{path} 字段必须严格为 {', '.join(schema['properties'])}")
        for key, child_schema in schema["properties"].items():
            validate_shape(value[key], child_schema, f"{path}.{key}")
    elif kind == "array":
        if not isinstance(value, list) or not schema["minItems"] <= len(value) <= schema["maxItems"]:
            raise ValueError(f"{path} 数组长度不符合约束")
        for index, child in enumerate(value):
            validate_shape(child, schema["items"], f"{path}[{index}]")
    elif kind == "string":
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{path} 必须为非空字符串")
        if not schema.get("minLength", 1) <= len(value) <= schema.get("maxLength", 10000):
            raise ValueError(f"{path} 文本长度不符合约束")
        if "enum" in schema and value not in schema["enum"]:
            raise ValueError(f"{path} 不在允许值中")
        if re.search(r"https?://|www\.|\[S\d+\]", value, re.IGNORECASE) and not path.endswith("reference") and ".evidence_quotes[" not in path:
            raise ValueError(f"{path} 不得生成链接或内嵌引用")


def validate_analysis(output: dict, evidence: list) -> None:
    validate_shape(output, ANALYSIS_SCHEMA)
    sources = {source["reference"]: source for source in evidence}
    references = [item["reference"] for item in output["items"]]
    if len(references) != len(set(references)) or set(references) != set(sources):
        raise ValueError("分析结果必须完整且不重复地覆盖当前批次的来源引用")
    for item in output["items"]:
        source = sources[item["reference"]]
        originals = (source["title"], source["content"])
        for record in [item, *item["risks"]]:
            if any(not any(quote in original for original in originals) for quote in record["evidence_quotes"]):
                raise ValueError(f"{item['reference']} 的证据摘录不在输入原文中")
        if item["risk_level"] in ("high", "medium") and not item["risks"]:
            raise ValueError("高、中风险必须提供风险说明和原文证据")


def validate_report(output: dict, evidence: list) -> None:
    validate_shape(output, REPORT_SCHEMA)
    allowed = {source["reference"] for source in evidence}
    for record in [output["overview"], output["conclusion"], output["risk_reason"], *output["recommendations"]]:
        references = record["references"]
        if len(references) != len(set(references)) or not set(references) <= allowed:
            raise ValueError("报告包含不存在或重复的证据引用")
