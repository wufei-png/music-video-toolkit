"""Make two checked projectM preset overlays from one soft-harm C preview.

Song media and review artifacts must be written outside the toolkit repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from music_video_toolkit.comparison import compare_previews
from music_video_toolkit.contracts import (
    LandscapeOutputProfile,
    ProviderRequest,
    RenderManifest,
)
from music_video_toolkit.documents import read_document
from music_video_toolkit.project import preflight_source, resolve_record_path, sha256_file
from music_video_toolkit.projectm import run_projectm
from music_video_toolkit.projectm_provider import (
    INTEGRATION,
    LOCK,
    ROOT,
    _checked_runtime,
    approved_preset_ids,
    integration_identity,
)
from music_video_toolkit.provider import validate_provider_request, validate_provider_result

PRESETS = ("study-soft-flow", "study-beat-petals")
RANGES = ((480000, 1056000), (1872000, 2448000), (9120000, 9696000))
MIX = 0.9


def _write(path: Path, value: object) -> None:
    document = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _hash_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _checked_control(project: Path, control_path: Path):
    source = preflight_source(project)
    control = RenderManifest.model_validate(read_document(control_path))
    profile = control.profile or LandscapeOutputProfile()
    if (
        control.status != "completed"
        or control.canonical_audio_sha256 != source.record.canonical.sha256
        or profile != LandscapeOutputProfile()
        or tuple((span.start_sample, span.end_sample) for span in control.ranges) != RANGES
        or len(control.outputs) < len(RANGES)
    ):
        raise ValueError("control must be the completed soft-harm C preview with three S11 ranges")
    clips = []
    for ref in control.outputs[: len(RANGES)]:
        clip = resolve_record_path(control_path, ref.path)
        if not clip.is_file() or sha256_file(clip) != ref.sha256:
            raise ValueError(f"missing or changed control clip: {clip}")
        clips.append(clip)
    return source, control, profile, clips


def _request(job: Path, source, profile, span, preset: Path, preset_project: Path) -> Path:
    parameters = {"preset_id": preset.stem, "policy": "locked-single"}
    request = ProviderRequest.model_validate(
        {
            "schema_version": "0.1",
            "source": {
                "path": str(source.canonical_path),
                "sha256": source.record.canonical.sha256,
                "sample_rate": 48000,
                "duration_samples": source.record.canonical.duration_samples,
            },
            "canonical_audio": {
                "path": str(source.canonical_path),
                "sha256": source.record.canonical.sha256,
            },
            "profile": profile.model_dump(mode="json"),
            "range": span.model_dump(mode="json"),
            "backend": {
                "name": "projectm",
                "version": LOCK["version"],
                "commit": LOCK["commit"],
                "integration_patch_sha256": integration_identity(),
            },
            "project": {"path": str(preset_project), "sha256": sha256_file(preset_project)},
            "assets": [{"path": str(preset), "sha256": sha256_file(preset)}],
            "parameters": parameters,
            "parameters_sha256": _hash_json(parameters),
        }
    )
    path = job / "request.json"
    _write(path, request)
    validate_provider_request(path)
    return path


def _audio_packet_hash(path: Path) -> str:
    result = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-c:a",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip().split("=", 1)[1].lower()


def _overlay(base: Path, provider: Path, destination: Path, frames: int) -> None:
    graph = (
        "[0:v]format=gbrp[base];[1:v]format=gbrp[fx];"
        f"[base][fx]blend=all_expr='min(255,A+{MIX:g}*B)',format=yuv420p[v]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(base),
            "-i",
            str(provider),
            "-filter_complex",
            graph,
            "-map",
            "[v]",
            "-map",
            "0:a:0",
            "-frames:v",
            str(frames),
            "-t",
            f"{frames / 30:.9f}",
            "-fps_mode",
            "cfr",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(destination),
        ],
        check=True,
    )


def _preview(variant: Path, control_path: Path, control, manifests: list[Path], clips: list[Path]):
    directory = variant / "preview"
    directory.mkdir()
    outputs = []
    for index, (base_clip, provider_path, span) in enumerate(
        zip(clips, manifests, control.ranges, strict=True), 1
    ):
        provider = validate_provider_result(
            variant / f"range-{index:02d}" / "request.json", provider_path
        )
        assert provider.video is not None
        visual = resolve_record_path(provider_path, provider.video.path)
        destination = directory / f"{index:02d}-overlay.mp4"
        frames = (span.end_sample - span.start_sample) // 1600
        _overlay(base_clip, visual, destination, frames)
        if _audio_packet_hash(base_clip) != _audio_packet_hash(destination):
            raise ValueError(f"copied audio differs for {destination}")
        outputs.append({"path": destination.name, "sha256": sha256_file(destination)})
    inputs = {
        "preview_request": sha256_file(variant / "study-config.json"),
        "preview_adapter": sha256_file(Path(__file__)),
        "base_preview": sha256_file(control_path),
    }
    for index, (manifest, ref) in enumerate(zip(manifests, control.outputs, strict=False), 1):
        inputs[f"provider_manifest_{index}"] = sha256_file(manifest)
        inputs[f"base_clip_{index}"] = ref.sha256
    preview = RenderManifest(
        schema_version="0.1",
        cache_key=_hash_json({"inputs": inputs, "outputs": outputs}),
        status="completed",
        source_sha256=control.source_sha256,
        canonical_audio_sha256=control.canonical_audio_sha256,
        profile=LandscapeOutputProfile(),
        inputs=inputs,
        seed=control.seed,
        environment={"adapter": "projectm-visual-study-overlay", "audio": "copied-aac"},
        ranges=control.ranges,
        outputs=outputs,
    )
    path = directory / "preview.render.json"
    _write(path, preview)
    return path


def run(project: Path, control_path: Path, checkout: Path, build: Path, output: Path) -> Path:
    project, control_path, checkout, build, output = (
        item.resolve() for item in (project, control_path, checkout, build, output)
    )
    if output.is_relative_to(ROOT) or output.exists() or not output.parent.is_dir():
        raise ValueError("choose a new output directory outside the toolkit repository")
    source, control, profile, clips = _checked_control(project, control_path)
    runtime = _checked_runtime(checkout, build)
    if not set(PRESETS).issubset(approved_preset_ids()):
        raise ValueError("study candidates are not in the approved preset catalog")
    output.mkdir()
    report = {
        "schema_version": "0.1",
        "status": "partial",
        "scope": "checked approved presets; three-range song preview only",
        "canonical_audio_sha256": source.record.canonical.sha256,
        "control_preview_sha256": sha256_file(control_path),
        "runtime": runtime,
        "variants": [],
    }
    previews = []
    for preset_id in PRESETS:
        started = time.monotonic()
        variant = output / preset_id
        variant.mkdir()
        preset = variant / f"{preset_id}.milk"
        shutil.copyfile(INTEGRATION / "presets" / preset.name, preset)
        preset_project = variant / "project.json"
        _write(preset_project, {"preset": {"path": preset.name, "sha256": sha256_file(preset)}})
        _write(
            variant / "study-config.json",
            {
                "schema_version": "0.1",
                "preset_id": preset_id,
                "mix": MIX,
                "control_preview_sha256": sha256_file(control_path),
            },
        )
        manifests = []
        jobs = []
        for index, span in enumerate(control.ranges, 1):
            job = variant / f"range-{index:02d}"
            job.mkdir()
            request_path = _request(job, source, profile, span, preset, preset_project)
            result = run_projectm(request_path, job / "provider", checkout=checkout, build=build)
            provider_path = Path(result["manifest"])
            validate_provider_result(request_path, provider_path)
            manifests.append(provider_path)
            jobs.append(
                {
                    "range": span.model_dump(mode="json"),
                    "provider_manifest_sha256": sha256_file(provider_path),
                }
            )
            print(f"{preset_id}: provider range {index}/3", flush=True)
        preview = _preview(variant, control_path, control, manifests, clips)
        previews.append(preview)
        report["variants"].append(
            {
                "id": preset_id,
                "preset_sha256": sha256_file(preset),
                "preview_manifest_sha256": sha256_file(preview),
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "ranges": jobs,
            }
        )
        _write(output / "qa.partial.json", report)
    comparison_request = output / "comparison-request.json"
    _write(
        comparison_request,
        {
            "schema_version": "0.1",
            "variants": [
                {
                    "id": "soft-harm-c",
                    "label": "Accepted C control",
                    "preview_manifest_path": str(control_path),
                },
                *(
                    {"id": preset_id, "label": preset_id, "preview_manifest_path": str(preview)}
                    for preset_id, preview in zip(PRESETS, previews, strict=True)
                ),
            ],
        },
    )
    comparison = compare_previews(comparison_request, output / "comparison")
    report["status"] = "completed-technical-review"
    report["comparison_sha256"] = sha256_file(comparison.manifest_path)
    _write(output / "qa.json", report)
    (output / "qa.partial.json").unlink(missing_ok=True)
    return comparison.manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--control-preview", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(run(args.project, args.control_preview, args.checkout, args.build, args.output))


if __name__ == "__main__":
    main()
