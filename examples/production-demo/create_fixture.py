#!/usr/bin/env python3
"""Create deterministic local inputs for the public production workflow demo."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shlex
import struct
import wave
import zlib
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def write_background(path: Path) -> None:
    width, height = 96, 54
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            distance = math.hypot(x - width / 2, y - height / 2)
            glow = max(0, round(90 - distance * 2))
            rows.extend((18 + glow, 24 + glow // 2, 48 + glow, 255))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(bytes(rows)))
        + png_chunk(b"IEND", b"")
    )


def write_audio(path: Path) -> None:
    sample_rate = 48_000
    frames = bytearray()
    for sample in range(3 * sample_rate):
        second = sample / sample_rate
        envelope = 0.18 if second < 1 else 0.45 if second < 2 else 0.8
        tone = math.sin(2 * math.pi * 110 * second) + 0.35 * math.sin(2 * math.pi * 220 * second)
        pulse = 0.0
        for onset in (1.0, 2.0):
            distance = second - onset
            if 0 <= distance < 0.03:
                pulse += math.sin(2 * math.pi * 880 * distance) * (1 - distance / 0.03)
        value = round(max(-1, min(1, envelope * 0.45 * tone + 0.35 * pulse)) * 28_000)
        frames.extend(struct.pack("<hh", value, value))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(frames)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def quoted(path: Path) -> str:
    return shlex.quote(str(path.resolve()))


def create_fixture(output: Path, review_mode: str) -> None:
    output = output.expanduser().resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing demo directory: {output}")
    project = output / "project"
    media = project / "media"
    media.mkdir(parents=True)
    audio = output / "synthetic-song.wav"
    background = media / "background.png"
    write_audio(audio)
    write_background(background)
    write_json(
        output / "brief.json",
        {
            "demo_version": "1",
            "title": "Synthetic three-part production demo",
            "visual_mode": "hybrid",
            "lyrics_mode": "off",
            "review_mode": review_mode,
            "output": {"width": 1920, "height": 1080, "fps_num": 30, "fps_den": 1},
            "source_note": "Deterministic synthetic tone and image; no external rights required",
        },
    )
    write_json(
        project / "assets.json",
        {
            "schema_version": "0.1",
            "assets": [
                {
                    "id": "background",
                    "path": "media/background.png",
                    "type": "image",
                    "sha256": sha256(background),
                    "origin": "synthetic",
                    "license": "MIT project fixture",
                    "source_note": "Generated deterministically by create_fixture.py",
                }
            ],
        },
    )
    write_json(
        project / "visual-plan.json",
        {
            "schema_version": "0.1",
            "timeline_path": "timeline.json",
            "assets_path": "assets.json",
            "mode": "hybrid",
            "seed": 909,
            "layers": [
                {
                    "id": "mood-background",
                    "kind": "image",
                    "category": "media",
                    "asset_id": "background",
                    "opacity": 0.72,
                    "parameters": {"fit": "cover", "motion": 0.03, "z": -5},
                },
                {
                    "id": "energy-orb",
                    "kind": "orb",
                    "category": "abstract",
                    "opacity": 0.85,
                    "parameters": {"x": -0.25, "color": "#7de3ff"},
                },
                {
                    "id": "energy-particles",
                    "kind": "particles",
                    "category": "abstract",
                    "opacity": 0.55,
                    "parameters": {"count": 180, "color": "#ffd27d"},
                },
            ],
            "routes": [
                {
                    "source": "mix.rms",
                    "target_layer": "energy-orb",
                    "target_parameter": "radius",
                    "transform": {"kind": "linear", "parameters": {"min": 0.18, "max": 0.72}},
                },
                {
                    "source": "mix.rms",
                    "target_layer": "energy-particles",
                    "target_parameter": "size",
                    "transform": {
                        "kind": "smooth",
                        "parameters": {
                            "min": 0.01,
                            "max": 0.07,
                            "attack_seconds": 0.08,
                            "release_seconds": 0.25,
                        },
                    },
                },
            ],
            "lyrics": {"mode": "off"},
        },
    )
    write_json(
        project / "preview.json",
        {
            "schema_version": "0.1",
            "ranges": [
                {"id": "sparse", "role": "sparse", "start_sample": 0, "end_sample": 24000},
                {
                    "id": "transition",
                    "role": "transition",
                    "start_sample": 48000,
                    "end_sample": 72000,
                },
                {
                    "id": "climax",
                    "role": "climax",
                    "start_sample": 96000,
                    "end_sample": 120000,
                },
            ],
        },
    )
    (output / "feedback.md").write_text(
        "# Demo feedback\n\n"
        + (
            "Status: awaiting explicit sample feedback before full render.\n"
            if review_mode == "sample-approval"
            else "Status: autonomous first cut; self-review is not user approval.\n"
        ),
        encoding="utf-8",
    )
    commands = [
        "mvt capabilities",
        "mvt doctor",
        f"mvt decode {quoted(audio)} --project {quoted(project)}",
        f"mvt analyze --project {quoted(project)} --stems none",
        f"mvt assets check --project {quoted(project)}",
        (
            f"mvt plan resolve --project {quoted(project)} "
            f"--plan {quoted(project / 'visual-plan.json')}"
        ),
        (
            f"mvt preview --project {quoted(project)} "
            f"--plan {quoted(project / 'resolved-plan.json')} "
            f"--ranges {quoted(project / 'preview.json')} "
            f"--output {quoted(output / 'preview')} --review-reel"
        ),
    ]
    if review_mode == "autonomous":
        commands.append(
            f"mvt render --project {quoted(project)} "
            f"--plan {quoted(project / 'resolved-plan.json')} "
            f"--output {quoted(output / 'first-cut.mp4')}"
        )
    script = "#!/bin/sh\nset -eu\n" + "\n".join(commands) + "\n"
    run_path = output / "run-workflow.sh"
    run_path.write_text(script, encoding="utf-8")
    os.chmod(run_path, 0o755)
    preview_script = (
        "#!/bin/sh\nset -eu\n"
        'target=${1:?"usage: rerender-preview.sh OUTPUT_DIR"}\n'
        f"mvt preview --project {quoted(project)} "
        f"--plan {quoted(project / 'resolved-plan.json')} "
        f'--ranges {quoted(project / "preview.json")} --output "$target" --review-reel\n'
    )
    preview_path = output / "rerender-preview.sh"
    preview_path.write_text(preview_script, encoding="utf-8")
    os.chmod(preview_path, 0o755)
    if review_mode == "autonomous":
        full_script = (
            "#!/bin/sh\nset -eu\n"
            'target=${1:?"usage: rerender-first-cut.sh OUTPUT.mp4"}\n'
            f"mvt render --project {quoted(project)} "
            f'--plan {quoted(project / "resolved-plan.json")} --output "$target"\n'
        )
        full_path = output / "rerender-first-cut.sh"
        full_path.write_text(full_script, encoding="utf-8")
        os.chmod(full_path, 0o755)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--review-mode", choices=("sample-approval", "autonomous"), default="sample-approval"
    )
    args = parser.parse_args()
    create_fixture(args.output, args.review_mode)


if __name__ == "__main__":
    main()
