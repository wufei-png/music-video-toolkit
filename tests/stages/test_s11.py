import json
from pathlib import Path

import pytest

from music_video_toolkit.cli import main
from music_video_toolkit.comparison import ComparisonError, compare_previews
from music_video_toolkit.contracts import ComparisonManifest, ComparisonMediaProbe
from music_video_toolkit.project import sha256_file

HASHES = {
    "original": "0" * 64,
    "canonical": "1" * 64,
    "timeline": "2" * 64,
    "plan-a": "a" * 64,
    "plan-b": "b" * 64,
    "audio-1": "3" * 64,
    "audio-2": "4" * 64,
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
) -> Path:
    directory = root / variant
    directory.mkdir()
    outputs = []
    for index in range(2):
        clip = directory / f"0{index + 1}-range-{index + 1}.mp4"
        clip.write_bytes(f"{variant}-clip-{index + 1}".encode())
        outputs.append({"path": clip.name, "sha256": sha256_file(clip)})
    manifest = {
        "schema_version": "0.1",
        "cache_key": ("5" if variant == "a" else "6") * 64,
        "status": "completed",
        "source_sha256": HASHES["original"],
        "canonical_audio_sha256": canonical,
        "inputs": {
            "timeline": HASHES["timeline"],
            "plan": HASHES[f"plan-{variant}"],
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
            width=1920,
            height=1080,
            fps_num=30,
            fps_den=1,
            frame_count=30,
            has_audio=True,
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
