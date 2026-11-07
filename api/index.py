"""Vercel entrypoint. The workspace packages are pure Python, so they are put on sys.path instead of pip-installed."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for p in ("packages/deterministic-tax-engine", "packages/mcp-servers", "packages/agents", "apps/api-gateway"):
    sys.path.insert(0, str(root / p))

from taxsetu_api.main import create_app  # noqa: E402

app = create_app()
