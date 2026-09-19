"""Offline projectM S13 feasibility probe; never registers a production backend."""

import argparse
import hashlib
import json
import math
import platform
import shutil
import struct
import subprocess
import wave
import zlib
from pathlib import Path

from music_video_toolkit.contracts import ProviderManifest, ProviderRequest
from music_video_toolkit.project import sha256_file
from music_video_toolkit.provider import probe_silent_video, validate_provider_result

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "integrations/projectm"
LOCK = json.loads((INTEGRATION / "lock.json").read_text(encoding="utf-8"))
PRESET = (
    "[preset00]\nfdecay=0.85\nwarp=0\nnWaveMode=6\nfWaveScale=1\n"
    "wave_r=0.2\nwave_g=0.8\nwave_b=1.0\nwave_x=0.5\nwave_y=0.5\n"
)


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(
            f"exit {result.returncode}: {' '.join(command)}\n{result.stdout}\n{result.stderr}"
        )
    return result


def png_bytes() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    scanline = b"\0" + bytes([40, 160, 240, 255] * 2)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(scanline * 2))
        + chunk(b"IEND", b"")
    )


def check_core(core: Path, build: Path) -> Path:
    if run(["git", "rev-parse", "HEAD"], cwd=core).stdout.strip() != LOCK["commit"]:
        raise ValueError("projectM core revision differs from lock")
    eval_commit = run(["git", "rev-parse", "HEAD"], cwd=core / "vendor/projectm-eval")
    if eval_commit.stdout.strip() != LOCK["eval_submodule_commit"]:
        raise ValueError("projectM-eval submodule differs from lock")
    if sha256_file(core / LOCK["license_file"]) != LOCK["license_sha256"]:
        raise ValueError("projectM license file differs from lock")
    source = INTEGRATION / "feasibility-provider.cpp"
    if sha256_file(source) != LOCK["provider_source_sha256"]:
        raise ValueError("projectM provider source differs from lock")
    library = build / "src/libprojectM/libprojectM-4.dylib"
    if not library.is_file():
        raise ValueError("build pinned projectM core before running the offline probe")
    return library


def make_inputs(directory: Path) -> tuple[Path, Path, Path, Path]:
    directory.mkdir()
    audio = directory / "canonical.wav"
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(3)
        wav.setframerate(48000)
        samples = bytearray()
        for index in range(48000):
            value = int(0.25 * (2**23 - 1) * math.sin(2 * math.pi * 440 * index / 48000))
            samples.extend(struct.pack("<i", value)[:3] * 2)
        wav.writeframes(samples)
    preset = directory / "mvt-feasibility.milk"
    preset.write_text(PRESET, encoding="utf-8")
    texture_dir = directory / "textures"
    texture_dir.mkdir()
    texture = texture_dir / "mvt-synthetic.png"
    texture.write_bytes(png_bytes())
    if (
        sha256_file(preset) != LOCK["preset_sha256"]
        or sha256_file(texture) != LOCK["texture_sha256"]
    ):
        raise ValueError("self-authored preset or texture differs from lock")
    project = directory / "project.json"
    project.write_text(
        json.dumps(
            {
                "preset": {"path": preset.name, "sha256": sha256_file(preset)},
                "texture": {
                    "path": str(texture.relative_to(directory)),
                    "sha256": sha256_file(texture),
                },
                "license": LOCK["preset_texture_license"],
            }
        ),
        encoding="utf-8",
    )
    return audio, preset, texture, project


