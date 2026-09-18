"""Generate public synthetic completed previews for an S11 A/B/C comparison."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

SCHEMA_VERSION = "0.1"
RANGES = [
    {"start_sample": 0, "end_sample": 24000},
    {"start_sample": 48000, "end_sample": 72000},
]
VARIANTS = {
    "a": ("Abstract A", ("red", "yellow")),
    "b": ("Mood B", ("lime", "magenta")),
    "c": ("Hybrid C", ("blue", "cyan")),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def generate_clip(ffmpeg: str, path: Path, color: str, frequency: int) -> None:
    result = subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=320x180:r=30:d=0.5",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate=48000:duration=0.5",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-shortest",
            "-y",
            str(path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr)


def create_fixture(output: Path) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("ffmpeg is required")
    output.mkdir(parents=True, exist_ok=False)
    shared = {
        "original": "0" * 64,
        "canonical": "1" * 64,
        "timeline": "2" * 64,
        "lyrics": "3" * 64,
        "renderer_host": "4" * 64,
    }
    requests = []
    for variant_index, (variant_id, (label, colors)) in enumerate(VARIANTS.items(), 1):
        directory = output / variant_id
        directory.mkdir()
        outputs = []
        for range_index, color in enumerate(colors, 1):
            clip = directory / f"0{range_index}-range-{range_index}.mp4"
            generate_clip(ffmpeg, clip, color, 440 if range_index == 1 else 660)
            outputs.append({"path": clip.name, "sha256": sha256(clip)})
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "cache_key": str(variant_index + 4) * 64,
            "status": "completed",
            "source_sha256": shared["original"],
            "canonical_audio_sha256": shared["canonical"],
            "inputs": {
                "timeline": shared["timeline"],
                "lyrics": shared["lyrics"],
                "renderer_host": shared["renderer_host"],
                "plan": f"{variant_index + 6:x}" * 64,
                "assets": f"{variant_index + 9:x}" * 64,
            },
            "seed": variant_index,
            "environment": {"renderer": "public-s11-synthetic"},
            "ranges": RANGES,
            "outputs": outputs,
        }
        manifest_path = directory / "preview.render.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        requests.append(
            {
                "id": variant_id,
                "label": label,
                "preview_manifest_path": str(manifest_path.relative_to(output)),
            }
        )
    request_path = output / "comparison-request.json"
    request_path.write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "variants": requests}, indent=2) + "\n",
        encoding="utf-8",
    )
    return request_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(create_fixture(args.output.resolve()))


if __name__ == "__main__":
    main()
