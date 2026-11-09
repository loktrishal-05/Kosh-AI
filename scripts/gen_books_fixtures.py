"""Regenerate the UI contract fixtures: the REAL converter output for each bundled example.
Run after changing the engine:  python scripts/gen_books_fixtures.py   (a Python test fails until you do)."""
import json
from pathlib import Path

from taxsetu_engine.single_entry import convert

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "apps" / "ca-workbench-web" / "lib" / "fixtures"
EXAMPLES = ("business_textbook", "kirana_full_year", "nonprofit_club", "individual_freelancer")


def build():
    return {n: convert(json.loads((ROOT / "docs" / "samples" / "single_entry" / f"{n}.json").read_text(encoding="utf-8"))) for n in EXAMPLES}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, result in build().items():
        (OUT / f"books_{name}.json").write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
    print("wrote", len(EXAMPLES), "fixtures to", OUT)
