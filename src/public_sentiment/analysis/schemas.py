from ..core.constants import RISK_LEVELS, SENTIMENTS

def object_schema(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def text_schema(maximum=1200) -> dict:
    return {"type": "string", "minLength": 1, "maxLength": maximum}


def array_schema(items: dict, minimum=0, maximum=50) -> dict:
    return {"type": "array", "items": items, "minItems": minimum, "maxItems": maximum}


RISK_SCHEMA = object_schema({"text": text_schema(600), "evidence_quotes": array_schema(text_schema(500), 1, 5)})


ITEM_SCHEMA = object_schema({
    "reference": text_schema(20), "summary": text_schema(600), "opinion": text_schema(600),
    "sentiment": {"type": "string", "enum": list(SENTIMENTS)},
    "sentiment_reason": text_schema(600), "evidence_quotes": array_schema(text_schema(500), 1, 5),
    "risk_level": {"type": "string", "enum": list(RISK_LEVELS)},
    "risks": array_schema(RISK_SCHEMA, 0, 10),
})


ANALYSIS_SCHEMA = object_schema({"items": array_schema(ITEM_SCHEMA, 1, 20)})


CITED_SCHEMA = object_schema({"text": text_schema(1600), "references": array_schema(text_schema(20), 1, 500)})


REPORT_SCHEMA = object_schema({
    "overview": CITED_SCHEMA, "conclusion": CITED_SCHEMA,
    "risk_level": {"type": "string", "enum": list(RISK_LEVELS)}, "risk_reason": CITED_SCHEMA,
    "recommendations": array_schema(CITED_SCHEMA, 1, 10), "limitations": text_schema(1600),
})
