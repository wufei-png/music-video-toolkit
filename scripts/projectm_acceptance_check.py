"""Real synthetic S14 full/excerpt, profile, composition and comparison proof."""

import argparse
import hashlib
import json
import re
import runpy
import subprocess
import tempfile
from pathlib import Path

from music_video_toolkit.audio import decode_audio
from music_video_toolkit.comparison import compare_previews
from music_video_toolkit.lyrics import import_lyrics
from music_video_toolkit.plan import resolve_plan
from music_video_toolkit.preview import render_preview
from music_video_toolkit.project import sha256_file
from music_video_toolkit.projectm import run_projectm
from music_video_toolkit.provider import validate_provider_result
from music_video_toolkit.provider_bundle import bundle_provider_previews
from music_video_toolkit.provider_composition import compose_provider_preview

ROOT = Path(__file__).resolve().parents[1]


def write_request(base: dict, path: Path, start: int, end: int, *, portrait: bool = False) -> Path:
    request = json.loads(json.dumps(base))
    request["range"] = {"start_sample": start * 1600, "end_sample": end * 1600}
    if portrait:
        request["profile"] = {"width": 1080, "height": 1920, "fps_num": 30, "fps_den": 1}
    path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    return path


def raw_frame_hashes(binary: Path, pcm: Path, preset: Path, start: int, end: int) -> list[str]:
    frame_bytes = 1920 * 1080 * 4
    command = [
        str(binary),
        str(pcm),
        str(preset),
        str(preset.parent),
        "1920",
        "1080",
        str(start),
        str(end),
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None and process.stderr is not None
    hashes = []
    for _ in range(end - start):
        frame = process.stdout.read(frame_bytes)
        if len(frame) != frame_bytes:
            raise AssertionError("native renderer wrote an incomplete frame")
        hashes.append(hashlib.sha256(frame).hexdigest())
    if process.stdout.read(1) or process.wait() or process.stderr.read():
        raise AssertionError("native renderer failed or wrote extra frame bytes")
    return hashes


def decoded_excerpt_psnr(full: Path, excerpt: Path) -> float:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(full),
            "-i",
            str(excerpt),
            "-filter_complex",
            "[0:v]trim=start_frame=15:end_frame=20,setpts=PTS-STARTPTS[a];"
            "[1:v]setpts=PTS-STARTPTS[b];[a][b]psnr",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    match = re.search(r"PSNR y:[^\n]*average:([0-9.]+)", result.stderr)
    if not match:
        raise AssertionError("decoded full/excerpt PSNR was not reported")
    score = float(match.group(1))
    if score < 48:
        raise AssertionError(f"decoded excerpt fell below the 48 dB gate: {score}")
    return score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    font = Path("/System/Library/Fonts/SFNSMono.ttf")
    if not font.is_file():
        parser.error(f"local caption font missing: {font}")
    temporary = None
    if args.output:
        directory = args.output.resolve()
        directory.mkdir(parents=True, exist_ok=False)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="mvt-projectm-acceptance-")
        directory = Path(temporary.name)
    try:
        write_fixture = runpy.run_path(str(ROOT / "tests/fixtures/s14/create_fixture.py"))[
            "write_fixture"
        ]
        input_request = write_fixture(directory / "provider-input")
        project = directory / "mvt-project"
        decoded = decode_audio(input_request.parent / "canonical.wav", project)
        timeline_path = project / "timeline.json"
        timeline_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "source": {
                        "path": "source/canonical.wav",
                        "sha256": decoded.record.canonical.sha256,
                        "sample_rate": 48000,
                        "duration_samples": decoded.record.canonical.duration_samples,
                    },
                    "analysis": [],
                    "signals": {},
                    "events": [],
                    "sections": [],
                }
            ),
            encoding="utf-8",
        )
        caption = project / "caption.lrc"
        caption.write_text("[00:00.00]Public projectM sample\n", encoding="utf-8")
        _, lyrics_path, _ = import_lyrics(caption, project, "en")
        base = json.loads(input_request.read_text(encoding="utf-8"))
        base["source"].update(
            path=str(decoded.canonical_path),
            sha256=decoded.record.canonical.sha256,
            duration_samples=decoded.record.canonical.duration_samples,
        )
        base["canonical_audio"] = {
            "path": str(decoded.canonical_path),
            "sha256": decoded.record.canonical.sha256,
        }
        full_request = write_request(base, input_request.parent / "full.json", 0, 30)
        excerpt_request = write_request(base, input_request.parent / "excerpt.json", 15, 20)
        portrait_request = write_request(
            base, input_request.parent / "portrait.json", 15, 20, portrait=True
        )
        full = run_projectm(
            full_request, directory / "full", checkout=args.checkout, build=args.build
        )
        excerpt = run_projectm(
            excerpt_request, directory / "excerpt", checkout=args.checkout, build=args.build
        )
        repeated = run_projectm(
            excerpt_request, directory / "excerpt-repeat", checkout=args.checkout, build=args.build
        )
        portrait = run_projectm(
            portrait_request, directory / "portrait", checkout=args.checkout, build=args.build
        )
        if excerpt["video_sha256"] != repeated["video_sha256"]:
            raise AssertionError("repeat excerpt video differs")
        for name, request in (
            ("full", full_request),
            ("excerpt", excerpt_request),
            ("excerpt-repeat", excerpt_request),
            ("portrait", portrait_request),
        ):
            validate_provider_result(request, directory / name / "provider-manifest.json")
        pcm = directory / "canonical.f32le"
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-i",
                str(decoded.canonical_path),
                "-f",
                "f32le",
                "-ac",
                "2",
                "-ar",
                "48000",
                str(pcm),
            ],
            check=True,
        )
        binary = args.build.resolve() / "mvt-projectm-render"
        preset = input_request.parent / "mvt-wave.milk"
        full_frames = raw_frame_hashes(binary, pcm, preset, 0, 30)
        excerpt_frames = raw_frame_hashes(binary, pcm, preset, 15, 20)
        if full_frames[15:20] != excerpt_frames:
            raise AssertionError("nonzero global excerpt differs from full-run raw frames")
        psnr = decoded_excerpt_psnr(directory / "full/video.mp4", directory / "excerpt/video.mp4")

        composed = compose_provider_preview(
            project,
            excerpt_request,
            Path(excerpt["manifest"]),
            timeline_path,
            directory / "composed",
            lyrics_path=lyrics_path,
            font_path=font,
        )
        portrait_composed = compose_provider_preview(
            project,
            portrait_request,
            Path(portrait["manifest"]),
            timeline_path,
            directory / "portrait-composed",
            lyrics_path=lyrics_path,
            font_path=font,
        )
        rerender = render_preview(
            project,
            Path(composed["resolved_plan"]),
            Path(composed["ranges"]),
            directory / "rerender",
        )
        if sha256_file(Path(composed["clip"])) != sha256_file(
            rerender.manifest_path.parent / "01-provider-range.mp4"
        ):
            raise AssertionError("saved-artifact rerender differs")
        bundle = bundle_provider_previews(
            [Path(composed["composition"])], directory / "provider-bundle"
        )
        assets = project / "assets.json"
        assets.write_text('{"schema_version":"0.1","assets":[]}\n', encoding="utf-8")
        plan = project / "visual-plan.json"
        plan.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "timeline_path": "timeline.json",
                    "assets_path": "assets.json",
                    "mode": "abstract",
                    "seed": 14,
                    "layers": [
                        {
                            "id": "orb",
                            "kind": "orb",
                            "category": "abstract",
                            "parameters": {"radius": 0.6, "color": "#55d6ff"},
                        }
                    ],
                    "lyrics": {"mode": "off"},
                }
            ),
            encoding="utf-8",
        )
        _, resolved = resolve_plan(project, plan, project / "resolved-plan.json")
        ranges = project / "ranges.json"
        ranges.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "ranges": [
                        {
                            "id": "provider-range",
                            "start_sample": 15 * 1600,
                            "end_sample": 20 * 1600,
                            "role": "other",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        built_in = render_preview(project, resolved, ranges, directory / "built-in")
        comparison_request = directory / "comparison-request.json"
        comparison_request.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "variants": [
                        {
                            "id": "projectm",
                            "label": "projectM",
                            "preview_manifest_path": str(bundle["manifest"]),
                        },
                        {
                            "id": "builtin",
                            "label": "Built-in",
                            "preview_manifest_path": str(built_in.manifest_path),
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        comparison = compare_previews(comparison_request, directory / "comparison")
        print(
            json.dumps(
                {
                    "ok": True,
                    "full_sha256": full["video_sha256"],
                    "excerpt_sha256": excerpt["video_sha256"],
                    "portrait_sha256": portrait["video_sha256"],
                    "raw_global_frames_sha256": excerpt_frames,
                    "decoded_full_excerpt_psnr_db": psnr,
                    "composed_clip_sha256": sha256_file(Path(composed["clip"])),
                    "portrait_composed_clip_sha256": sha256_file(Path(portrait_composed["clip"])),
                    "comparison": str(comparison.manifest_path),
                },
                indent=2,
            )
        )
    finally:
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    main()
