import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from music_video_toolkit.cli import main
from music_video_toolkit.comparison import (
    ComparisonError,
    _contact_frame_size,
    compare_previews,
)
from music_video_toolkit.contracts import (
    ComparisonManifest,
    ComparisonMediaProbe,
    ComparisonProfile,
)
from music_video_toolkit.project import sha256_file

ROOT = Path(__file__).resolve().parents[2]

HASHES = {
    "original": "0" * 64,
    "canonical": "1" * 64,
    "timeline": "2" * 64,
    "plan-a": "a" * 64,
    "plan-b": "b" * 64,
    "audio-1": "3" * 64,
    "audio-2": "4" * 64,
    "stream": "7" * 64,
    "preview-request": "8" * 64,
    "preview-adapter": "9" * 64,
}
RANGES = [
    {"start_sample": 0, "end_sample": 48000},
    {"start_sample": 96000, "end_sample": 144000},
]


def write_preview(
    root: Path,
    variant: str,
    *,
    canonical: str = HASHES["canonical"],
    ranges: list[dict[str, int]] | None = None,
    review_reel: bool = False,
) -> Path:
    directory = root / variant
    directory.mkdir()
    outputs = []
    for index in range(2):
        clip = directory / f"0{index + 1}-range-{index + 1}.mp4"
        clip.write_bytes(f"{variant}-clip-{index + 1}".encode())
        outputs.append({"path": clip.name, "sha256": sha256_file(clip)})
    if review_reel:
        reel = directory / "review-reel.mp4"
        reel.write_bytes(f"{variant}-review-reel".encode())
        outputs.append({"path": reel.name, "sha256": sha256_file(reel)})
    manifest = {
        "schema_version": "0.1",
        "cache_key": ("5" if variant == "a" else "6") * 64,
        "status": "completed",
        "source_sha256": HASHES["original"],
        "canonical_audio_sha256": canonical,
        "profile": {"width": 1920, "height": 1080, "fps_num": 30, "fps_den": 1},
        "inputs": {
            "timeline": HASHES["timeline"],
            "plan": HASHES[f"plan-{variant}"],
            "preview_request": HASHES["preview-request"],
            "preview_adapter": HASHES["preview-adapter"],
        },
        "seed": 1 if variant == "a" else 2,
        "environment": {"renderer": f"synthetic-{variant}"},
        "ranges": ranges or RANGES,
        "outputs": outputs,
    }
    path = directory / "preview.render.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def write_request(path: Path, previews: list[tuple[str, Path]]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "variants": [
                    {
                        "id": variant,
                        "label": f"Variant {variant.upper()}",
                        "preview_manifest_path": str(preview),
                    }
                    for variant, preview in previews
                ],
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def fake_media(monkeypatch):
    monkeypatch.setattr("music_video_toolkit.comparison._dependency", lambda name: name)
    monkeypatch.setattr(
        "music_video_toolkit.comparison._tool_version", lambda path: f"{path} synthetic"
    )

    def probe(ffprobe, ffmpeg, path):
        del ffprobe, ffmpeg
        range_index = 0 if path.name.startswith("01-") else 1
        return ComparisonMediaProbe(
            video_codec="h264",
            video_pixel_format="yuv420p",
            width=1920,
            height=1080,
            fps_num=30,
            fps_den=1,
            avg_fps_num=30,
            avg_fps_den=1,
            frame_count=120 if path.name == "review-reel.mp4" else 30,
            stream_compatibility_sha256=HASHES["stream"],
            has_audio=True,
            audio_codec="aac",
            audio_sha256=HASHES[f"audio-{range_index + 1}"],
            audio_sample_rate=48000,
            audio_channels=2,
        )

    monkeypatch.setattr("music_video_toolkit.comparison._probe_clip", probe)

    def reel(ffmpeg, job_dir, prepared):
        del ffmpeg
        output = job_dir / "review-reel.mp4"
        output.write_bytes(
            b"|".join(path.read_bytes() for path in _ordered_paths_for_test(prepared))
        )
        return output

    def sheet(ffmpeg, job_dir, prepared):
        del ffmpeg, prepared
        output = job_dir / "contact-sheet.png"
        output.write_bytes(b"synthetic contact sheet")
        return output

    monkeypatch.setattr("music_video_toolkit.comparison._build_review_reel", reel)
    monkeypatch.setattr("music_video_toolkit.comparison._build_contact_sheet", sheet)