def make_pcm(audio: Path, output: Path) -> None:
    with wave.open(str(audio), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (48000, 2, 3):
            raise ValueError("canonical PCM format mismatch")
        pcm = wav.readframes(9600)
    with output.open("wb") as stream:
        for index in range(0, len(pcm), 3):
            sample = int.from_bytes(pcm[index : index + 3], byteorder="little", signed=True)
            stream.write(struct.pack("<f", sample / 8388608.0))


def make_request(directory: Path, audio: Path, preset: Path, texture: Path, project: Path) -> Path:
    parameters = {"frames": 6, "frame_time": "explicit-30", "input_format": "pcm_s24le"}
    parameter_hash = hashlib.sha256(
        json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    request = ProviderRequest.model_validate(
        {
            "schema_version": "0.1",
            "source": {
                "path": audio.name,
                "sha256": sha256_file(audio),
                "sample_rate": 48000,
                "duration_samples": 48000,
            },
            "canonical_audio": {"path": audio.name, "sha256": sha256_file(audio)},
            "profile": {"width": 1920, "height": 1080, "fps_num": 30, "fps_den": 1},
            "range": {"start_sample": 0, "end_sample": 9600},
            "backend": {
                "name": "projectm",
                "version": LOCK["version"],
                "commit": LOCK["commit"],
                "integration_patch_sha256": LOCK["provider_source_sha256"],
            },
            "project": {"path": project.name, "sha256": sha256_file(project)},
            "assets": [
                {"path": preset.name, "sha256": sha256_file(preset)},
                {"path": str(texture.relative_to(directory)), "sha256": sha256_file(texture)},
            ],
            "parameters": parameters,
            "parameters_sha256": parameter_hash,
        }
    )
    path = directory / "request.json"
    path.write_text(request.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def encode_result(
    index: int, directory: Path, binary: Path, request_path: Path, ffmpeg: str, library: Path
) -> dict[str, object]:
    request = ProviderRequest.model_validate(json.loads(request_path.read_text(encoding="utf-8")))
    output = directory / f"result-{index}"
    output.mkdir()
    raw = output / "frames.rgba"
    pcm = directory / "input/canonical.f32le"
    preset = directory / "input/mvt-feasibility.milk"
    textures = directory / "input/textures"
    render = run([str(binary), str(pcm), str(preset), str(textures), str(raw)])
    (output / "timing.log").write_text(render.stderr, encoding="utf-8")
    video = output / "video.mp4"
    run(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "-s",
            "1920x1080",
            "-r",
            "30",
            "-i",
            str(raw),
            "-vf",
            "vflip",
            "-frames:v",
            "6",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(video),
        ]
    )
    probe = probe_silent_video(video)
    manifest = ProviderManifest(
        schema_version="0.1",
        status="completed",
        request={"path": "../input/request.json", "sha256": sha256_file(request_path)},
        source_sha256=request.source.sha256,
        profile=request.profile,
        range=request.range,
        backend=request.backend,
        project_sha256=request.project.sha256,
        plugin_sha256=[],
        asset_sha256=[ref.sha256 for ref in request.assets],
        parameters_sha256=request.parameters_sha256,
        environment={
            "platform": platform.platform(),
            "provider_sha256": sha256_file(binary),
            "core_dylib_sha256": sha256_file(library),
            "ffmpeg": run([ffmpeg, "-version"]).stdout.splitlines()[0],
        },
        video={"path": video.name, "sha256": sha256_file(video)},
        probe=probe,
    )
    manifest_path = output / "provider-manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    validate_provider_result(request_path, manifest_path)
    raw.unlink()
    return {
        "manifest": str(manifest_path),
        "video_sha256": sha256_file(video),
        "timing": render.stderr,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    core = args.core.resolve()
    build = args.build.resolve()
    output = args.output.resolve()
    if output.exists() or not output.parent.is_dir():
        parser.error("choose a new external output directory")
    library = check_core(core, build)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        parser.error("ffmpeg is required")
    output.mkdir()
    audio, preset, texture, project = make_inputs(output / "input")
    make_pcm(audio, output / "input/canonical.f32le")
    request_path = make_request(output / "input", audio, preset, texture, project)
    binary = output / "feasibility-provider"
    run(
        [
            "c++",
            "-std=c++17",
            "-O2",
            "-DGL_SILENCE_DEPRECATION",
            "-I",
            str(core / "src/api/include"),
            "-I",
            str(build / "src/api/include"),
            str(INTEGRATION / "feasibility-provider.cpp"),
            "-L",
            str(library.parent),
            "-lprojectM-4",
            f"-Wl,-rpath,{library.parent}",
            "-framework",
            "OpenGL",
            "-o",
            str(binary),
        ]
    )
    results = [encode_result(i, output, binary, request_path, ffmpeg, library) for i in (1, 2)]
    report = {
        "core_commit": LOCK["commit"],
        "eval_submodule_commit": LOCK["eval_submodule_commit"],
        "core_license": LOCK["license"],
        "preset_texture_license": LOCK["preset_texture_license"],
        "preset_sha256": LOCK["preset_sha256"],
        "texture_sha256": LOCK["texture_sha256"],
        "provider_source_sha256": LOCK["provider_source_sha256"],
        "source_sha256": sha256_file(audio),
        "range": {"start_sample": 0, "end_sample": 9600},
        "profile": {"width": 1920, "height": 1080, "fps_num": 30, "fps_den": 1},
        "results": results,
        "byte_identical": results[0]["video_sha256"] == results[1]["video_sha256"],
        "scope": "feasibility only; no global-time replay or production adapter",
    }
    (output / "feasibility-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
