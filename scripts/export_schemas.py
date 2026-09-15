"""Run with uv run --locked python scripts/export_schemas.py [--check]."""

import argparse
import json
from pathlib import Path

from music_video_toolkit.contracts import CONTRACTS

parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1] / "schemas"
root.mkdir(exist_ok=True)
for name, model in CONTRACTS.items():
    path = root / f"{name}.schema.json"
    expected = json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not path.exists() or path.read_text() != expected:
            raise SystemExit(f"Schema drift: {path}; regenerate with scripts/export_schemas.py")
    else:
        path.write_text(expected)
print("Schemas match" if args.check else "Schemas exported")
