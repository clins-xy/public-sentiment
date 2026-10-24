def markdown_text(value: str) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    for character in ("\\", "`", "*", "_", "{", "}", "[", "]", "<", ">", "|", "#", "!"):
        text = text.replace(character, "\\" + character)
    return text


def cited(record: dict) -> str:
    return markdown_text(record["text"]) + " " + " ".join(f"[{reference}]" for reference in record["references"])
