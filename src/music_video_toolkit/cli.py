"""Small machine-readable CLI; unavailable pipeline commands are not registered."""

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path

from pydantic import ValidationError

from . import __version__
from .audio import DecodeError, decode_audio
from .contracts import CONTRACTS
from .documents import read_document
from .render import RenderError, render_minimal, renderer_doctor

AVAILABLE = ["capabilities", "doctor", "validate", "schema", "decode", "render"]
PLANNED = ["analyze", "plan resolve", "assets check", "lyrics", "preview"]


def emit(value: object, *, error: bool = False) -> None:
    print(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        file=sys.stderr if error else sys.stdout,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mvt", description="Deterministic music video toolkit")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities", help="List implemented and planned capabilities")
    commands.add_parser("doctor", help="Report host and external tool availability")
    decode = commands.add_parser("decode", help="Decode input audio to the canonical project WAV")
    decode.add_argument("input", type=Path)
    decode.add_argument("--project", type=Path, required=True)
    render = commands.add_parser("render", help="Render the supported fixed-frame plan")
    render.add_argument("--project", type=Path, required=True)
    render.add_argument("--plan", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
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
                "stage": "s02",
                "available": AVAILABLE,
                "planned": PLANNED,
                "can_render": True,
                "render_scope": "S02 fixture layers: s02.pulse, s02.image, s02.text",
                "validation_scope": "single artifact structure and local semantics",
                "project_preflight": [
                    "canonical source path",
                    "content hashes",
                    "WAV format",
                    "actual PCM sample count",
                ],
            }
        )
    elif args.command == "doctor":
        tools = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe", "node", "pnpm")}
        renderer = renderer_doctor()
        emit(
            {
                "platform": platform.system(),
                "machine": platform.machine(),
                "python": platform.python_version(),
                "tools": tools,
                "renderer": renderer,
                "pipeline_ready": all(tools.values()) and renderer["ready"],
                "reason": (
                    "S02 fixed-frame renderer only; analysis and production layers are pending"
                ),
            }
        )
        return 0 if all(tools.values()) and renderer["ready"] else 1
    elif args.command == "schema":
        emit(CONTRACTS[args.kind].model_json_schema())
    elif args.command == "decode":
        try:
            result = decode_audio(args.input, args.project)
        except DecodeError as exc:
            emit({"ok": False, "code": exc.code, "details": exc.details}, error=True)
            return exc.exit_code
        emit(result.report())
    elif args.command == "render":
        try:
            result = render_minimal(args.project, args.plan, args.output)
        except RenderError as exc:
            emit({"ok": False, "code": exc.code, "details": exc.details}, error=True)
            return exc.exit_code
        emit(result)
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
