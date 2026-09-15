import json
import wave
from pathlib import Path

import pytest

from music_video_toolkit.alignment import AlignmentError, align_lyrics, apply_alignment_edits
from music_video_toolkit.audio import decode_audio
from music_video_toolkit.cli import main
from music_video_toolkit.contracts import AlignmentReport, Lyrics


def project_fixture(tmp_path: Path, seconds: float = 15.0) -> Path:
    original = tmp_path / "silence.wav"
    with wave.open(str(original), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(48_000)
        wav.writeframes(b"\0" * int(seconds * 48_000) * 4)
    project = tmp_path / "project"
    decode_audio(original, project)
    return project


def fake_runner(tmp_path: Path, words: list[tuple[str, float, float]]) -> Path:
    path = tmp_path / "fake_alignment.py"
    segments = [
        {
            "start": words[0][1],
            "end": words[-1][2],
            "text": " " + " ".join(word for word, _, _ in words),
            "words": [
                {"word": f" {word}", "start": start, "end": end, "score": 0.9}
                for word, start, end in words
            ],
        }
    ]
    path.write_text(
        """import argparse, json
p=argparse.ArgumentParser()
p.add_argument('--output', required=True)
p.add_argument('--audio'); p.add_argument('--language'); p.add_argument('--model')
p.add_argument('--model-dir'); p.add_argument('--threads')
a=p.parse_args()
document={
  'runtime': {'tool':'fake-whisperx','version':'3.8.6','model':a.model,
              'device':'cpu','compute_type':'int8','vad_method':'pyannote'},
  'segments': SEGMENTS,
  'elapsed_seconds': 0.01,
}
open(a.output, 'w', encoding='utf-8').write(json.dumps(document))
""".replace("SEGMENTS", repr(segments)),
        encoding="utf-8",
    )
    return path


def configure_runner(monkeypatch, runner: Path, model_dir: Path):
    monkeypatch.setenv("MVT_ALIGNMENT_RUNNER", str(runner))
    monkeypatch.setenv("MVT_ALIGNMENT_MODEL_DIR", str(model_dir))


def test_known_text_mapping_preserves_repetitions_and_lists_unmatched(tmp_path, monkeypatch):
    project = project_fixture(tmp_path)
    runner = fake_runner(
        tmp_path,
        [
            ("alpha", 0.1, 0.4),
            ("moon", 0.45, 0.8),
            ("repeat", 1.2, 1.6),
            ("light", 1.65, 2.0),
            ("sparse", 4.0, 4.4),
            ("cloud", 4.5, 4.9),
            ("repeat", 7.0, 7.4),
            ("light", 7.45, 7.8),
        ],
    )
    configure_runner(monkeypatch, runner, tmp_path / "models")
    text = tmp_path / "lyrics.md"
    text.write_text(
        "# Song\n[Verse]\nalpha moon\nrepeat light\nsparse cloud\nrepeat light\nunheard ending\n",
        encoding="utf-8",
    )
    result = align_lyrics(text, project, "en")
    assert [cue.text for cue in result.lyrics.cues] == [
        "alpha moon",
        "repeat light",
        "sparse cloud",
        "repeat light",
    ]
    repeated = [cue.start_sample for cue in result.lyrics.cues if cue.text == "repeat light"]
    assert repeated[0] < repeated[1]
    assert [(line.source_line, line.status) for line in result.report.lines][-1] == (
        7,
        "unmatched",
    )
    assert result.report.audio_kind == "canonical"
    assert result.report.audio_offset_samples == 0
    assert result.lyrics.origin == "aligned"
    assert result.lyrics.text_source_sha256 == result.report.text_source.sha256
    assert all(
        first.end_sample <= second.start_sample
        for first, second in zip(result.lyrics.cues, result.lyrics.cues[1:], strict=False)
    )
    assert result.lyrics.cues[-1].end_sample <= 15 * 48_000
    assert align_lyrics(text, project, "en").cached is True

    document = json.loads(result.lyrics_path.read_text())
    document["origin"] = "edited"
    document["cues"][0]["start_sample"] += 100
    result.lyrics_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(AlignmentError) as caught:
        align_lyrics(text, project, "en")
    assert caught.value.code == "alignment_output_conflict"
    assert Lyrics.model_validate_json(result.lyrics_path.read_text()).origin == "edited"


def test_reference_metrics_use_fixed_median_and_nearest_rank_p90(tmp_path, monkeypatch):
    project = project_fixture(tmp_path, 20.0)
    tokens = [f"token{chr(97 + index)}" for index in range(12)]
    words = [(token, 0.5 + index, 0.8 + index) for index, token in enumerate(tokens)]
    runner = fake_runner(tmp_path, words)
    configure_runner(monkeypatch, runner, tmp_path / "models")
    text = tmp_path / "lyrics.txt"
    text.write_text("\n".join([*tokens, "missingword"]) + "\n", encoding="utf-8")
    audio_hash = json.loads((project / "source/source.json").read_text())["canonical"]["sha256"]
    references = tmp_path / "references.json"
    references.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "audio_sha256": audio_hash,
                "points": [
                    {"source_line": index + 1, "start_sample": round((0.5 + index) * 48_000)}
                    for index in range(12)
                ],
            }
        ),
        encoding="utf-8",
    )
    result = align_lyrics(
        text,
        project,
        "en",
        project / "evaluated.json",
        project / "alignment/evaluated-report.json",
        references,
    )
    assert result.report.evaluation is not None
    assert result.report.evaluation.passed is True
    assert result.report.evaluation.matched_reference_points == 12
    assert result.report.evaluation.unmatched_reference_points == 0
    assert result.report.evaluation.median_absolute_error_samples == 0
    assert result.report.evaluation.p90_absolute_error_samples == 0
    AlignmentReport.model_validate_json(result.report_path.read_text())

    bad = json.loads(references.read_text())
    for point in bad["points"]:
        point["start_sample"] += 30_000
    failed_references = tmp_path / "failed-references.json"
    failed_references.write_text(json.dumps(bad), encoding="utf-8")
    failed = align_lyrics(
        text,
        project,
        "en",
        project / "failed.json",
        project / "alignment/failed-report.json",
        failed_references,
    )
    assert failed.report.evaluation is not None
    assert failed.report.evaluation.passed is False

    missing_candidate = json.loads(references.read_text())
    missing_candidate["points"][-1] = {
        "source_line": 13,
        "start_sample": round(12.5 * 48_000),
    }
    missing_references = tmp_path / "missing-candidate-references.json"
    missing_references.write_text(json.dumps(missing_candidate), encoding="utf-8")
    incomplete = align_lyrics(
        text,
        project,
        "en",
        project / "incomplete.json",
        project / "alignment/incomplete-report.json",
        missing_references,
    )
    assert incomplete.report.evaluation is not None
    assert incomplete.report.evaluation.passed is False
    assert incomplete.report.evaluation.matched_reference_points == 11
    assert incomplete.report.evaluation.unmatched_reference_points == 1


