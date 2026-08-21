"""Create the ACTION_LIFECYCLE_EVENTS table if it does not exist."""

from __future__ import annotations

import os
from pathlib import Path

sys_path = Path(__file__).resolve().parents[1]
if str(sys_path) not in os.sys.path:
    os.sys.path.insert(0, str(sys_path))

from store_insight.pipeline.config.loader import load_config  # noqa: E402
from store_insight.pipeline.lifecycle import ensure_events_table  # noqa: E402
from store_insight.pipeline.pipeline.session import create_session, load_env  # noqa: E402


def main() -> None:
    load_env()
    cfg = load_config(os.environ.get("CLIENT") or "eastofengland")
    session = create_session(cfg)
    ensure_events_table(session)
    print("ACTION_LIFECYCLE_EVENTS table ensured.")


if __name__ == "__main__":
    main()
