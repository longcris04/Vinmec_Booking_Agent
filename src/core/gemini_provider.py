import os
import time
import google.generativeai as genai
from typing import Dict, Any, Optional, Generator
from src.core.llm_provider import LLMProvider

class GeminiProvider(LLMProvider):
    def __init__(self, model_name: str = "gemini-2.5-flash", api_key: Optional[str] = None):
        super().__init__(model_name, api_key)
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        
        # In Gemini, system instruction is passed during model initialization or as a prefix
        # For simplicity in this lab, we'll prepend it if provided
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"System: {system_prompt}\n\nUser: {prompt}"

        response = self.model.generate_content(full_prompt)

        end_time = time.time()
        latency_ms = int((end_time - start_time) * 1000)

        content = response.text

        # usage_metadata có thể không tồn tại tùy phiên bản SDK -> trích xuất an toàn
        meta = (getattr(getattr(response, "_result", None), "usage_metadata", None)
                or getattr(response, "usage_metadata", None))
        prompt_tokens = getattr(meta, "prompt_token_count", 0) if meta else 0
        completion_tokens = getattr(meta, "candidates_token_count", 0) if meta else 0
        total_tokens = getattr(meta, "total_token_count", 0) if meta else 0

        # Fallback: nếu SDK không trả token, ước lượng bằng count_tokens
        if total_tokens == 0:
            try:
                prompt_tokens = self.model.count_tokens(full_prompt).total_tokens
                completion_tokens = self.model.count_tokens(content).total_tokens
                total_tokens = prompt_tokens + completion_tokens
            except Exception:
                pass

        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

        return {
            "content": content,
            "usage": usage,
            "latency_ms": latency_ms,
            "provider": "google"
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"System: {system_prompt}\n\nUser: {prompt}"

        response = self.model.generate_content(full_prompt, stream=True)
        for chunk in response:
            yield chunk.text
