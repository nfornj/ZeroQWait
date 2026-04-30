from __future__ import annotations

import os


TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "zeroqwait-agent-brain")


def temporal_enabled() -> bool:
    return os.getenv("TEMPORAL_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}