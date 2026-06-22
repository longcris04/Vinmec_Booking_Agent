from typing import Dict, Any, List, Optional
from src.telemetry.logger import logger

class PerformanceTracker:
    """
    Tracking industry-standard metrics for LLMs.
    """
    def __init__(self):
        self.session_metrics = []

    def track_request(self, provider: str, model: str, usage: Dict[str, int], latency_ms: int):
        """
        Logs a single request metric to our telemetry.
        """
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)

        metric = {
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "latency_ms": int(latency_ms),
            "cost_estimate": self._calculate_cost(model, {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }),
        }
        self.session_metrics.append(metric)
        logger.log_event("LLM_METRIC", metric)

    def _calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """
        Lightweight cost estimate for local telemetry.
        The repository may run across different providers, so this keeps
        the default model-agnostic and deterministic.
        """
        return (usage.get("total_tokens", 0) / 1000) * 0.01

    def get_session_metrics(self) -> List[Dict[str, Any]]:
        """Return a copy of all metrics collected in the current session."""
        return list(self.session_metrics)

    def summarize(self) -> Dict[str, Any]:
        """Aggregate token, latency, and cost metrics for the current session."""
        count = len(self.session_metrics)
        total_prompt_tokens = sum(item["prompt_tokens"] for item in self.session_metrics)
        total_completion_tokens = sum(item["completion_tokens"] for item in self.session_metrics)
        total_tokens = sum(item["total_tokens"] for item in self.session_metrics)
        total_latency_ms = sum(item["latency_ms"] for item in self.session_metrics)
        total_cost = sum(item["cost_estimate"] for item in self.session_metrics)

        average_latency_ms = total_latency_ms / count if count else 0.0
        average_tokens = total_tokens / count if count else 0.0

        return {
            "requests": count,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "average_tokens_per_request": average_tokens,
            "average_latency_ms": average_latency_ms,
            "total_cost_estimate": total_cost,
        }

    def reset(self) -> None:
        """Clear the in-memory session metrics."""
        self.session_metrics.clear()

# Global tracker instance
tracker = PerformanceTracker()
