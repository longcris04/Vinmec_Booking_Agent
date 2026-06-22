"""
Entry point chạy Vinmec ReAct Agent (viết tay).

Cách chạy:
    python main.py
Cấu hình provider trong .env: DEFAULT_PROVIDER = openai | openrouter | google | local
"""

import os
import sys
from dotenv import load_dotenv

# Đảm bảo in được tiếng Việt trên console Windows (cp1252)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Cho phép import package src/ khi chạy trực tiếp
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent.agent import ReActAgent
from src.tools.vinmec_tools import TOOLS


def get_provider():
    """Khởi tạo LLM provider theo .env."""
    provider = os.getenv("DEFAULT_PROVIDER", "google").lower()

    if provider == "openai":
        from src.core.openai_provider import OpenAIProvider
        return OpenAIProvider(
            model_name=os.getenv("DEFAULT_MODEL", "gpt-4o"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    if provider == "openrouter":
        from src.core.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(
            model_name=os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
    if provider == "google":
        from src.core.gemini_provider import GeminiProvider
        # Model riêng cho Gemini (không dùng chung DEFAULT_MODEL của OpenAI)
        return GeminiProvider(
            model_name=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            api_key=os.getenv("GEMINI_API_KEY"),
        )
    if provider == "local":
        from src.core.local_provider import LocalProvider
        return LocalProvider(
            model_name=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

    raise ValueError(f"DEFAULT_PROVIDER không hợp lệ: {provider}. Chọn: openai | openrouter | google | local")


def main():
    load_dotenv()
    llm = get_provider()
    agent = ReActAgent(llm, TOOLS, max_steps=5)

    default_q = ("Tôi muốn khám Tim mạch ở Vinmec gần nhất, "
                 "dùng gói Vinmec Care, tổng chi phí phải trả là bao nhiêu?")
    question = input(f"Bạn hỏi gì? (Enter để dùng câu mẫu)\n> ").strip() or default_q

    print(f"\n[Provider: {llm.model_name}]")
    print(f"[Câu hỏi] {question}\n")
    answer = agent.run(question)
    print(f"\n=== TRẢ LỜI ===\n{answer}")


if __name__ == "__main__":
    main()
