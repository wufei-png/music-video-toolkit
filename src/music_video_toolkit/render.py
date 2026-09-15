"""S02 Python adapter for deterministic browser frame capture and MP4 encoding."""

import base64
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from pydantic import ValidationError

from .contracts import (
    AssetManifest,
    FileRef,
    RenderManifest,
    ResolvedPlan,
    SampleRange,
    Timeline,
    VisualPlan,
)
from .documents import read_document
from .plan import PlanError, validate_resolved_plan
from .project import ProjectPreflightError, preflight_source, resolve_record_path, sha256_file

FPS_NUM = 30
FPS_DEN = 1
SAMPLE_RATE = 48000
SUPPORTED_LAYER_KINDS = {"s02.pulse", "s02.image", "s02.text"}


class RenderError(Exception):
    """A stable render failure suitable for machine-readable CLI output."""

    def __init__(self, code: str, details: object, exit_code: int = 2):
        super().__init__(str(details))
        self.code = code
        self.details = details
        self.exit_code = exit_code


def renderer_root() -> Path:
    return Path(__file__).resolve().parents[2] / "renderer"


def renderer_doctor() -> dict[str, object]:
    node = shutil.which("node")
    pnpm = shutil.which("pnpm")
    root = renderer_root()
    report: dict[str, object] = {"root": str(root), "node": node, "pnpm": pnpm}
    if node is None or not (root / "node_modules/playwright").exists():
        report.update(browser=None, ready=False)
        return report
    command = [
        node,
        "--input-type=module",
        "-e",
        (
            "import {existsSync} from 'node:fs'; import {chromium} from 'playwright'; "
            "const path=chromium.executablePath(); "
            "console.log(JSON.stringify({path,exists:existsSync(path)}));"
        ),
    ]
    try:
        result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    except OSError:
        report.update(browser=None, ready=False)
        return report
    try:
        browser = json.loads(result.stdout) if result.returncode == 0 else None
    except json.JSONDecodeError:
        browser = None
    report.update(browser=browser, ready=bool(browser and browser.get("exists") and pnpm))
    return report