def test_invalid_references_and_missing_runtime_are_explicit(tmp_path, monkeypatch):
    project = project_fixture(tmp_path)
    text = tmp_path / "lyrics.txt"
    text.write_text("one line\n", encoding="utf-8")
    monkeypatch.setenv("MVT_ALIGNMENT_RUNNER", str(tmp_path / "missing.py"))
    with pytest.raises(AlignmentError) as caught:
        align_lyrics(text, project, "en")
    assert caught.value.code == "missing_alignment_runtime"

    runner = fake_runner(tmp_path, [("one", 1.0, 1.2), ("line", 1.3, 1.5)])
    configure_runner(monkeypatch, runner, tmp_path / "models")
    references = tmp_path / "references.json"
    references.write_text(
        json.dumps({"schema_version": "0.1", "audio_sha256": "0" * 64, "points": []}),
        encoding="utf-8",
    )
    with pytest.raises(AlignmentError) as caught:
        align_lyrics(text, project, "en", reference_path=references)
    assert caught.value.code == "invalid_alignment_references"
    assert not (project / "lyrics.aligned.json").exists()


def test_cli_emits_alignment_summary(tmp_path, monkeypatch, capsys):
    project = project_fixture(tmp_path)
    runner = fake_runner(tmp_path, [("hello", 1.0, 1.4), ("world", 1.5, 1.9)])
    configure_runner(monkeypatch, runner, tmp_path / "models")
    text = tmp_path / "lyrics.txt"
    text.write_text("hello world\n", encoding="utf-8")
    assert (
        main(
            [
                "lyrics",
                "align",
                "--text",
                str(text),
                "--project",
                str(project),
                "--language",
                "en",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["cues"] == 1
    assert report["unmatched"] == 0
    assert report["evaluation"] is None


def test_complete_review_edits_fill_unmatched_lines_without_model_rerun(tmp_path, monkeypatch):
    project = project_fixture(tmp_path)
    runner = fake_runner(tmp_path, [("first", 1.0, 1.4), ("third", 7.0, 7.4)])
    configure_runner(monkeypatch, runner, tmp_path / "models")
    text = tmp_path / "lyrics.txt"
    text.write_text("first line\nmissing middle\nthird line\n", encoding="utf-8")
    aligned = align_lyrics(text, project, "en")
    assert [line.status for line in aligned.report.lines] == ["matched", "unmatched", "matched"]
    audio_hash = json.loads((project / "source/source.json").read_text())["canonical"]["sha256"]
    edits = tmp_path / "edits.json"
    edits.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "audio_sha256": audio_hash,
                "points": [
                    {"source_line": 1, "start_sample": 48_000},
                    {"source_line": 2, "start_sample": 4 * 48_000},
                    {"source_line": 3, "start_sample": 7 * 48_000},
                ],
            }
        ),
        encoding="utf-8",
    )
    result = apply_alignment_edits(project, edits)
    assert result.lyrics.origin == "edited"
    assert [cue.text for cue in result.lyrics.cues] == [
        "first line",
        "missing middle",
        "third line",
    ]
    assert [cue.start_sample for cue in result.lyrics.cues] == [48_000, 192_000, 336_000]
    assert result.lyrics.cues[-1].end_sample == 15 * 48_000
    assert apply_alignment_edits(project, edits).cached is True

    changed = json.loads(edits.read_text())
    changed["points"][1]["start_sample"] += 100
    edits.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(AlignmentError) as caught:
        apply_alignment_edits(project, edits)
    assert caught.value.code == "alignment_edit_output_conflict"