def _ordered_paths_for_test(prepared):
    return [
        variant.clip_paths[range_index]
        for range_index in range(len(prepared.ranges))
        for variant in prepared.variants
    ]


@pytest.mark.parametrize(
    ("video_codec", "average_rate"),
    [("mpeg4", "30/1"), ("h264", "24/1")],
)
def test_comparison_probe_rejects_unsupported_or_variable_rate_media(
    tmp_path, monkeypatch, video_codec, average_rate
):
    streams = {
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": video_codec,
                "pix_fmt": "yuv420p",
                "width": 320,
                "height": 180,
                "r_frame_rate": "30/1",
                "avg_frame_rate": average_rate,
                "time_base": "1/15360",
                "nb_read_frames": "30",
            },
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_fmt": "fltp",
                "sample_rate": "48000",
                "channels": 2,
                "channel_layout": "stereo",
                "time_base": "1/48000",
            },
        ]
    }

    def run(command, **kwargs):
        del kwargs
        if command[0] == "ffprobe":
            return SimpleNamespace(stdout=json.dumps(streams))
        return SimpleNamespace(stdout=f"SHA256={'8' * 64}\n")

    monkeypatch.setattr("music_video_toolkit.comparison._run", run)
    comparison = __import__("music_video_toolkit.comparison", fromlist=["_probe_clip"])
    with pytest.raises(ComparisonError) as caught:
        comparison._probe_clip("ffprobe", "ffmpeg", tmp_path / "clip.mp4")
    assert caught.value.code == "comparison_media_probe_failed"


