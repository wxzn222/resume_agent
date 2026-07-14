"""Optional Ollama/OpenAI-compatible model transport."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def parse_json_object(content: str) -> dict[str, Any]:
    """Extract the first valid JSON object, including nested objects."""

    if not isinstance(content, str) or not content.strip():
        raise ValueError("模型返回内容为空")

    decoder = json.JSONDecoder()
    for index, character in enumerate(content):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(content[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("模型返回内容中没有有效的 JSON 对象")


def _read_env_example() -> dict[str, str]:
    path = Path(__file__).resolve().parent.parent / ".env.example"
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


class ModelClient:
    """Thin, lazily initialized client for an OpenAI-compatible endpoint."""

    def __init__(
        self,
        client: object | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        defaults = _read_env_example()
        self._client = client
        self.model = model or os.getenv("MODEL_NAME") or defaults.get("MODEL_NAME")
        self.base_url = (
            base_url
            or os.getenv("OLLAMA_BASE_URL")
            or defaults.get("OLLAMA_BASE_URL")
        )
        self.api_key = os.getenv("API_KEY") or api_key or defaults.get("API_KEY")
        configured_timeout = (
            timeout
            if timeout is not None
            else os.getenv("MODEL_TIMEOUT_SECONDS", "30")
        )
        self.timeout = float(configured_timeout)
        if self.timeout <= 0:
            raise ValueError("模型超时时间必须大于 0 秒")

    def _get_client(self) -> object:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "未安装 openai，无法调用本地 Ollama；规则评分将继续执行"
            ) from exc
        if not self.model or not self.base_url:
            raise RuntimeError("模型配置不完整：缺少 MODEL_NAME 或 OLLAMA_BASE_URL")
        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "ollama",
            timeout=self.timeout,
        )
        return self._client

    def chat(self, prompt: str, temperature: float = 0.0) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt 不能为空")
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=2048,
        )
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError) as exc:
            raise ValueError("模型响应结构无效") from exc
        if not isinstance(content, str) or not content.strip():
            raise ValueError("模型返回内容为空")
        return content.strip()

    def chat_json(
        self, prompt: str, temperature: float = 0.0
    ) -> dict[str, Any]:
        return parse_json_object(self.chat(prompt, temperature=temperature))

    def test_connect(self) -> dict[str, Any]:
        try:
            content = self.chat("ping", temperature=0.0)
            return {
                "status": "success",
                "model": self.model,
                "response_received": bool(content),
            }
        except Exception as exc:
            return {
                "status": "fail",
                "error": str(exc),
            }
