import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ollama_llama():
    load_dotenv()
    model_name = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    from src.core.local_provider import LocalProvider
    provider = LocalProvider(model_name=model_name, base_url=base_url)

    prompt = "Explain what an AI Agent is in one sentence."
    print(f"\n--- Testing Ollama provider | model: {model_name} ---")
    print(f"User: {prompt}")
    print("Assistant: ", end="", flush=True)

    for chunk in provider.stream(prompt):
        print(chunk, end="", flush=True)
    print("\n\n✅ Ollama LocalProvider is working correctly!")


if __name__ == "__main__":
    test_ollama_llama()
