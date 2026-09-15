"""Small machine-readable CLI; unavailable pipeline commands are not registered."""

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path

from pydantic import ValidationError

from . import __version__
from .contracts import CONTRACTS
from .documents import read_document

AVAILABLE = ["capabilities", "doctor", "validate", "schema"]
PLANNED = ["decode", "analyze", "plan resolve", "assets check", "lyrics", "render", "preview"]


def emit(value: object, *, error: bool = False) -> None:
    print(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        file=sys.stderr if error else sys.stdout,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mvt", description="Music video toolkit bootstrap")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities", help="List implemented and planned capabilities")
    commands.add_parser("doctor", help="Report host and required future tool availability")
    validate = commands.add_parser("validate", help="Validate a single JSON artifact, not media")
    validate.add_argument("--kind", choices=CONTRACTS, required=True)
    validate.add_argument("file", type=Path)
    schema = commands.add_parser("schema", help="Print generated JSON Schema")
    schema.add_argument("--kind", choices=CONTRACTS, required=True)
    args = parser.parse_args(argv)
    if args.command == "capabilities":
        emit(
            {
                "version": __version__,
                "schema_version": "0.1",
                "stage": "bootstrap",
                "available": AVAILABLE,
                "planned": PLANNED,
                "can_render": False,
                "validation_scope": "single artifact; not media or cross-file preflight",
            }
        )
    elif args.command == "doctor":
        tools = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe", "node", "pnpm")}
        emit(
            {
                "platform": platform.system(),
                "machine": platform.machine(),
                "python": platform.python_version(),
                "tools": tools,
                "pipeline_ready": False,
                "reason": "Rendering and model adapters are not implemented",
            }
        )
        return 0 if all(tools.values()) else 1
    elif args.command == "schema":
        emit(CONTRACTS[args.kind].model_json_schema())
    elif args.command == "validate":
        try:
            CONTRACTS[args.kind].model_validate(read_document(args.file))
        except (ValueError, OSError, UnicodeError) as exc:
            details = (
                exc.errors(include_url=False, include_context=False, include_input=False)
                if isinstance(exc, ValidationError)
                else str(exc)
            )
            emit({"ok": False, "code": "invalid_artifact", "details": details}, error=True)
            return 2
        emit(
            {"ok": True, "kind": args.kind, "file": str(args.file), "scope": "single artifact only"}
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
