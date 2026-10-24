import math
import re
from urllib.parse import urlsplit

def validate_llm_config(config: dict) -> None:
    for key in ("api_key_env", "base_url_env", "model_env"):
        if not isinstance(config[key], str) or not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,79}", config[key]):
            raise ValueError(f"llm.{key} 必须为环境变量名")
    if not isinstance(config["base_url"], str) or not isinstance(config["model"], str) or len(config["model"]) > 200:
        raise ValueError("llm.base_url 和 model 必须为字符串，model 最长 200 字符")
    validate_base_url(config["base_url"])
    if config["response_format"] not in ("json_schema", "json_object"):
        raise ValueError("llm.response_format 必须为 json_schema 或 json_object")
    for key, minimum, maximum in (("timeout", 1, 600), ("max_retries", 0, 2), ("batch_size", 1, 20),
                                  ("max_chars_per_source", 200, 10000), ("max_tokens", 512, 32000)):
        if type(config[key]) is not int or not minimum <= config[key] <= maximum:
            raise ValueError(f"llm.{key} 必须为 {minimum}–{maximum} 的整数")
    temperature = config["temperature"]
    if type(temperature) not in (int, float) or not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError("llm.temperature 必须为 0–2 的有限数值")
    if type(config["capture_training"]) is not bool:
        raise ValueError("llm.capture_training 必须为布尔值")


def validate_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("LLM base_url 须为不含凭据、查询参数和片段的 HTTP(S) API 根地址")
    if parsed.path.rstrip("/").endswith("/chat/completions"):
        raise ValueError("LLM base_url 请填写 API 根地址（通常以 /v1 结尾），不要填写 /chat/completions")
    return value.rstrip("/")
