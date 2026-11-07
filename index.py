"""Vercel entrypoint (zero-config FastAPI: exports `app`). The workspace packages are pure Python, so they go on sys.path instead of being pip-installed."""
import sys
from pathlib import Path

for p in ("packages/deterministic-tax-engine", "packages/mcp-servers", "packages/agents", "apps/api-gateway"):
    sys.path.insert(0, str(Path(__file__).resolve().parent / p))

from taxsetu_api.main import create_app  # noqa: E402

app = create_app()