def _dependency(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RenderError(
            "missing_dependency",
            {"tool": name, "message": f"Install {name} and ensure it is on PATH"},
            3,
        )
    return path


def _load(model, path: Path, label: str):
    try:
        return model.model_validate(read_document(path))
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        details = (
            exc.errors(include_url=False, include_context=False, include_input=False)
            if isinstance(exc, ValidationError)
            else str(exc)
        )
        raise RenderError("invalid_render_input", {"artifact": label, "details": details}) from exc


def _run(
    command: list[str], *, cwd: Path | None = None, code: str
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise RenderError(code, str(exc), 3) from exc
    if result.returncode != 0:
        raise RenderError(
            code,
            {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr},
            5,
        )
    return result


def _abstract_inputs(project: Path, plan_path: Path, source) -> dict[str, object]:
    plan = _load(ResolvedPlan, plan_path, "resolved-plan")
    if plan.mode != "abstract":
        raise RenderError("unsupported_render_plan", {"mode": plan.mode}, 4)
    timeline_path = resolve_record_path(plan_path, plan.timeline_path)
    timeline = _load(Timeline, timeline_path, "timeline")
    source_plan_path = resolve_record_path(plan_path, plan.source_plan.path)
    expected = {
        "timeline_hash": plan.timeline_sha256,
        "timeline_source": source.record.canonical.sha256,
        "duration_samples": source.record.canonical.duration_samples,
    }
    actual = {
        "timeline_hash": sha256_file(timeline_path) if timeline_path.is_file() else None,
        "timeline_source": timeline.source.sha256,
        "duration_samples": timeline.source.duration_samples,
    }
    if actual != expected:
        raise RenderError("resolved_plan_mismatch", {"expected": expected, "actual": actual}, 4)
    if resolve_record_path(timeline_path, timeline.source.path) != source.canonical_path:
        raise RenderError("timeline_source_mismatch", {"path": timeline.source.path}, 4)
    if not source_plan_path.is_file() or sha256_file(source_plan_path) != plan.source_plan.sha256:
        raise RenderError("resolved_plan_mismatch", {"source_plan": str(source_plan_path)}, 4)
    missing = sorted({route.source for route in plan.routes} - set(timeline.signals))
    if missing:
        raise RenderError("missing_route_signal", {"signals": missing}, 4)
    try:
        validate_resolved_plan(plan, timeline)
    except PlanError as exc:
        raise RenderError(exc.code, exc.details, 4) from exc
    frame_count = (timeline.source.duration_samples * FPS_NUM + SAMPLE_RATE - 1) // SAMPLE_RATE
    return {
        "scene_mode": "abstract",
        "source": source,
        "plan": plan,
        "plan_path": plan_path,
        "source_plan_path": source_plan_path,
        "timeline": timeline,
        "timeline_path": timeline_path,
        "frame_count": frame_count,
        "pulse_frames": [],
    }


def _renderer_inputs(project: Path, plan_path: Path) -> dict[str, object]:
    try:
        source = preflight_source(project)
    except ProjectPreflightError as exc:
        raise RenderError(
            "project_preflight_failed", {"cause": exc.code, "details": exc.details}, 4
        ) from exc
    plan_path = plan_path.resolve()
    try:
        raw_plan = read_document(plan_path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise RenderError(
            "invalid_render_input", {"artifact": "plan", "details": str(exc)}
        ) from exc
    if "spans" in raw_plan:
        return _abstract_inputs(project, plan_path, source)
    plan = _load(VisualPlan, plan_path, "plan")
    timeline_path = resolve_record_path(plan_path, plan.timeline_path)
    assets_path = resolve_record_path(plan_path, plan.assets_path)
    timeline = _load(Timeline, timeline_path, "timeline")
    assets = _load(AssetManifest, assets_path, "assets")

    timeline_source = resolve_record_path(timeline_path, timeline.source.path)
    expected_source = {
        "path": source.canonical_path,
        "sha256": source.record.canonical.sha256,
        "sample_rate": source.record.canonical.sample_rate,
        "duration_samples": source.record.canonical.duration_samples,
    }
    actual_source = {
        "path": timeline_source,
        "sha256": timeline.source.sha256,
        "sample_rate": timeline.source.sample_rate,
        "duration_samples": timeline.source.duration_samples,
    }
    if actual_source != expected_source:
        raise RenderError(
            "timeline_source_mismatch",
            {
                "expected": {**expected_source, "path": str(expected_source["path"])},
                "actual": {**actual_source, "path": str(actual_source["path"])},
            },
            4,
        )

    enabled = [layer for layer in plan.layers if layer.enabled]
    unknown = sorted({layer.kind for layer in enabled} - SUPPORTED_LAYER_KINDS)
    if unknown:
        raise RenderError(
            "unsupported_render_plan",
            {"supported_layer_kinds": sorted(SUPPORTED_LAYER_KINDS), "unknown": unknown},
            4,
        )
    pulse_layers = [layer for layer in enabled if layer.kind == "s02.pulse"]
    image_layers = [layer for layer in enabled if layer.kind == "s02.image"]
    text_layers = [layer for layer in enabled if layer.kind == "s02.text"]
    if len(pulse_layers) != 1 or len(image_layers) != 1 or len(text_layers) != 1:
        raise RenderError(
            "unsupported_render_plan",
            "S02 requires one enabled s02.pulse, s02.image and s02.text layer",
            4,
        )
    pulse_event = pulse_layers[0].parameters.get("event")
    title = text_layers[0].parameters.get("text")
    if (
        not isinstance(pulse_event, str)
        or not pulse_event
        or not isinstance(title, str)
        or not title
    ):
        raise RenderError(
            "unsupported_render_plan",
            "pulse event and text layer content must be non-empty strings",
            4,
        )
    image_id = image_layers[0].asset_id
    image_asset = next((asset for asset in assets.assets if asset.id == image_id), None)
    if image_asset is None or image_asset.type != "image":
        raise RenderError("missing_render_asset", {"asset_id": image_id}, 4)
    image_path = resolve_record_path(assets_path, image_asset.path)
    if not image_path.is_file():
        raise RenderError("missing_render_asset", {"path": str(image_path)}, 4)
    try:
        actual_image_hash = sha256_file(image_path)
        image_bytes = image_path.read_bytes()
    except OSError as exc:
        raise RenderError(
            "render_asset_unreadable", {"path": str(image_path), "message": str(exc)}, 4
        ) from exc
    if actual_image_hash != image_asset.sha256:
        raise RenderError(
            "render_asset_hash_mismatch",
            {"path": str(image_path), "expected": image_asset.sha256, "actual": actual_image_hash},
            4,
        )
    if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RenderError("unsupported_render_asset", "S02 local image fixture must be PNG", 4)

    frame_count = (timeline.source.duration_samples * FPS_NUM + SAMPLE_RATE - 1) // SAMPLE_RATE
    pulse_frames = sorted(
        {
            (event.sample * FPS_NUM + SAMPLE_RATE - 1) // SAMPLE_RATE
            for event in timeline.events
            if event.name == pulse_event
        }
    )
    if not pulse_frames:
        raise RenderError("unsupported_render_plan", f"timeline has no {pulse_event!r} events", 4)
    return {
        "scene_mode": "fixture",
        "source": source,
        "plan": plan,
        "plan_path": plan_path,
        "timeline": timeline,
        "timeline_path": timeline_path,
        "assets_path": assets_path,
        "image_path": image_path,
        "image_data_url": "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"),
        "title": title,
        "frame_count": frame_count,
        "pulse_frames": pulse_frames,
    }


def _probe_output(ffprobe: str, path: Path, frame_count: int) -> dict[str, object]:
    result = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,nb_frames",
            "-of",
            "json",
            str(path),
        ],
        code="render_probe_failed",
    )
    try:
        streams = json.loads(result.stdout)["streams"]
        video = next(stream for stream in streams if stream["codec_type"] == "video")
        audio = next(stream for stream in streams if stream["codec_type"] == "audio")
        actual = {
            "video_codec": video["codec_name"],
            "width": video["width"],
            "height": video["height"],
            "fps": video["r_frame_rate"],
            "frames": int(video["nb_frames"]),
            "audio_codec": audio["codec_name"],
            "audio_rate": int(audio["sample_rate"]),
            "audio_channels": audio["channels"],
        }
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RenderError("render_probe_failed", "ffprobe returned incomplete streams", 5) from exc
    expected = {
        "video_codec": "h264",
        "width": 1920,
        "height": 1080,
        "fps": "30/1",
        "frames": frame_count,
        "audio_codec": "aac",
        "audio_rate": 48000,
        "audio_channels": 2,
    }
    if actual != expected:
        raise RenderError("render_output_mismatch", {"expected": expected, "actual": actual}, 5)
    return actual


