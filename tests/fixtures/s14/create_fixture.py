"""Public synthetic projectM provider request; no third-party preset or song data."""

import hashlib
import json
import math
import shutil
import struct
import wave
from pathlib import Path

from music_video_toolkit.contracts import ProviderRequest
from music_video_toolkit.project import sha256_file
from music_video_toolkit.projectm_provider import INTEGRATION, LOCK, integration_identity


def write_fixture(
    directory: Path,
    *,
    start_frame: int = 0,
    end_frame: int = 6,
    portrait: bool = False,
    preset_id: str = "mvt-wave",
) -> Path:
    directory.mkdir(parents=True)
    canonical = directory / "canonical.wav"
    with wave.open(str(canonical), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(3)
        stream.setframerate(48000)
        samples = bytearray()
        for sample in range(48000):
            value = int(0.25 * (2**23 - 1) * math.sin(2 * math.pi * 440 * sample / 48000))
            samples.extend(struct.pack("<i", value)[:3] * 2)
        stream.writeframes(samples)
    if preset_id not in LOCK["approved_presets"]:
        raise ValueError(f"unknown fixture preset: {preset_id}")
    preset = directory / f"{preset_id}.milk"
    shutil.copyfile(INTEGRATION / "presets" / preset.name, preset)
    project = directory / "project.json"
    project.write_text(
        json.dumps({"preset": {"path": preset.name, "sha256": sha256_file(preset)}}) + "\n",
        encoding="utf-8",
    )
    parameters = {"preset_id": preset_id, "policy": "locked-single"}
    parameter_hash = hashlib.sha256(
        json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    profile = (
        {"width": 1080, "height": 1920, "fps_num": 30, "fps_den": 1}
        if portrait
        else {"width": 1920, "height": 1080, "fps_num": 30, "fps_den": 1}
    )
    request = ProviderRequest.model_validate(
        {
            "schema_version": "0.1",
            "source": {
                "path": canonical.name,
                "sha256": sha256_file(canonical),
                "sample_rate": 48000,
                "duration_samples": 48000,
            },
            "canonical_audio": {"path": canonical.name, "sha256": sha256_file(canonical)},
            "profile": profile,
            "range": {"start_sample": start_frame * 1600, "end_sample": end_frame * 1600},
            "backend": {
                "name": "projectm",
                "version": LOCK["version"],
                "commit": LOCK["commit"],
                "integration_patch_sha256": integration_identity(),
            },
            "project": {"path": project.name, "sha256": sha256_file(project)},
            "assets": [{"path": preset.name, "sha256": sha256_file(preset)}],
            "parameters": parameters,
            "parameters_sha256": parameter_hash,
        }
    )
    request_path = directory / "request.json"
    request_path.write_text(request.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return request_path
