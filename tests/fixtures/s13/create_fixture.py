"""Create a public synthetic Astrofox provider job outside the repository."""

import argparse
import hashlib
import json
import math
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOCK = json.loads((ROOT / "integrations/astrofox/lock.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_fixture(destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    audio_path = destination / "canonical.wav"
    with wave.open(str(audio_path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(3)
        wav.setframerate(48000)
        frames = bytearray()
        for sample in range(48000):
            value = int(0.25 * (2**23 - 1) * math.sin(2 * math.pi * 440 * sample / 48000))
            frame = struct.pack("<i", value)[:3]
            frames.extend(frame * 2)
        wav.writeframes(frames)
    project = {
        "name": "S13 public synthetic bars",
        "version": "2.0.0",
        "snapshot": {
            "version": "2.0.0",
            "stage": {
                "properties": {
                    "width": 1920,
                    "height": 1080,
                    "backgroundColor": "#101020",
                    "zoom": 1,
                }
            },
            "scenes": [
                {
                    "id": "synthetic-scene",
                    "name": "Scene",
                    "type": "display",
                    "enabled": True,
                    "properties": {"blendMode": "Normal", "opacity": 1},
                    "displays": [
                        {
                            "id": "synthetic-bars",
                            "name": "BarSpectrumDisplay",
                            "type": "display",
                            "enabled": True,
                            "properties": {
                                "width": 1320,
                                "height": 500,
                                "x": 0,
                                "y": 0,
                                "color": ["#55ccff", "#ff77aa"],
                                "shadowColor": ["#173348", "#31182e"],
                            },
                            "reactors": {},
                        }
                    ],
                    "effects": [],
                }
            ],
            "reactors": [],
        },
    }
    project_path = destination / "project.json"
    project_path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    parameters: dict[str, object] = {}
    parameter_hash = hashlib.sha256(
        json.dumps(parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    request = {
        "schema_version": "0.1",
        "source": {
            "path": audio_path.name,
            "sha256": sha256(audio_path),
            "sample_rate": 48000,
            "duration_samples": 48000,
        },
        "canonical_audio": {"path": audio_path.name, "sha256": sha256(audio_path)},
        "profile": {"width": 1920, "height": 1080, "fps_num": 30, "fps_den": 1},
        "range": {"start_sample": 0, "end_sample": 48000},
        "backend": {
            "name": "astrofox",
            "version": "2.0.0",
            "commit": LOCK["commit"],
            "integration_patch_sha256": LOCK["patch_stack_sha256"],
        },
        "project": {"path": project_path.name, "sha256": sha256(project_path)},
        "plugins": [],
        "assets": [],
        "parameters": parameters,
        "parameters_sha256": parameter_hash,
    }
    request_path = destination / "request.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    return request_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(write_fixture(args.destination.resolve()))
