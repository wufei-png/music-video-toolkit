import hashlib
import json
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from music_video_toolkit.audio import decode_audio
from music_video_toolkit.cli import main
from music_video_toolkit.contracts import Lyrics
from music_video_toolkit.lyrics import LyricsError, import_lyrics
from music_video_toolkit.plan import PlanError, resolve_plan
from music_video_toolkit.render import render_minimal


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_fixture(tmp_path: Path, seconds: float = 3.0) -> Path:
    original = tmp_path / "silence.wav"
    with wave.open(str(original), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(48_000)
        wav.writeframes(b"\0" * int(seconds * 48_000) * 4)
    project = tmp_path / "project"
    source = decode_audio(original, project)
    (project / "timeline.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "source": {
                    "path": "source/canonical.wav",
                    "sha256": source.record.canonical.sha256,
                    "sample_rate": 48_000,
                    "duration_samples": int(seconds * 48_000),
                },
                "analysis": [],
                "signals": {},
                "events": [],
                "sections": [],
            }
        ),
        encoding="utf-8",
    )
    return project


def write_assets(project: Path, with_font: bool) -> str | None:
    assets = []
    font_id = None
    if with_font:
        font = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
        font_id = "subtitle-font"
        assets.append(
            {
                "id": font_id,
                "path": str(font),
                "type": "font",
                "sha256": sha256(font),
                "origin": "synthetic",
                "license": "Apple system font; local acceptance only",
                "source_note": "Not copied or claimed as a portable project asset",
            }
        )
    (project / "assets.json").write_text(
        json.dumps({"schema_version": "0.1", "assets": assets}), encoding="utf-8"
    )
    return font_id


def abstract_plan(lyrics: dict | None = None) -> dict:
    return {
        "schema_version": "0.1",
        "timeline_path": "timeline.json",
        "assets_path": "assets.json",
        "mode": "abstract",
        "seed": 606,
        "layers": [{"id": "orb", "kind": "orb", "category": "abstract"}],
        "routes": [],
        "sections": [],
        "lyrics": lyrics or {"mode": "off"},
    }


def lower_frame(path: Path, frame: int) -> bytes:
    result = subprocess.run(
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            f"select='eq(n,{frame})',crop=1600:238:160:799,format=gray",
            "-vsync",
            "0",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode()
    return result.stdout


def test_lrc_import_records_end_rule_and_preserves_repeated_text(tmp_path):
    project = project_fixture(tmp_path)
    source = tmp_path / "bilingual.lrc"
    source.write_text(
        "[ar:Synthetic]\n[00:00.50]第一句！\n[00:01.25][Chorus]\n"
        "[00:01.50]Repeat, repeat.\n[00:02.00]Repeat, repeat.\n",
        encoding="utf-8",
    )
    lyrics, output, cached = import_lyrics(source, project, "zh+en")
    assert cached is False
    assert [cue.start_sample for cue in lyrics.cues] == [24_000, 72_000, 96_000]
    assert [cue.end_sample for cue in lyrics.cues] == [72_000, 96_000, 144_000]
    assert [cue.text for cue in lyrics.cues[-2:]] == ["Repeat, repeat."] * 2
    assert lyrics.provenance.parameters["end_time_policy"] == "next_start_or_song_end"
    assert lyrics.provenance.parameters["skipped_stage_headings"] == 1
    assert lyrics.text_source_sha256 == sha256(source)
    assert import_lyrics(source, project, "zh+en")[2] is True

    edited = json.loads(output.read_text())
    edited["origin"] = "edited"
    edited["cues"][0]["text"] = "手工修正"
    output.write_text(json.dumps(edited), encoding="utf-8")
    with pytest.raises(LyricsError) as caught:
        import_lyrics(source, project, "zh+en")
    assert caught.value.code == "lyrics_output_conflict"
    assert json.loads(output.read_text())["cues"][0]["text"] == "手工修正"


def test_cli_import_emits_saved_cue_summary(tmp_path, capsys):
    project = project_fixture(tmp_path)
    source = tmp_path / "captions.lrc"
    source.write_text("[00:00.00]开始\n[00:01.00]End\n", encoding="utf-8")
    command = [
        "lyrics",
        "import",
        str(source),
        "--project",
        str(project),
        "--language",
        "zh+en",
    ]
    assert main(command) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["cues"] == 2
    assert Lyrics.model_validate_json((project / "lyrics.json").read_text()).cues[1].text == "End"


def test_srt_import_preserves_multiline_and_rejects_overlap(tmp_path):
    project = project_fixture(tmp_path)
    source = tmp_path / "captions.srt"
    source.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\n你好，世界！\nHello, world!\n\n"
        "2\n00:00:01,200 --> 00:00:02,800\nLong punctuation: one, two; three?\n",
        encoding="utf-8",
    )
    lyrics, _, _ = import_lyrics(source, project, "zh+en")
    assert lyrics.cues[0].text == "你好，世界！\nHello, world!"
    assert (lyrics.cues[0].start_sample, lyrics.cues[0].end_sample) == (0, 48_000)

    source.write_text(
        "1\n00:00:00,000 --> 00:00:01,500\nFirst\n\n2\n00:00:01,000 --> 00:00:02,000\nSecond\n",
        encoding="utf-8",
    )
    with pytest.raises(LyricsError) as caught:
        import_lyrics(source, project, "en", project / "overlap.json")
    assert caught.value.code == "overlapping_lyrics"