def render_minimal(project: Path, plan_path: Path, output: Path) -> dict[str, object]:
    project = project.resolve()
    output = output.resolve()
    manifest_path = output.with_suffix(output.suffix + ".render.json")
    if output.exists() or manifest_path.exists():
        raise RenderError(
            "output_conflict", {"output": str(output), "manifest": str(manifest_path)}, 4
        )
    inputs = _renderer_inputs(project, plan_path)
    node = _dependency("node")
    pnpm = _dependency("pnpm")
    ffmpeg = _dependency("ffmpeg")
    ffprobe = _dependency("ffprobe")
    doctor = renderer_doctor()
    if not doctor["ready"]:
        raise RenderError(
            "missing_browser",
            {
                "message": (
                    "Install the pinned Chromium with "
                    "pnpm --dir renderer exec playwright install chromium"
                ),
                "doctor": doctor,
            },
            3,
        )
    root = renderer_root()
    _run([pnpm, "build"], cwd=root, code="renderer_build_failed")
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=output.parent, prefix=f".{output.stem}-", suffix=".mp4"
        )
    except OSError as exc:
        raise RenderError(
            "output_unwritable", {"path": str(output.parent), "message": str(exc)}, 5
        ) from exc
    os.close(descriptor)
    temporary = Path(temporary_name)
    config_path: Path | None = None
    output_installed = False
    manifest_installed = False
    manifest_temporary: Path | None = None
    try:
        descriptor, config_name = tempfile.mkstemp(
            dir=output.parent, prefix=".render-config-", suffix=".json"
        )
        config_path = Path(config_name)
        config = {
            "sceneMode": inputs["scene_mode"],
            "width": 1920,
            "height": 1080,
            "fpsNum": FPS_NUM,
            "fpsDen": FPS_DEN,
            "frameCount": inputs["frame_count"],
            "audioPath": str(inputs["source"].canonical_path),
            "outputPath": str(temporary),
            "ffmpegPath": ffmpeg,
        }
        if inputs["scene_mode"] == "fixture":
            config.update(
                pulseFrames=inputs["pulse_frames"],
                imageDataUrl=inputs["image_data_url"],
                title=inputs["title"],
            )
        else:
            config.update(
                sampleRate=SAMPLE_RATE,
                seed=inputs["plan"].seed,
                signals={
                    name: signal.model_dump(mode="json")
                    for name, signal in inputs["timeline"].signals.items()
                },
                spans=[span.model_dump(mode="json") for span in inputs["plan"].spans],
                routes=[route.model_dump(mode="json") for route in inputs["plan"].routes],
            )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(config, stream, ensure_ascii=False)
        host_result = _run(
            [node, str(root / "dist/render.js"), str(config_path)],
            cwd=root,
            code="renderer_failed",
        )
        try:
            host = json.loads(host_result.stdout)
        except json.JSONDecodeError as exc:
            raise RenderError("renderer_failed", "renderer returned invalid JSON", 5) from exc
        probe = _probe_output(ffprobe, temporary, int(inputs["frame_count"]))
        os.replace(temporary, output)
        output_installed = True

        package = json.loads((root / "package.json").read_text())
        ffmpeg_version = _run([ffmpeg, "-version"], code="ffmpeg_unavailable").stdout.splitlines()[
            0
        ]
        webgl_renderer = str(host["webgl"]["renderer"])
        acceleration = (
            "software"
            if any(word in webgl_renderer.lower() for word in ("swiftshader", "software"))
            else "hardware_or_system"
        )
        manifest_inputs = {
            "source_record": sha256_file(inputs["source"].record_path),
            "timeline": sha256_file(inputs["timeline_path"]),
            "plan": sha256_file(inputs["plan_path"]),
        }
        if inputs["scene_mode"] == "fixture":
            manifest_inputs.update(
                assets=sha256_file(inputs["assets_path"]),
                fixture_image=sha256_file(inputs["image_path"]),
            )
        else:
            manifest_inputs["source_plan"] = sha256_file(inputs["source_plan_path"])
        render_manifest = RenderManifest(
            schema_version="0.1",
            status="completed",
            source_sha256=inputs["source"].record.original.sha256,
            inputs=manifest_inputs,
            seed=inputs["plan"].seed,
            environment={
                "python": platform.python_version(),
                "node": _run([node, "--version"], code="node_unavailable").stdout.strip(),
                "playwright": package["devDependencies"]["playwright"],
                "chromium": str(host["chromium"]),
                "three": package["dependencies"]["three"],
                "ffmpeg": ffmpeg_version,
                "webgl_vendor": str(host["webgl"]["vendor"]),
                "webgl_renderer": webgl_renderer,
                "acceleration": acceleration,
            },
            ranges=[
                SampleRange(start_sample=0, end_sample=inputs["timeline"].source.duration_samples)
            ],
            outputs=[
                FileRef(
                    path=os.path.relpath(output, manifest_path.parent), sha256=sha256_file(output)
                )
            ],
        )
        descriptor, manifest_temp_name = tempfile.mkstemp(
            dir=manifest_path.parent, prefix=f".{manifest_path.stem}-", suffix=".json"
        )
        manifest_temporary = Path(manifest_temp_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(render_manifest.model_dump_json(indent=2))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(manifest_temporary, manifest_path)
        manifest_temporary = None
        manifest_installed = True
    except RenderError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise RenderError("render_failed", str(exc), 5) from exc
    finally:
        temporary.unlink(missing_ok=True)
        if config_path is not None:
            config_path.unlink(missing_ok=True)
        if manifest_temporary is not None:
            manifest_temporary.unlink(missing_ok=True)
        if output_installed and not manifest_installed:
            output.unlink(missing_ok=True)

    return {
        "ok": True,
        "output": str(output),
        "manifest": str(manifest_path),
        "frame_count": inputs["frame_count"],
        "pulse_frames": inputs["pulse_frames"],
        "probe": probe,
        "readiness": host["readiness"],
        "webgl": host["webgl"],
        "acceleration": acceleration,
    }
