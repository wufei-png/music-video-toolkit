"""Small machine-readable CLI; unavailable pipeline commands are not registered."""

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path

from pydantic import ValidationError

from . import __version__
from .alignment import AlignmentError, align_lyrics, apply_alignment_edits
from .analysis import AnalysisError, analyze_project
from .assets import AssetError, check_assets
from .audio import DecodeError, decode_audio
from .comparison import ComparisonError, compare_previews
from .contracts import CONTRACTS
from .documents import read_document
from .lyrics import LyricsError, import_lyrics
from .plan import PlanError, resolve_plan
from .preview import PreviewError, render_preview
from .render import RenderError, render_minimal, renderer_doctor

AVAILABLE = [
    "capabilities",
    "doctor",
    "validate",
    "schema",
    "decode",
    "analyze",
    "plan resolve",
    "assets check",
    "lyrics import",
    "lyrics align",
    "lyrics apply-edits",
    "preview",
    "compare",
    "render",
]
PLANNED = []


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
    analyze = commands.add_parser(
        "analyze", help="Extract mix features and optional real four stems"
    )
    analyze.add_argument("--project", type=Path, required=True)
    analyze.add_argument("--stems", choices=("four", "none"), required=True)
    plan = commands.add_parser("plan", help="Resolve bounded visual plans")
    plan_commands = plan.add_subparsers(dest="plan_command", required=True)
    resolve = plan_commands.add_parser("resolve", help="Resolve sections and layer parameters")
    resolve.add_argument("--project", type=Path, required=True)
    resolve.add_argument("--plan", type=Path, required=True)
    resolve.add_argument("--output", type=Path)
    assets = commands.add_parser("assets", help="Preflight local image, video and font assets")
    asset_commands = assets.add_subparsers(dest="asset_command", required=True)
    check = asset_commands.add_parser("check", help="Verify hashes, types and media metadata")
    check.add_argument("--project", type=Path, required=True)
    check.add_argument("--manifest", type=Path)
    check.add_argument("--output", type=Path)
    lyrics = commands.add_parser("lyrics", help="Import or align line-level lyrics")
    lyric_commands = lyrics.add_subparsers(dest="lyrics_command", required=True)
    lyric_import = lyric_commands.add_parser("import", help="Import UTF-8 LRC or SRT cues")
    lyric_import.add_argument("file", type=Path)
    lyric_import.add_argument("--project", type=Path, required=True)
    lyric_import.add_argument("--language", required=True)
    lyric_import.add_argument("--output", type=Path)
    lyric_align = lyric_commands.add_parser("align", help="Align known UTF-8 lyrics with WhisperX")
    lyric_align.add_argument("--text", type=Path, required=True)
    lyric_align.add_argument("--project", type=Path, required=True)
    lyric_align.add_argument("--language", choices=("en", "zh"), required=True)
    lyric_align.add_argument("--output", type=Path)
    lyric_align.add_argument("--report", type=Path)
    lyric_align.add_argument("--references", type=Path)
    lyric_edits = lyric_commands.add_parser(
        "apply-edits", help="Save reviewed line starts as an edited lyrics artifact"
    )
    lyric_edits.add_argument("--project", type=Path, required=True)
    lyric_edits.add_argument("--edits", type=Path, required=True)
    lyric_edits.add_argument("--aligned", type=Path)
    lyric_edits.add_argument("--report", type=Path)
    lyric_edits.add_argument("--output", type=Path)
    preview = commands.add_parser("preview", help="Render explicit global-time preview ranges")
    preview.add_argument("--project", type=Path, required=True)
    preview.add_argument("--plan", type=Path, required=True)
    preview.add_argument("--ranges", type=Path, required=True)
    preview.add_argument("--output", type=Path, required=True)
    preview.add_argument("--review-reel", action="store_true")
    compare = commands.add_parser("compare", help="Compare completed same-audio previews")
    compare.add_argument("--request", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
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
                "stage": "s09",
                "production_stage": "s10",
                "available": AVAILABLE,
                "planned": PLANNED,
                "can_render": True,
                "render_scope": (
                    "fixed 1080p30 abstract, mood and hybrid plans with imported lyrics "
                    "or saved aligned/edited cues; explicit global-time multi-range previews"
                ),
                "analysis_scope": (
                    "48 kHz mix features; optional htdemucs vocals/drums/bass/other"
                ),
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
        tools = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe", "node", "pnpm", "uv")}
        renderer = renderer_doctor()
        runtime = Path(
            os.environ.get(
                "MVT_SEPARATION_PROJECT",
                str(Path(__file__).resolve().parents[2] / "environments/separation"),
            )
        ).expanduser()
        analysis_runtime = {
            "path": str(runtime),
            "ready": (runtime / "pyproject.toml").is_file()
            and (runtime / "uv.lock").is_file()
            and (runtime / "analyze_audio.py").is_file(),
            "model_downloaded": False,
        }
        model_dir = Path(
            os.environ.get(
                "MVT_MODEL_DIR",
                str(Path.home() / "Library/Caches/music-video-toolkit/audio-separator"),
            )
        ).expanduser()
        analysis_runtime["model_downloaded"] = (model_dir / "htdemucs.yaml").is_file() and (
            model_dir / "955717e8-8726e21a.th"
        ).is_file()
        alignment_project = Path(
            os.environ.get(
                "MVT_ALIGNMENT_PROJECT",
                str(Path(__file__).resolve().parents[2] / "environments/alignment"),
            )
        ).expanduser()
        alignment_model_dir = Path(
            os.environ.get(
                "MVT_ALIGNMENT_MODEL_DIR",
                str(Path.home() / "Library/Caches/music-video-toolkit/whisperx"),
            )
        ).expanduser()
        alignment_runtime = {
            "path": str(alignment_project),
            "ready": all(
                (alignment_project / name).is_file()
                for name in ("pyproject.toml", "uv.lock", "align_audio.py")
            ),
            "model_cache": str(alignment_model_dir),
            "model_cache_present": alignment_model_dir.is_dir()
            and any(alignment_model_dir.iterdir()),
        }
        ready = (
            all(tools.values())
            and renderer["ready"]
            and analysis_runtime["ready"]
            and alignment_runtime["ready"]
        )
        emit(
            {
                "platform": platform.system(),
                "machine": platform.machine(),
                "python": platform.python_version(),
                "tools": tools,
                "renderer": renderer,
                "analysis_runtime": analysis_runtime,
                "alignment_runtime": alignment_runtime,
                "pipeline_ready": ready,
                "reason": (
                    "S03 analysis, S06 rendering and optional S07 alignment runtime; "
                    "models may be absent"
                ),
            }
        )
        return 0 if ready else 1
    elif args.command == "schema":
        emit(CONTRACTS[args.kind].model_json_schema())
    elif args.command == "decode":
        try:
            result = decode_audio(args.input, args.project)
        except DecodeError as exc:
            emit({"ok": False, "code": exc.code, "details": exc.details}, error=True)
            return exc.exit_code
        emit(result.report())
    elif args.command == "analyze":
        try:
            result = analyze_project(args.project, args.stems)
        except AnalysisError as exc:
            emit({"ok": False, "code": exc.code, "details": exc.details}, error=True)
            return exc.exit_code
        emit(result.report())
    elif args.command == "plan" and args.plan_command == "resolve":
        try:
            resolved, output = resolve_plan(args.project, args.plan, args.output)
        except PlanError as exc:
            emit({"ok": False, "code": exc.code, "details": exc.details}, error=True)
            return exc.exit_code
        emit(
            {
                "ok": True,
                "output": str(output),
                "mode": resolved.mode,
                "spans": len(resolved.spans),
                "routes": len(resolved.routes),
            }
        )
    elif args.command == "assets" and args.asset_command == "check":
        try:
            checked, output, cached = check_assets(args.project, args.manifest, args.output)
        except AssetError as exc:
            emit({"ok": False, "code": exc.code, "details": exc.details}, error=True)
            return exc.exit_code
        emit(
            {
                "ok": True,
                "cached": cached,
                "output": str(output),
                "cache_key": checked.cache_key,
                "assets": len(checked.assets),
            }
        )
    elif args.command == "lyrics" and args.lyrics_command == "import":
        try:
            imported, output, cached = import_lyrics(
                args.file, args.project, args.language, args.output
            )
        except LyricsError as exc:
            emit({"ok": False, "code": exc.code, "details": exc.details}, error=True)
            return exc.exit_code
        emit(
            {
                "ok": True,
                "cached": cached,
                "output": str(output),
                "language": imported.language,
                "cues": len(imported.cues),
            }
        )
    elif args.command == "lyrics" and args.lyrics_command == "align":
        try:
            result = align_lyrics(
                args.text,
                args.project,
                args.language,
                args.output,
                args.report,
                args.references,
            )
        except AlignmentError as exc:
            emit({"ok": False, "code": exc.code, "details": exc.details}, error=True)
            return exc.exit_code
        emit(result.summary())
    elif args.command == "lyrics" and args.lyrics_command == "apply-edits":
        try:
            result = apply_alignment_edits(
                args.project, args.edits, args.aligned, args.report, args.output
            )
        except AlignmentError as exc:
            emit({"ok": False, "code": exc.code, "details": exc.details}, error=True)
            return exc.exit_code
        emit(result.summary())
    elif args.command == "preview":
        try:
            result = render_preview(
                args.project,
                args.plan,
                args.ranges,
                args.output,
                review_reel=args.review_reel,
            )
        except PreviewError as exc:
            emit({"ok": False, "code": exc.code, "details": exc.details}, error=True)
            return exc.exit_code
        emit(result.summary())
    elif args.command == "compare":
        try:
            result = compare_previews(args.request, args.output)
        except ComparisonError as exc:
            emit({"ok": False, "code": exc.code, "details": exc.details}, error=True)
            return exc.exit_code
        emit(result.summary())
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
