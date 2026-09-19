"""Real public synthetic Astrofox to MVT captioned preview and saved rerender."""

import argparse
import json
import runpy
import tempfile
from pathlib import Path

from music_video_toolkit.astrofox import render_astrofox
from music_video_toolkit.audio import decode_audio
from music_video_toolkit.lyrics import import_lyrics
from music_video_toolkit.preview import render_preview
from music_video_toolkit.project import sha256_file
from music_video_toolkit.provider_composition import compose_provider_preview

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    font = Path("/System/Library/Fonts/SFNSMono.ttf")
    if not font.is_file():
        parser.error(f"synthetic caption check needs a local font: {font}")
    if args.output:
        directory = args.output.resolve()
        directory.mkdir(parents=True, exist_ok=False)
        temporary = None
    else:
        temporary = tempfile.TemporaryDirectory(prefix="mvt-astrofox-compose-")
        directory = Path(temporary.name)
    try:
        write_fixture = runpy.run_path(str(ROOT / "tests/fixtures/s13/create_fixture.py"))[
            "write_fixture"
        ]
        request_path = write_fixture(
            directory / "provider-input", with_plugin=True, with_asset=True
        )
        project = directory / "mvt-project"
        decoded = decode_audio(request_path.parent / "canonical.wav", project)
        timeline = {
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
        timeline_path = project / "timeline.json"
        timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
        caption = project / "caption.lrc"
        caption.write_text("[00:00.00]Public synthetic caption\n", encoding="utf-8")
        _, lyrics_path, _ = import_lyrics(caption, project, "en")
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request["source"] = {
            "path": str(decoded.canonical_path),
            "sha256": decoded.record.canonical.sha256,
            "sample_rate": 48000,
            "duration_samples": decoded.record.canonical.duration_samples,
        }
        request["canonical_audio"] = {
            "path": str(decoded.canonical_path),
            "sha256": decoded.record.canonical.sha256,
        }
        request_path.write_text(json.dumps(request), encoding="utf-8")
        rendered = render_astrofox(
            request_path, directory / "provider-output", checkout=args.checkout.resolve()
        )
        composed = compose_provider_preview(
            project,
            request_path,
            Path(rendered["manifest"]),
            timeline_path,
            directory / "composed",
            lyrics_path=lyrics_path,
            font_path=font,
        )
        rerender = render_preview(
            project,
            Path(composed["resolved_plan"]),
            Path(composed["ranges"]),
            directory / "rerender",
        )
        original_clip = Path(composed["clip"])
        repeated_clip = rerender.manifest_path.parent / "01-provider-range.mp4"
        if sha256_file(original_clip) != sha256_file(repeated_clip):
            raise AssertionError("saved-artifact rerender differs from initial composition")
        print(
            json.dumps(
                {
                    "provider_manifest": rendered["manifest"],
                    "composition": composed["composition"],
                    "clip": composed["clip"],
                    "clip_sha256": sha256_file(original_clip),
                    "rerender_sha256": sha256_file(repeated_clip),
                    "canonical_audio_sha256": decoded.record.canonical.sha256,
                    "lyrics_sha256": sha256_file(lyrics_path),
                },
                indent=2,
            )
        )
    finally:
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    main()
