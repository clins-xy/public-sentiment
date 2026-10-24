import copy
import json
import os
import urllib.error
import urllib.request

from ..config.llm import validate_base_url
from .prompts import PROMPT_VERSION, SYSTEM_PROMPT


def task_timeout(config: dict, source_count: int, stage: str) -> int:
    batches = max(1, (source_count + config["batch_size"] - 1) // config["batch_size"]) if stage == "analysis" else 1
    return batches * (config["max_retries"] + 1) * (config["timeout"] + 5) + 30


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Disable redirects so API credentials are never forwarded to another host."""
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class RetryableError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, config: dict):
        self.config = config
        self.base_url = validate_base_url(os.environ.get(config["base_url_env"]) or config["base_url"])
        self.model = (os.environ.get(config["model_env"]) or config["model"]).strip()
        self.api_key = os.environ.get(config["api_key_env"], "").strip()
        if not self.model:
            raise ValueError("请在 .env 填写 LLM_MODEL，或在 config.json 填写 llm.model")
        if not self.api_key:
            raise ValueError(f"请在 .env 或环境变量填写 {config['api_key_env']}；本地无鉴权服务可填写 local")
        if any(ord(character) < 33 or ord(character) > 126 for character in self.api_key):
            raise ValueError("LLM_API_KEY 只能包含可见 ASCII 字符，不能含空格、换行或中文")
        self.samples = []

    def generate(self, stage: str, query: str, evidence: list, schema: dict, validator) -> dict:
        instruction = "逐条输出摘要、主要观点、情绪及理由、原文摘录与风险。每条来源必须恰好出现一次。" if stage == "analysis" else "根据逐条分析归纳概况、结论、总体风险及理由、建议和局限。每段事实判断须用 references 引用输入证据；区分样本情绪与实际事件风险。"
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps({
            "task": instruction, "query": query, "evidence": evidence, "output_schema": schema,
        }, ensure_ascii=False)}]
        for attempt in range(self.config["max_retries"] + 1):
            try:
                response = self.request(messages, stage, schema)
            except RetryableError:
                if attempt == self.config["max_retries"]:
                    raise
                continue
            try:
                output = json.loads(response["content"])
                validator(output, evidence)
            except (ValueError, TypeError, KeyError) as error:
                if attempt == self.config["max_retries"]:
                    raise RuntimeError(f"模型 {stage} 输出未通过结构或证据校验，任务终止；请检查模型能力或增大 max_tokens") from None
                messages = [*messages[:2], {"role": "user", "content": f"上次输出不符合约束：{error}。请根据原始证据重新生成完整 JSON。"}]
                continue
            if self.config["capture_training"]:
                self.samples.append({"stage": stage, "prompt_version": PROMPT_VERSION, "model": self.model,
                                     "messages": copy.deepcopy(messages), "response": output, "schema": schema,
                                     "usage": response["usage"], "reviewed": False})
            return output
        raise RuntimeError("模型调用失败")

    def request(self, messages: list, stage: str, schema: dict) -> dict:
        response_format = {"type": self.config["response_format"]}
        if response_format["type"] == "json_schema":
            response_format["json_schema"] = {"name": f"sentiment_{stage}", "strict": True, "schema": schema}
        body = {"model": self.model, "messages": messages, "temperature": self.config["temperature"],
                "max_tokens": self.config["max_tokens"], "stream": False, "response_format": response_format}
        request = urllib.request.Request(self.base_url + "/chat/completions", data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}",
                                                  "Accept": "application/json", "User-Agent": "PublicSentiment/0.2"})
        opener = urllib.request.build_opener(NoRedirect())
        try:
            with opener.open(request, timeout=self.config["timeout"]) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise RuntimeError("模型响应超过 4 MiB 限制")
        except urllib.error.HTTPError as error:
            try:
                details = json.loads(error.read(16384))
            except (ValueError, OSError):
                details = None
            finally:
                error.close()
            if error.code == 403 and isinstance(details, dict) and details.get("cloudflare_error") is True and details.get("error_code") == 1010:
                raise RuntimeError("模型接口 HTTP 403：Cloudflare 1010 拒绝了客户端标识，请联系模型服务商检查网关访问规则") from None
            exception = RetryableError if error.code in (429, 500, 502, 503, 504) else RuntimeError
            raise exception(f"模型接口 HTTP {error.code}；请核对 base_url、API Key、模型名和 response_format，服务须支持 Chat Completions") from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise RetryableError("模型接口连接失败或超时，请检查地址、服务及 llm.timeout") from None
        try:
            envelope = json.loads(raw)
            choice = envelope["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise RetryableError("模型输出未完整结束（截断、拒绝或工具调用），请检查模型或增大 max_tokens")
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip() or choice["message"].get("refusal"):
                raise RetryableError("模型返回空内容或拒绝回答")
            return {"content": content, "usage": envelope.get("usage", {})}
        except (ValueError, KeyError, IndexError, TypeError):
            raise RetryableError("模型接口响应不符合 Chat Completions 协议") from None
