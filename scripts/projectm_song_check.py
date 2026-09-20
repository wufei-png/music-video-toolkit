"""Compare checked projectM jobs against an existing landscape same-song preview.

All requests, media, song paths, and QA stay in the caller's external output.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from music_video_toolkit.comparison import compare_previews
from music_video_toolkit.contracts import LandscapeOutputProfile, ProviderRequest, RenderManifest
from music_video_toolkit.documents import read_document
from music_video_toolkit.project import preflight_source, resolve_record_path, sha256_file
from music_video_toolkit.projectm import run_projectm
from music_video_toolkit.projectm_provider import (
    INTEGRATION,
    LOCK,
    approved_preset_ids,
    integration_identity,
)
from music_video_toolkit.provider import validate_provider_result
from music_video_toolkit.provider_bundle import bundle_provider_previews
from music_video_toolkit.provider_composition import compose_provider_preview


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _request(
    directory: Path, *, source, profile, sample_range, preset: Path, preset_project: Path
) -> Path:
    parameters = {"preset_id": preset.stem, "policy": "locked-single"}
    parameter_hash = hashlib.sha256(
        json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
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
            "range": sample_range.model_dump(mode="json"),
            "backend": {
                "name": "projectm",
                "version": LOCK["version"],
                "commit": LOCK["commit"],
                "integration_patch_sha256": integration_identity(),
            },
            "project": {"path": str(preset_project), "sha256": sha256_file(preset_project)},
            "assets": [{"path": str(preset), "sha256": sha256_file(preset)}],
            "parameters": parameters,
            "parameters_sha256": parameter_hash,
        }
    )
    path = directory / "request.json"
    path.write_text(request.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--lyrics", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--control-preview", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preset-id", choices=approved_preset_ids(), default="mvt-wave")
    args = parser.parse_args()
    source = preflight_source(args.project)
    control = RenderManifest.model_validate(read_document(args.control_preview))
    profile = control.profile or LandscapeOutputProfile()
    if (
        control.status != "completed"
        or control.canonical_audio_sha256 != source.record.canonical.sha256
        or (
            profile.width,
            profile.height,
            profile.fps_num,
            profile.fps_den,
        )
        != (1920, 1080, 30, 1)
        or not control.ranges
    ):
        parser.error("control preview is not the matching completed 1920x1080/30 song")
    first_clip = resolve_record_path(args.control_preview, control.outputs[0].path)
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate",
            "-of",
            "json",
            str(first_clip),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    if (stream["width"], stream["height"], stream["r_frame_rate"]) != (1920, 1080, "30/1"):
        parser.error("control clip does not match the bounded projectM profile")
    for span in control.ranges:
        if span.start_sample % 1600 or span.end_sample % 1600:
            parser.error("control range is not on a 30 fps frame boundary")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    preset = output / f"{args.preset_id}.milk"
    shutil.copyfile(INTEGRATION / "presets" / preset.name, preset)
    preset_project = output / "project.json"
    _write(preset_project, {"preset": {"path": preset.name, "sha256": sha256_file(preset)}})
    report: dict[str, object] = {
        "schema_version": "0.1",
        "source_sha256": source.record.canonical.sha256,
        "control_preview_sha256": sha256_file(args.control_preview),
        "backend_commit": LOCK["commit"],
        "integration_patch_sha256": integration_identity(),
        "preset_id": args.preset_id,
        "preset_sha256": sha256_file(preset),
        "ranges": [],
    }
    compositions = []
    for index, span in enumerate(control.ranges, 1):
        job = output / f"range-{index:02d}"
        job.mkdir()
        request_path = _request(
            job,
            source=source,
            profile=profile,
            sample_range=span,
            preset=preset,
            preset_project=preset_project,
        )
        started = time.monotonic()
        result = run_projectm(
            request_path, job / "provider", checkout=args.checkout, build=args.build
        )
        elapsed = time.monotonic() - started
        validate_provider_result(request_path, Path(result["manifest"]))
        composed = compose_provider_preview(
            args.project,
            request_path,
            Path(result["manifest"]),
            args.timeline,
            job / "composed",
            lyrics_path=args.lyrics,
            font_path=args.font,
        )
        compositions.append(Path(composed["composition"]))
        report["ranges"].append(
            {
                "range": span.model_dump(mode="json"),
                "pre_roll_frames": span.start_sample // 1600,
                "provider_elapsed_seconds": round(elapsed, 3),
                "video_sha256": result["video_sha256"],
                "composed_clip_sha256": sha256_file(Path(composed["clip"])),
            }
        )
        _write(output / "qa.partial.json", report)
        print(f"completed range {index}/{len(control.ranges)} in {elapsed:.1f}s", flush=True)
    bundle = bundle_provider_previews(compositions, output / "projectm-preview")
    comparison_request = output / "comparison-request.json"
    _write(
        comparison_request,
        {
            "schema_version": "0.1",
            "variants": [
                {
                    "id": "mvt-built-in",
                    "label": "MVT built-in abstract",
                    "preview_manifest_path": str(args.control_preview.resolve()),
                },
                {
                    "id": "projectm",
                    "label": f"projectM locked {args.preset_id}",
                    "preview_manifest_path": bundle["manifest"],
                },
            ],
        },
    )
    comparison = compare_previews(comparison_request, output / "comparison")
    report["projectm_preview_sha256"] = sha256_file(Path(bundle["manifest"]))
    report["comparison_sha256"] = sha256_file(comparison.manifest_path)
    report["comparison"] = str(comparison.manifest_path)
    _write(output / "qa.json", report)
    (output / "qa.partial.json").unlink()
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
