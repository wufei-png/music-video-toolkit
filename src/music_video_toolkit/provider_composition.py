"""Compose a checked silent provider range with MVT audio and saved lyrics."""

import json
import os
import shutil
import tempfile
from pathlib import Path

from .contracts import AssetManifest, PreviewRequest, VisualPlan
from .plan import PlanError, resolve_plan
from .preview import PreviewError, render_preview
from .project import ProjectPreflightError, preflight_source, resolve_record_path, sha256_file
from .provider import ProviderError, validate_provider_request, validate_provider_result


class CompositionError(Exception):
    def __init__(self, code: str, details: object, exit_code: int = 4):
        super().__init__(str(details))
        self.code = code
        self.details = details
        self.exit_code = exit_code


def _relative(target: Path, directory: Path) -> str:
    return os.path.relpath(target.resolve(), directory)


def _write(path: Path, value) -> None:
    data = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compose_provider_preview(
    project: Path,
    request_path: Path,
    manifest_path: Path,
    timeline_path: Path,
    output: Path,
    *,
    lyrics_path: Path | None = None,
    font_path: Path | None = None,
) -> dict[str, object]:
    project = project.resolve()
    request_path = request_path.resolve()
    manifest_path = manifest_path.resolve()
    timeline_path = timeline_path.resolve()
    output = output.resolve()
    if output.exists() or not output.parent.is_dir():
        raise CompositionError("invalid_composition_output", str(output))
    if (lyrics_path is None) != (font_path is None):
        raise CompositionError(
            "incomplete_lyric_inputs", "lyrics and font must be supplied together"
        )
    try:
        source = preflight_source(project)
        manifest = validate_provider_result(request_path, manifest_path)
        provider_request = validate_provider_request(request_path)
    except (ProjectPreflightError, ProviderError) as exc:
        raise CompositionError(exc.code, exc.details) from exc
    if (
        resolve_record_path(request_path, provider_request.canonical_audio.path)
        != source.canonical_path
        or provider_request.source.sha256 != source.record.canonical.sha256
        or provider_request.source.duration_samples != source.record.canonical.duration_samples
    ):
        raise CompositionError("provider_source_mismatch", "provider is not bound to project audio")
    assert manifest.video is not None and manifest.probe is not None
    video_path = resolve_record_path(manifest_path, manifest.video.path)
    if lyrics_path is not None:
        lyrics_path = lyrics_path.resolve()
        font_path = font_path.resolve()
        if not lyrics_path.is_file() or not font_path.is_file():
            raise CompositionError(
                "missing_lyric_input", {"lyrics": str(lyrics_path), "font": str(font_path)}
            )
    job = Path(tempfile.mkdtemp(dir=output.parent, prefix=f".{output.name}.tmp-"))
    try:
        assets = [
            {
                "id": "provider-video",
                "path": _relative(video_path, job),
                "type": "video",
                "sha256": manifest.video.sha256,
                "origin": "harness",
                "source_note": f"{manifest.backend.name} provider manifest {manifest_path}",
            }
        ]
        if font_path is not None:
            assets.append(
                {
                    "id": "caption-font",
                    "path": _relative(font_path, job),
                    "type": "font",
                    "sha256": sha256_file(font_path),
                    "origin": "user",
                }
            )
        assets_path = job / "assets.json"
        _write(assets_path, AssetManifest(schema_version="0.1", assets=assets))
        layer = {
            "id": "provider-video",
            "category": "media",
            "kind": "video",
            "asset_id": "provider-video",
            "parameters": {
                "fit": "cover",
                "offset_samples": manifest.range.start_sample,
                "in_frame": 0,
                "out_frame": manifest.probe.frame_count,
                "end_behavior": "hold",
                "muted": True,
            },
        }
        lyrics = (
            {
                "mode": "imported",
                "path": _relative(lyrics_path, job),
                "font_asset_id": "caption-font",
            }
            if lyrics_path is not None
            else {"mode": "off"}
        )
        plan = VisualPlan.model_validate(
            {
                "schema_version": "0.1",
                "timeline_path": _relative(timeline_path, job),
                "assets_path": "assets.json",
                "mode": "mood",
                "seed": 0,
                "output": manifest.profile.model_dump(mode="json"),
                "layers": [layer],
                "lyrics": lyrics,
            }
        )
        plan_path = job / "plan.json"
        _write(plan_path, plan)
        _, resolved_path = resolve_plan(project, plan_path, job / "resolved-plan.json")
        ranges = PreviewRequest.model_validate(
            {
                "schema_version": "0.1",
                "ranges": [
                    {
                        "id": "provider-range",
                        "start_sample": manifest.range.start_sample,
                        "end_sample": manifest.range.end_sample,
                        "role": "other",
                    }
                ],
            }
        )
        ranges_path = job / "ranges.json"
        _write(ranges_path, ranges)
        preview = render_preview(project, resolved_path, ranges_path, job / "preview")
        binding = {
            "schema_version": "0.1",
            "request": {"path": _relative(request_path, job), "sha256": sha256_file(request_path)},
            "provider_manifest": {
                "path": _relative(manifest_path, job),
                "sha256": sha256_file(manifest_path),
            },
            "provider_video_sha256": manifest.video.sha256,
            "resolved_plan_sha256": sha256_file(resolved_path),
            "preview_manifest_sha256": sha256_file(preview.manifest_path),
            "canonical_audio_sha256": source.record.canonical.sha256,
            "lyrics_sha256": sha256_file(lyrics_path) if lyrics_path is not None else None,
            "profile": manifest.profile.model_dump(mode="json"),
            "range": manifest.range.model_dump(mode="json"),
        }
        _write(job / "provider-composition.json", binding)
        os.replace(job, output)
        return {
            "ok": True,
            "provider": manifest.backend.name,
            "composition": str(output / "provider-composition.json"),
            "resolved_plan": str(output / "resolved-plan.json"),
            "ranges": str(output / "ranges.json"),
            "preview_manifest": str(output / "preview/preview.render.json"),
            "clip": str(output / "preview/01-provider-range.mp4"),
            "canonical_audio_sha256": source.record.canonical.sha256,
            "lyrics_sha256": binding["lyrics_sha256"],
        }
    except (PlanError, PreviewError) as exc:
        raise CompositionError(exc.code, exc.details, exc.exit_code) from exc
    finally:
        shutil.rmtree(job, ignore_errors=True)
