import json
import time
from typing import Dict, Any, Optional, Generator

import requests

from src.core.llm_provider import LLMProvider

_DEFAULT_BASE_URL = "http://localhost:11434"


class LocalProvider(LLMProvider):
    """LLM Provider for local models via Ollama (e.g. llama3.1:8b)."""

    def __init__(self, model_name: str = "llama3.1:8b", base_url: str = _DEFAULT_BASE_URL):
        super().__init__(model_name=model_name)
        self.base_url = base_url.rstrip("/")

    def _messages(self, prompt: str, system_prompt: Optional[str]) -> list:
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        start = time.time()
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model_name, "messages": self._messages(prompt, system_prompt), "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        return {
            "content": data["message"]["content"],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "latency_ms": int((time.time() - start) * 1000),
            "provider": "ollama",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        with requests.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model_name, "messages": self._messages(prompt, system_prompt), "stream": True},
            stream=True,
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    token = json.loads(line).get("message", {}).get("content", "")
                    if token:
                        yield token
