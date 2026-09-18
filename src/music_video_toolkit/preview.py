"""Atomic multi-range preview rendering with material-input cache validation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .contracts import FileRef, PreviewRequest, RenderManifest, SampleRange
from .documents import read_document
from .project import resolve_record_path, sha256_file
from .render import (
    SAMPLE_RATE,
    RenderError,
    _dependency,
    _manifest_inputs,
    _renderer_inputs,
    _run,
    render_minimal,
)


class PreviewError(Exception):
    """A stable preview failure suitable for machine-readable CLI output."""

    def __init__(self, code: str, details: object, exit_code: int = 2):
        super().__init__(str(details))
        self.code = code
        self.details = details
        self.exit_code = exit_code


@dataclass(frozen=True)
class PreviewResult:
    manifest: RenderManifest
    manifest_path: Path
    cached: bool

    def summary(self) -> dict[str, object]:
        return {
            "ok": True,
            "cached": self.cached,
            "manifest": str(self.manifest_path),
            "ranges": len(self.manifest.ranges),
            "outputs": [
                str(resolve_record_path(self.manifest_path, output.path))
                for output in self.manifest.outputs
            ],
            "cache_key": self.manifest.cache_key,
        }


def _load_request(path: Path) -> PreviewRequest:
    try:
        return PreviewRequest.model_validate(read_document(path))
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        details = (
            exc.errors(include_url=False, include_context=False, include_input=False)
            if isinstance(exc, ValidationError)
            else str(exc)
        )
        raise PreviewError("invalid_preview_ranges", details, 4) from exc


def _cache_key(
    source_sha256: str,
    inputs: dict[str, str],
    seed: int,
    profile: dict[str, int],
    request: PreviewRequest,
    review_reel: bool,
) -> str:
    value = {
        "source_sha256": source_sha256,
        "inputs": inputs,
        "seed": seed,
        "profile": profile,
        "ranges": [item.model_dump(mode="json") for item in request.ranges],
        "review_reel": review_reel,
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _validated_cache(
    output_dir: Path,
    cache_key: str,
    inputs: dict[str, str],
    profile,
    ranges: list[SampleRange],
    expected_outputs: list[str],
) -> tuple[RenderManifest, Path] | None:
    manifest_path = output_dir / "preview.render.json"
    try:
        manifest = RenderManifest.model_validate(read_document(manifest_path))
        if (
            manifest.status != "completed"
            or manifest.cache_key != cache_key
            or manifest.inputs != inputs
            or manifest.profile != profile
            or manifest.ranges != ranges
            or [output.path for output in manifest.outputs] != expected_outputs
        ):
            return None
        for output in manifest.outputs:
            path = resolve_record_path(manifest_path, output.path)
            if not path.is_relative_to(output_dir) or not path.is_file():
                return None
            if sha256_file(path) != output.sha256:
                return None
        return manifest, manifest_path
    except (OSError, UnicodeError, ValueError, ValidationError):
        return None


def _write_manifest(path: Path, manifest: RenderManifest) -> None:
    descriptor, name = tempfile.mkstemp(
        dir=path.parent, prefix=".preview-manifest-", suffix=".json"
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(manifest.model_dump_json(indent=2))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _review_reel(job_dir: Path, clips: list[Path]) -> Path:
    ffmpeg = _dependency("ffmpeg")
    list_path = job_dir / ".concat.txt"
    list_path.write_text(
        "".join(f"file '{clip.name}'\n" for clip in clips),
        encoding="utf-8",
    )
    output = job_dir / "review-reel.mp4"
    _run(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(output),
        ],
        cwd=job_dir,
        code="review_reel_failed",
    )
    list_path.unlink(missing_ok=True)
    return output


def render_preview(
    project: Path,
    plan_path: Path,
    ranges_path: Path,
    output_dir: Path,
    *,
    review_reel: bool = False,
) -> PreviewResult:
    project = project.resolve()
    plan_path = plan_path.expanduser().resolve()
    ranges_path = ranges_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    request = _load_request(ranges_path)
    try:
        inputs = _renderer_inputs(project, plan_path)
    except RenderError as exc:
        raise PreviewError(exc.code, exc.details, exc.exit_code) from exc
    duration = inputs["timeline"].source.duration_samples
    profile = inputs["plan"].output
    frame_samples = SAMPLE_RATE * profile.fps_den // profile.fps_num
    for item in request.ranges:
        if item.end_sample > duration:
            raise PreviewError(
                "preview_range_out_of_bounds",
                {"id": item.id, "end_sample": item.end_sample, "duration_samples": duration},
                4,
            )
        if item.start_sample % frame_samples or item.end_sample % frame_samples:
            raise PreviewError(
                "preview_range_not_frame_aligned",
                {"id": item.id, "frame_samples": frame_samples},
                4,
            )
    manifest_inputs = _manifest_inputs(inputs)
    manifest_inputs["preview_request"] = sha256_file(ranges_path)
    manifest_inputs["preview_adapter"] = sha256_file(Path(__file__))
    selected_ranges = [
        SampleRange(start_sample=item.start_sample, end_sample=item.end_sample)
        for item in request.ranges
    ]
    cache_key = _cache_key(
        inputs["source"].record.original.sha256,
        manifest_inputs,
        inputs["plan"].seed,
        profile.model_dump(mode="json"),
        request,
        review_reel,
    )
    expected_outputs = [
        f"{index:02d}-{item.id}.mp4" for index, item in enumerate(request.ranges, 1)
    ]
    if review_reel:
        expected_outputs.append("review-reel.mp4")
    if output_dir.exists():
        cached = _validated_cache(
            output_dir,
            cache_key,
            manifest_inputs,
            profile,
            selected_ranges,
            expected_outputs,
        )
        if cached is not None:
            return PreviewResult(*cached, cached=True)
        raise PreviewError(
            "preview_output_conflict",
            {"path": str(output_dir), "message": "existing preview is incomplete or stale"},
            4,
        )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    job_dir = Path(tempfile.mkdtemp(dir=output_dir.parent, prefix=f".{output_dir.name}-"))
    try:
        clips: list[Path] = []
        environment: dict[str, str] | None = None
        for index, item in enumerate(request.ranges, 1):
            clip = job_dir / f"{index:02d}-{item.id}.mp4"
            try:
                render_minimal(
                    project,
                    plan_path,
                    clip,
                    SampleRange(start_sample=item.start_sample, end_sample=item.end_sample),
                )
            except RenderError as exc:
                raise PreviewError(exc.code, exc.details, exc.exit_code) from exc
            clip_manifest = RenderManifest.model_validate(
                read_document(clip.with_suffix(".mp4.render.json"))
            )
            environment = environment or clip_manifest.environment
            clips.append(clip)
        outputs = list(clips)
        if review_reel:
            outputs.append(_review_reel(job_dir, clips))
        manifest_path = job_dir / "preview.render.json"
        manifest = RenderManifest(
            schema_version="0.1",
            cache_key=cache_key,
            status="completed",
            source_sha256=inputs["source"].record.original.sha256,
            canonical_audio_sha256=inputs["source"].record.canonical.sha256,
            profile=profile,
            inputs=manifest_inputs,
            seed=inputs["plan"].seed,
            environment=environment or {"renderer": "unavailable"},
            ranges=selected_ranges,
            outputs=[FileRef(path=output.name, sha256=sha256_file(output)) for output in outputs],
        )
        _write_manifest(manifest_path, manifest)
        os.replace(job_dir, output_dir)
        return PreviewResult(manifest, output_dir / manifest_path.name, cached=False)
    except PreviewError:
        raise
    except RenderError as exc:
        raise PreviewError(exc.code, exc.details, exc.exit_code) from exc
    except (OSError, ValidationError, ValueError) as exc:
        raise PreviewError("preview_failed", str(exc), 5) from exc
    finally:
        if job_dir.exists():
            shutil.rmtree(job_dir)
