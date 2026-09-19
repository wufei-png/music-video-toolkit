"""Create a public synthetic Astrofox provider job outside the repository."""

import argparse
import base64
import hashlib
import json
import math
import struct
import wave
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOCK = json.loads((ROOT / "integrations/astrofox/lock.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_fixture(
    destination: Path, *, with_plugin: bool = False, with_asset: bool = False
) -> Path:
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
    plugin_refs = []
    asset_refs = []
    displays = project["snapshot"]["scenes"][0]["displays"]
    if with_plugin:
        shader = (
            "varying vec2 vUv; uniform float time; uniform float volume; "
            "void main() { gl_FragColor=vec4(vUv.x, volume, 0.5+0.5*sin(time), 1.0); }"
        )
        shader_integrity = (
            "sha384-" + base64.b64encode(hashlib.sha384(shader.encode()).digest()).decode()
        )
        plugin_path = destination / "synthetic-plugin.json"
        plugin = {
            "manifest": {
                "api": 1,
                "name": "@synthetic/gradient",
                "version": "1.0.0",
                "label": "Synthetic gradient",
                "type": "display",
                "runtime": "shader",
                "shader": "display.frag",
                "permissions": [],
                "libraries": [],
                "defaultProperties": {"width": 1920, "height": 1080},
                "controls": {},
            },
            "sourceUrl": plugin_path.as_uri(),
            "installedAt": "2026-01-01T00:00:00Z",
            "files": {"display.frag": shader},
            "integrity": {"display.frag": shader_integrity},
            "dev": False,
        }
        plugin_path.write_text(json.dumps(plugin), encoding="utf-8")
        plugin_refs.append({"path": plugin_path.name, "sha256": sha256(plugin_path)})
        displays.append(
            {
                "id": "synthetic-gradient",
                "name": "@synthetic/gradient",
                "type": "display",
                "enabled": True,
                "properties": {"width": 1920, "height": 1080},
                "reactors": {},
            }
        )
    if with_asset:
        asset_path = destination / "synthetic.png"

        def chunk(kind: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + kind
                + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
            )

        scanline = b"\0" + bytes([40, 160, 240, 255] * 2)
        png = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(scanline * 2))
            + chunk(b"IEND", b"")
        )
        asset_path.write_bytes(png)
        asset_refs.append({"path": asset_path.name, "sha256": sha256(asset_path)})
        displays.append(
            {
                "id": "synthetic-image",
                "name": "ImageDisplay",
                "type": "display",
                "enabled": True,
                "properties": {
                    "src": asset_path.name,
                    "sourcePath": asset_path.name,
                    "width": 240,
                    "height": 240,
                    "x": 600,
                    "y": 250,
                },
                "reactors": {},
            }
        )
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
        "plugins": plugin_refs,
        "assets": asset_refs,
        "parameters": parameters,
        "parameters_sha256": parameter_hash,
    }
    request_path = destination / "request.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    return request_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    parser.add_argument("--with-plugin", action="store_true")
    parser.add_argument("--with-asset", action="store_true")
    args = parser.parse_args()
    print(
        write_fixture(
            args.destination.resolve(), with_plugin=args.with_plugin, with_asset=args.with_asset
        )
    )