def test_compare_command_installs_reuses_and_reorders_range_major(tmp_path, fake_media, capsys):
    preview_a = write_preview(tmp_path, "a")
    preview_b = write_preview(tmp_path, "b")
    request = tmp_path / "request.json"
    write_request(request, [("a", preview_a), ("b", preview_b)])
    output = tmp_path / "comparison"

    assert main(["compare", "--request", str(request), "--output", str(output)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["cached"] is False
    manifest = ComparisonManifest.model_validate(
        json.loads((output / "comparison.json").read_text())
    )
    assert [variant.id for variant in manifest.variants] == ["a", "b"]
    assert (output / "review-reel.mp4").read_bytes() == (b"a-clip-1|b-clip-1|a-clip-2|b-clip-2")

    assert compare_previews(request, output).cached is True
    reproduced = compare_previews(request, tmp_path / "reproduced-output")
    assert reproduced.manifest.cache_key == manifest.cache_key

    reordered = tmp_path / "reordered.json"
    write_request(reordered, [("b", preview_b), ("a", preview_a)])
    reordered_result = compare_previews(reordered, tmp_path / "reordered-output")
    assert reordered_result.manifest.cache_key != manifest.cache_key
    assert [variant.id for variant in reordered_result.manifest.variants] == ["b", "a"]


def test_compare_rejects_source_range_profile_audio_and_hash_mismatches(
    tmp_path, fake_media, monkeypatch
):
    preview_a = write_preview(tmp_path, "a")
    preview_b = write_preview(tmp_path, "b", canonical="f" * 64)
    request = tmp_path / "request.json"
    write_request(request, [("a", preview_a), ("b", preview_b)])
    with pytest.raises(ComparisonError) as caught:
        compare_previews(request, tmp_path / "source-output")
    assert caught.value.code == "comparison_source_mismatch"

    data = json.loads(preview_b.read_text())
    data["canonical_audio_sha256"] = HASHES["canonical"]
    data["ranges"][1].update(start_sample=80000, end_sample=128000)
    preview_b.write_text(json.dumps(data))
    with pytest.raises(ComparisonError) as caught:
        compare_previews(request, tmp_path / "range-output")
    assert caught.value.code == "comparison_range_mismatch"

    data["ranges"] = RANGES
    preview_b.write_text(json.dumps(data))
    original_probe = __import__(
        "music_video_toolkit.comparison", fromlist=["_probe_clip"]
    )._probe_clip

    def mismatched_probe(ffprobe, ffmpeg, path):
        probe = original_probe(ffprobe, ffmpeg, path)
        if path.parent.name == "b":
            return probe.model_copy(update={"width": 1080})
        return probe

    monkeypatch.setattr("music_video_toolkit.comparison._probe_clip", mismatched_probe)
    with pytest.raises(ComparisonError) as caught:
        compare_previews(request, tmp_path / "profile-output")
    assert caught.value.code == "comparison_profile_mismatch"

    def mismatched_audio_probe(ffprobe, ffmpeg, path):
        probe = original_probe(ffprobe, ffmpeg, path)
        if path.parent.name == "b" and path.name.startswith("01-"):
            return probe.model_copy(update={"audio_sha256": "f" * 64})
        return probe

    monkeypatch.setattr("music_video_toolkit.comparison._probe_clip", mismatched_audio_probe)
    with pytest.raises(ComparisonError) as caught:
        compare_previews(request, tmp_path / "audio-output")
    assert caught.value.code == "comparison_audio_mismatch"

    monkeypatch.setattr("music_video_toolkit.comparison._probe_clip", original_probe)
    (preview_b.parent / "01-range-1.mp4").write_bytes(b"tampered")
    with pytest.raises(ComparisonError) as caught:
        compare_previews(request, tmp_path / "hash-output")
    assert caught.value.code == "comparison_input_hash_mismatch"


def test_compare_rejects_completed_full_render_manifests(tmp_path, fake_media):
    preview_a = write_preview(tmp_path, "a")
    preview_b = write_preview(tmp_path, "b")
    full_render = json.loads(preview_b.read_text())
    full_render["inputs"].pop("preview_request")
    full_render["inputs"].pop("preview_adapter")
    full_render["ranges"] = full_render["ranges"][:1]
    full_render["outputs"] = full_render["outputs"][:1]
    preview_b.write_text(json.dumps(full_render), encoding="utf-8")
    request = tmp_path / "request.json"
    write_request(request, [("a", preview_a), ("b", preview_b)])

    with pytest.raises(ComparisonError) as caught:
        compare_previews(request, tmp_path / "comparison")

    assert caught.value.code == "comparison_preview_manifest_required"


def test_compare_rejects_preview_path_aliases(tmp_path, fake_media):
    preview = write_preview(tmp_path, "a")
    alias = preview.parent / ".." / preview.parent.name / preview.name
    request = tmp_path / "request.json"
    write_request(request, [("a", preview), ("alias", alias)])

    with pytest.raises(ComparisonError) as caught:
        compare_previews(request, tmp_path / "comparison")

    assert caught.value.code == "comparison_preview_duplicate"


def test_compare_rejects_stale_or_damaged_output(tmp_path, fake_media):
    preview_a = write_preview(tmp_path, "a")
    preview_b = write_preview(tmp_path, "b")
    request = tmp_path / "request.json"
    write_request(request, [("a", preview_a), ("b", preview_b)])
    output = tmp_path / "comparison"
    result = compare_previews(request, output)
    assert result.cached is False

    (output / "contact-sheet.png").write_bytes(b"damaged")
    with pytest.raises(ComparisonError) as caught:
        compare_previews(request, output)
    assert caught.value.code == "comparison_output_conflict"

    partial = tmp_path / "partial"
    partial.mkdir()
    with pytest.raises(ComparisonError) as caught:
        compare_previews(request, partial)
    assert caught.value.code == "comparison_output_conflict"


def test_compare_rejects_tampered_input_review_reel(tmp_path, fake_media):
    preview_a = write_preview(tmp_path, "a", review_reel=True)
    preview_b = write_preview(tmp_path, "b", review_reel=True)
    request = tmp_path / "request.json"
    write_request(request, [("a", preview_a), ("b", preview_b)])
    (preview_b.parent / "review-reel.mp4").write_bytes(b"tampered")

    with pytest.raises(ComparisonError) as caught:
        compare_previews(request, tmp_path / "comparison")

    assert caught.value.code == "comparison_input_hash_mismatch"


def decode_rgb(path: Path, *, scale: str | None = None) -> bytes:
    command = [shutil.which("ffmpeg") or "ffmpeg", "-nostdin", "-v", "error", "-i", str(path)]
    if scale is not None:
        command.extend(["-vf", f"scale={scale}:flags=neighbor,format=rgb24"])
    command.extend(["-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
    result = subprocess.run(command, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr.decode()
    return result.stdout


def assert_color(actual: bytes, expected: tuple[int, int, int]) -> None:
    assert all(
        abs(channel - target) <= 20 for channel, target in zip(actual, expected, strict=True)
    )


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [(1920, 1080, (480, 270)), (1080, 1920, (270, 480))],
)
def test_contact_sheet_tiles_preserve_supported_profile_aspect(width, height, expected):
    profile = ComparisonProfile(
        video_codec="h264",
        video_pixel_format="yuv420p",
        width=width,
        height=height,
        fps_num=30,
        fps_den=1,
        stream_compatibility_sha256="0" * 64,
        has_audio=True,
        range_count=1,
    )

    assert _contact_frame_size(profile) == expected


@pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe")),
    reason="S11 external tools required",
)
def test_real_abc_review_artifacts_are_ordered_labeled_and_pipeline_isolated(tmp_path, monkeypatch):
    fixture = tmp_path / "public-abc"
    script = ROOT / "tests/fixtures/s11/create_fixture.py"
    generated = subprocess.run(
        [sys.executable, str(script), str(fixture)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stderr
    request = fixture / "comparison-request.json"

    def forbidden(*args, **kwargs):
        del args, kwargs
        raise AssertionError("compare invoked an upstream pipeline stage")

    for target in (
        "music_video_toolkit.analysis.analyze_project",
        "music_video_toolkit.alignment.align_lyrics",
        "music_video_toolkit.plan.resolve_plan",
        "music_video_toolkit.preview.render_preview",
        "music_video_toolkit.render.render_minimal",
    ):
        monkeypatch.setattr(target, forbidden)

    output = tmp_path / "comparison"
    result = compare_previews(request, output)
    assert result.cached is False
    assert compare_previews(request, output).cached is True
    manifest = result.manifest
    assert [variant.id for variant in manifest.variants] == ["a", "b", "c"]
    assert manifest.profile.model_dump(exclude={"stream_compatibility_sha256"}) == {
        "video_codec": "h264",
        "video_pixel_format": "yuv420p",
        "width": 320,
        "height": 180,
        "fps_num": 30,
        "fps_den": 1,
        "has_audio": True,
        "range_count": 2,
    }
    assert len(manifest.profile.stream_compatibility_sha256) == 64
    assert len({variant.inputs["plan"] for variant in manifest.variants}) == 3
    assert len({variant.inputs["assets"] for variant in manifest.variants}) == 3
    assert len({variant.inputs["timeline"] for variant in manifest.variants}) == 1
    assert len({variant.inputs["lyrics"] for variant in manifest.variants}) == 1

    reel_frames = decode_rgb(output / "review-reel.mp4", scale="1:1")
    assert len(reel_frames) == 90 * 3
    expected_colors = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
    ]
    for segment, expected in enumerate(expected_colors):
        frame = segment * 15 + 5
        assert_color(reel_frames[frame * 3 : frame * 3 + 3], expected)

    sheet = decode_rgb(output / "contact-sheet.png")
    width, height = 1440, 600
    assert len(sheet) == width * height * 3
    for range_index in range(2):
        for variant_index, expected in enumerate(
            expected_colors[range_index * 3 : range_index * 3 + 3]
        ):
            label_white = 0
            for y in range(range_index * 300, range_index * 300 + 30):
                for x in range(variant_index * 480, (variant_index + 1) * 480):
                    pixel = (y * width + x) * 3
                    if min(sheet[pixel : pixel + 3]) >= 240:
                        label_white += 1
            assert label_white >= 50
            x = variant_index * 480 + 240
            y = range_index * 300 + 30 + 135
            pixel = (y * width + x) * 3
            assert_color(sheet[pixel : pixel + 3], expected)
