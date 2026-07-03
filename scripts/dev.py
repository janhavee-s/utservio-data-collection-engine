#!/usr/bin/env python3
"""
Development startup script.

Starts FastAPI with auto-reload, debug logging, and development settings.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_env() -> None:
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    load_env()

    os.environ["CI_DEBUG"] = "true"
    os.environ["CI_LOG_LEVEL"] = "debug"
    os.environ["CI_ENVIRONMENT"] = "development"

    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "8000"))

    print("=" * 60)
    print("  Utservio Competitor Intelligence - Development Mode")
    print("=" * 60)
    print(f"  Host:         {host}")
    print(f"  Port:         {port}")
    print("  Auto-reload:  enabled")
    print("  Debug:        true")
    print("  Log Level:    debug")
    print(f"  Docs:         http://{host}:{port}/docs")
    print("=" * 60)
    print()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        reload_dirs=[str(PROJECT_ROOT / "app")],
        log_level="debug",
        access_log=True,
    )


if __name__ == "__main__":
    main()


