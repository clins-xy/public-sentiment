import hashlib

from ..core.constants import TYPE_LABELS

def build_graph(payload: dict) -> dict:
    result = payload["result"]
    references = [source["reference"] for source in result["sources"]]
    nodes = [{"id": "topic", "type": "topic", "label": result["query"], "source_refs": references}]
    edges = []
    for source in result["sources"]:
        reference = source["reference"]
        channel_id = f"channel-{source['source_type']}"
        if not any(node["id"] == channel_id for node in nodes):
            channel_refs = [item["reference"] for item in result["sources"] if item["source_type"] == source["source_type"]]
            nodes.append({"id": channel_id, "type": "channel", "label": TYPE_LABELS[source["source_type"]], "source_refs": channel_refs})
            edges.append({"source": "topic", "target": channel_id, "type": "propagated_via", "source_refs": channel_refs})
        source_id = f"source-{reference}"
        nodes.append({"id": source_id, "type": source["source_type"], "label": source["title"], "source_refs": [reference], "url": source["url"], "sentiment": source["sentiment"]})
        if source.get("locator"):
            nodes[-1].update(locator=source["locator"], platform=source.get("platform", ""))
        edges.append({"source": channel_id, "target": source_id, "type": "contains", "source_refs": [reference]})
        for risk in source["risks"]:
            risk_id = "risk-" + hashlib.sha256(risk["text"].encode()).hexdigest()[:16]
            existing = next((node for node in nodes if node["id"] == risk_id), None)
            if existing:
                if reference not in existing["source_refs"]:
                    existing["source_refs"].append(reference)
            else:
                nodes.append({"id": risk_id, "type": "risk", "label": risk["text"], "source_refs": [reference]})
            edges.append({"source": source_id, "target": risk_id, "type": "mentions_risk", "source_refs": [reference], "evidence_quotes": risk["evidence_quotes"]})
    return {"report_id": result["report_id"], "query": result["query"], "created_at": result["executed_at"], "nodes": nodes, "edges": edges}
