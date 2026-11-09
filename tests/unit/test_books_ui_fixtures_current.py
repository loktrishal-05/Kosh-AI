"""The UI's contract fixtures must be the engine's CURRENT output; otherwise the page may be tested against a shape that no longer exists."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ui_fixtures_match_current_engine_output():
    spec = importlib.util.spec_from_file_location("gen_books_fixtures", ROOT / "scripts" / "gen_books_fixtures.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    for name, result in gen.build().items():
        stored = json.loads((gen.OUT / f"books_{name}.json").read_text(encoding="utf-8"))
        assert stored == json.loads(json.dumps(result)), f"run: python scripts/gen_books_fixtures.py  ({name} changed)"
