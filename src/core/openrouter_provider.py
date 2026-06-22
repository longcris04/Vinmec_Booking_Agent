import time
from typing import Dict, Any, Optional, Generator
from openai import OpenAI
from src.core.llm_provider import LLMProvider

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(LLMProvider):
    def __init__(self, model_name: str, api_key: Optional[str] = None):
        super().__init__(model_name, api_key)
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=OPENROUTER_BASE_URL,
        )

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        content = response.choices[0].message.content
        usage = response.usage
        return {
            "content": content,
            "usage": {
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            },
            "latency_ms": latency_ms,
            "provider": "openrouter",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