def test_off_mode_does_not_read_invalid_default_lyrics(tmp_path):
    project = project_fixture(tmp_path, 1.0)
    write_assets(project, with_font=False)
    (project / "lyrics.json").write_text("{invalid", encoding="utf-8")
    plan = project / "plan.json"
    plan.write_text(json.dumps(abstract_plan()), encoding="utf-8")
    resolved, _ = resolve_plan(project, plan)
    assert resolved.lyrics.mode == "off"
    assert resolved.lyrics_sha256 is None


def test_resolver_rejects_wrong_audio_or_font_identity(tmp_path):
    project = project_fixture(tmp_path)
    font_id = write_assets(project, with_font=True)
    source = tmp_path / "captions.srt"
    source.write_text("1\n00:00:00,000 --> 00:00:01,000\nText\n", encoding="utf-8")
    _, lyrics_path, _ = import_lyrics(source, project, "en")
    plan = project / "plan.json"
    plan.write_text(
        json.dumps(
            abstract_plan({"mode": "imported", "path": "lyrics.json", "font_asset_id": font_id})
        ),
        encoding="utf-8",
    )
    lyrics = json.loads(lyrics_path.read_text())
    lyrics["audio_sha256"] = "0" * 64
    lyrics_path.write_text(json.dumps(lyrics), encoding="utf-8")
    with pytest.raises(PlanError) as caught:
        resolve_plan(project, plan)
    assert caught.value.code == "lyrics_audio_mismatch"

    plan_document = json.loads(plan.read_text())
    plan_document["lyrics"]["font_asset_id"] = "unknown-font"
    plan.write_text(json.dumps(plan_document), encoding="utf-8")
    lyrics["audio_sha256"] = json.loads((project / "source/source.json").read_text())["canonical"][
        "sha256"
    ]
    lyrics_path.write_text(json.dumps(lyrics), encoding="utf-8")
    with pytest.raises(PlanError) as caught:
        resolve_plan(project, plan)
    assert caught.value.code == "invalid_lyrics_font"


@pytest.mark.skipif(
    not all(shutil.which(name) for name in ("ffmpeg", "ffprobe", "node", "pnpm", "mdls")),
    reason="render and macOS font dependencies required",
)
def test_bilingual_captions_render_on_exact_cues_with_safe_interlude(tmp_path):
    project = project_fixture(tmp_path, 2.5)
    font_id = write_assets(project, with_font=True)
    source = tmp_path / "captions.srt"
    source.write_text(
        "1\n00:00:00,000 --> 00:00:00,800\n你好，世界！\nHello, world!\n\n"
        "2\n00:00:01,200 --> 00:00:02,500\n"
        "长句与标点保持在安全边距内。\nA long sentence stays inside the safe title area.\n",
        encoding="utf-8",
    )
    import_lyrics(source, project, "zh+en")
    plan = project / "plan.json"
    plan.write_text(
        json.dumps(
            abstract_plan({"mode": "imported", "path": "lyrics.json", "font_asset_id": font_id})
        ),
        encoding="utf-8",
    )
    resolved, resolved_path = resolve_plan(project, plan, project / "plans/resolved.json")
    assert resolved.lyrics.path == "../lyrics.json"
    output = project / "bilingual.mp4"
    report = render_minimal(project, resolved_path, output)
    assert report["frame_count"] == 75
    first, interlude, second = (lower_frame(output, frame) for frame in (10, 30, 50))
    assert sha256_bytes(first) != sha256_bytes(interlude)
    assert sha256_bytes(second) != sha256_bytes(interlude)
    assert min(first) < max(first) and min(second) < max(second)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
