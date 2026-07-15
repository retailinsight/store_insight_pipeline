"""
Per-run budget tracker for Snowflake Cortex calls.

Thread-safe so it can be shared across parallel ``investigate()`` workers.
"""

from __future__ import annotations

import threading


class CortexBudget:
    """
    Tracks Cortex calls and estimated tokens for a single pipeline run.

    Parameters
    ----------
    max_calls  : maximum number of Cortex calls allowed (None = unlimited)
    max_tokens : maximum number of estimated tokens allowed (None = unlimited)
    """

    def __init__(
        self,
        max_calls: int | None = None,
        max_tokens: int | None = None,
    ):
        self.max_calls = max_calls
        self.max_tokens = max_tokens
        self.calls_used = 0
        self.tokens_used = 0
        self._lock = threading.Lock()

    def record(self, estimated_tokens: int) -> bool:
        """
        Record a planned Cortex call.  Returns True if still within budget,
        False if the call would exceed it.
        """
        with self._lock:
            if self.max_calls is not None and self.calls_used + 1 > self.max_calls:
                return False
            if self.max_tokens is not None and self.tokens_used + estimated_tokens > self.max_tokens:
                return False
            self.calls_used += 1
            self.tokens_used += estimated_tokens
            return True

    def is_exceeded(self) -> bool:
        """Return True if the budget is already exceeded."""
        with self._lock:
            calls_exceeded = self.max_calls is not None and self.calls_used >= self.max_calls
            tokens_exceeded = self.max_tokens is not None and self.tokens_used >= self.max_tokens
            return calls_exceeded or tokens_exceeded

    def __repr__(self) -> str:
        return (
            f'CortexBudget(calls={self.calls_used}/{self.max_calls}, '
            f'tokens={self.tokens_used}/{self.max_tokens})'
        )


def budget_from_config(cfg) -> CortexBudget | None:
    """
    Build a CortexBudget from a PipelineConfig or dict.

    Returns None if no cortex budget section is configured.
    """
    if cfg is None:
        return None
    cortex_cfg = getattr(cfg, 'cortex', None) if not isinstance(cfg, dict) else cfg.get('cortex')
    if cortex_cfg is None:
        return None
    max_calls = getattr(cortex_cfg, 'max_calls_per_run', None)
    if max_calls is None and isinstance(cortex_cfg, dict):
        max_calls = cortex_cfg.get('max_calls_per_run')
    max_tokens = getattr(cortex_cfg, 'max_tokens_per_run', None)
    if max_tokens is None and isinstance(cortex_cfg, dict):
        max_tokens = cortex_cfg.get('max_tokens_per_run')
    if max_calls is None and max_tokens is None:
        return None
    return CortexBudget(
        max_calls=int(max_calls) if max_calls is not None else None,
        max_tokens=int(max_tokens) if max_tokens is not None else None,
    )


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token for English text."""
    return max(1, len(text) // 4)
