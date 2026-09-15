"""Isolated four-stem separation and renderer-neutral timeline analysis."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from . import __version__
from .contracts import (
    AnalysisRun,
    FileRef,
    Provenance,
    SeparationModel,
    Source,
    StemAlignment,
    StemAudio,
    StemManifest,
    Timeline,
)
from .documents import read_document
from .project import ProjectPreflightError, preflight_source, resolve_record_path, sha256_file

TIMELINE_PATH = Path("timeline.json")
RUN_PATH = Path("analysis/run.json")
STEM_MANIFEST_PATH = Path("stems/stems.json")
STEM_NAMES = ("vocals", "drums", "bass", "other")
MODEL_NAME = "htdemucs.yaml"
MODEL_LABEL = "htdemucs"
MODEL_CONFIG = "htdemucs.yaml"
MODEL_WEIGHTS = "955717e8-8726e21a.th"
MODEL_SOURCE = "https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/955717e8-8726e21a.th"
SEPARATOR_VERSION = "0.44.2"
ANALYZER_CONFIG = {
    "hop_samples": 1024,
    "rms_frame_samples": 2048,
    "chroma_fft_samples": 4096,
    "center": False,
    "end_padding": "zero_pad_each_analysis_window; emit ceil(duration_samples/hop_samples) values",
    "normalization": "each signal divided by its observed absolute maximum",
    "silence_policy": "max <= 1e-12 emits all zeros",
    "low_frequency_max_hz": 200.0,
    "beat_semantics": "beat estimate; not downbeat or bar phase",
}


class AnalysisError(Exception):
    """A stable analysis failure suitable for machine-readable CLI output."""

    def __init__(self, code: str, details: object, exit_code: int = 2):
        super().__init__(str(details))
        self.code = code
        self.details = details
        self.exit_code = exit_code


@dataclass(frozen=True)
class AnalysisResult:
    run: AnalysisRun
    run_path: Path
    timeline_path: Path
    stem_manifest_path: Path | None
    cached: bool

    def report(self) -> dict[str, object]:
        return {
            "ok": True,
            "cached": self.cached,
            "mode": self.run.mode,
            "cache_key": self.run.cache_key,
            "timeline": str(self.timeline_path),
            "stems": str(self.stem_manifest_path) if self.stem_manifest_path else None,
            "run": str(self.run_path),
            "timings_seconds": self.run.timings_seconds,
        }


def _json_hash(value: object) -> str:
    import hashlib

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _runtime_project() -> Path:
    configured = os.environ.get("MVT_SEPARATION_PROJECT")
    path = (
        Path(configured).expanduser()
        if configured
        else Path(__file__).resolve().parents[2] / "environments/separation"
    )
    if not (path / "pyproject.toml").is_file() or not (path / "uv.lock").is_file():
        raise AnalysisError(
            "missing_analysis_runtime",
            {
                "path": str(path),
                "message": "Set MVT_SEPARATION_PROJECT to the locked separation environment",
            },
            3,
        )
    return path.resolve()


def _dependency(name: str) -> str:
    value = shutil.which(name)
    if value is None:
        raise AnalysisError(
            "missing_dependency", {"tool": name, "message": f"Install {name} and put it on PATH"}, 3
        )
    return value


def _run(command: list[str], code: str) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise AnalysisError(code, {"message": str(exc)}, 3) from exc
    if result.returncode != 0:
        raise AnalysisError(
            code,
            {
                "returncode": result.returncode,
                "stdout_tail": result.stdout[-4000:],
                "stderr_tail": result.stderr[-4000:],
            },
            5,
        )
    return result


def _write_json(path: Path, model: AnalysisRun | StemManifest | Timeline) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(model.model_dump_json(indent=2))
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _model_paths(model_dir: Path) -> tuple[Path, Path]:
    return model_dir / MODEL_CONFIG, model_dir / MODEL_WEIGHTS


def _model_record(model_dir: Path) -> SeparationModel:
    config, weights = _model_paths(model_dir)
    missing = [str(path) for path in (config, weights) if not path.is_file()]
    if missing:
        raise AnalysisError(
            "model_output_missing",
            {
                "model": MODEL_NAME,
                "missing": missing,
                "message": "Separator did not install its model files",
            },
            5,
        )
    return SeparationModel(
        name=MODEL_NAME,
        config_sha256=sha256_file(config),
        weights_sha256=sha256_file(weights),
        source=MODEL_SOURCE,
        license_status="unconfirmed",
        redistributable=False,
    )


def _cache_key(source_hash: str, mode: str, model: SeparationModel | None) -> str:
    return _json_hash(
        {
            "source_sha256": source_hash,
            "mode": mode,
            "analysis": ANALYZER_CONFIG,
            "separator": SEPARATOR_VERSION if model else None,
            "model": model.model_dump(mode="json") if model else None,
        }
    )


def _read_cached(
    project: Path, source_hash: str, mode: str, cache_key: str
) -> AnalysisResult | None:
    run_path = project / RUN_PATH
    timeline_path = project / TIMELINE_PATH
    try:
        run = AnalysisRun.model_validate(read_document(run_path))
    except (OSError, UnicodeError, ValueError, ValidationError):
        return None
    if run.source_sha256 != source_hash or run.mode != mode or run.cache_key != cache_key:
        return None
    expected_outputs = {"timeline": (project / TIMELINE_PATH).resolve()}
    if mode == "four":
        expected_outputs["stems"] = (project / STEM_MANIFEST_PATH).resolve()
    try:
        for name, reference in run.outputs.items():
            path = resolve_record_path(run_path, reference.path)
            if path != expected_outputs[name] or not path.is_file():
                return None
            if sha256_file(path) != reference.sha256:
                return None
    except OSError:
        return None
    try:
        timeline = Timeline.model_validate(read_document(timeline_path))
    except (OSError, UnicodeError, ValueError, ValidationError):
        return None
    if timeline.source.sha256 != source_hash:
        return None
    if (
        resolve_record_path(timeline_path, timeline.source.path)
        != (project / "source/canonical.wav").resolve()
    ):
        return None
    stem_manifest_path = project / STEM_MANIFEST_PATH if mode == "four" else None
    if stem_manifest_path:
        try:
            manifest = StemManifest.model_validate(read_document(stem_manifest_path))
        except (OSError, UnicodeError, ValueError, ValidationError):
            return None
        if manifest.cache_key != cache_key:
            return None
        if (
            resolve_record_path(stem_manifest_path, manifest.source.path)
            != (project / "source/canonical.wav").resolve()
        ):
            return None
        try:
            for name, stem in manifest.stems.items():
                path = resolve_record_path(stem_manifest_path, stem.path)
                if path != (project / "stems" / f"{name}.wav").resolve() or not path.is_file():
                    return None
                if sha256_file(path) != stem.sha256:
                    return None
        except OSError:
            return None
    return AnalysisResult(run, run_path, timeline_path, stem_manifest_path, True)


def _wave_info(path: Path) -> tuple[int, int, int, int]:
    try:
        with wave.open(str(path), "rb") as wav:
            return wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()
    except (OSError, EOFError, wave.Error) as exc:
        raise AnalysisError(
            "invalid_stem_output", {"path": str(path), "message": str(exc)}, 5
        ) from exc


def _normalize_stem(ffmpeg: str, source: Path, output: Path, target_samples: int) -> StemAlignment:
    input_rate, channels, _, input_samples = _wave_info(source)
    if channels != 2:
        raise AnalysisError("invalid_stem_output", {"path": str(source), "channels": channels}, 5)
    natural = output.with_name(f".{output.name}.resampled.wav")
    _run(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-map_metadata",
            "-1",
            "-af",
            "aresample=48000",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s24le",
            str(natural),
        ],
        "stem_normalization_failed",
    )
    natural_rate, natural_channels, natural_width, natural_samples = _wave_info(natural)
    if (natural_rate, natural_channels, natural_width) != (48000, 2, 3):
        raise AnalysisError("invalid_stem_output", {"path": str(natural)}, 5)
    delta = target_samples - natural_samples
    adjustment = "none" if delta == 0 else "pad" if delta > 0 else "trim"
    if delta == 0:
        os.replace(natural, output)
    else:
        _run(
            [
                ffmpeg,
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-i",
                str(natural),
                "-map_metadata",
                "-1",
                "-af",
                f"apad=whole_len={target_samples},atrim=end_sample={target_samples}",
                "-c:a",
                "pcm_s24le",
                str(output),
            ],
            "stem_alignment_failed",
        )
        natural.unlink(missing_ok=True)
    observed = _wave_info(output)
    if observed != (48000, 2, 3, target_samples):
        raise AnalysisError(
            "stem_alignment_failed",
            {"path": str(output), "expected": [48000, 2, 3, target_samples], "actual": observed},
            5,
        )
    return StemAlignment(
        input_sample_rate=input_rate,
        input_duration_samples=input_samples,
        natural_output_samples=natural_samples,
        target_duration_samples=target_samples,
        adjustment=adjustment,
        adjustment_samples=delta,
    )


def _separate(
    runtime: Path,
    uv: str,
    ffmpeg: str,
    canonical: Path,
    temporary: Path,
    model_dir: Path,
    duration_samples: int,
) -> tuple[dict[str, Path], dict[str, StemAlignment], SeparationModel]:
    raw_dir = temporary / "raw"
    normalized_dir = temporary / "normalized"
    raw_dir.mkdir()
    normalized_dir.mkdir()
    _run(
        [
            uv,
            "run",
            "--project",
            str(runtime),
            "--locked",
            "audio-separator",
            str(canonical),
            "--model_filename",
            MODEL_NAME,
            "--model_file_dir",
            str(model_dir),
            "--output_dir",
            str(raw_dir),
            "--output_format",
            "WAV",
            "--log_level",
            "info",
        ],
        "separation_failed",
    )
    model = _model_record(model_dir)
    raw_files = list(raw_dir.glob("*.wav"))
    selected: dict[str, Path] = {}
    for name in STEM_NAMES:
        matches = [path for path in raw_files if f"({name.title()})_{MODEL_LABEL}" in path.name]
        if len(matches) != 1:
            raise AnalysisError(
                "separation_output_missing",
                {
                    "stem": name,
                    "matches": [str(path) for path in matches],
                    "all": [str(path) for path in raw_files],
                },
                5,
            )
        selected[name] = matches[0]
    normalized: dict[str, Path] = {}
    alignments: dict[str, StemAlignment] = {}
    for name, source in selected.items():
        output = normalized_dir / f"{name}.wav"
        alignments[name] = _normalize_stem(ffmpeg, source, output, duration_samples)
        normalized[name] = output
    return normalized, alignments, model


def _analyze_files(
    runtime: Path,
    uv: str,
    canonical: Path,
    stems: dict[str, Path],
    output: Path,
    source_sha256: str,
    duration_samples: int,
) -> Timeline:
    script = runtime / "analyze_audio.py"
    if not script.is_file():
        raise AnalysisError("missing_analysis_runtime", {"path": str(script)}, 3)
    command = [
        uv,
        "run",
        "--project",
        str(runtime),
        "--locked",
        "python",
        str(script),
        "--source",
        str(canonical),
        "--source-path",
        "source/canonical.wav",
        "--source-sha256",
        source_sha256,
        "--duration-samples",
        str(duration_samples),
        "--output",
        str(output),
    ]
    for name in STEM_NAMES:
        if name in stems:
            command.extend(["--stem", f"{name}={stems[name]}"])
    _run(command, "feature_analysis_failed")
    try:
        timeline = Timeline.model_validate(read_document(output))
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        details = exc.errors(include_url=False) if isinstance(exc, ValidationError) else str(exc)
        raise AnalysisError("invalid_timeline_output", details, 5) from exc
    if len(timeline.analysis) != 1 or timeline.analysis[0].parameters != ANALYZER_CONFIG:
        raise AnalysisError(
            "analysis_configuration_mismatch",
            {
                "expected": ANALYZER_CONFIG,
                "actual": [item.model_dump() for item in timeline.analysis],
            },
            5,
        )
    return timeline


def analyze_project(project: Path, mode: str) -> AnalysisResult:
    if mode not in {"four", "none"}:
        raise AnalysisError("invalid_stem_mode", {"mode": mode})
    try:
        source = preflight_source(project)
    except ProjectPreflightError as exc:
        raise AnalysisError(exc.code, exc.details, 4) from exc
    runtime = _runtime_project()
    uv = _dependency("uv")
    ffmpeg = _dependency("ffmpeg")
    project = source.project
    model_dir = (
        Path(
            os.environ.get(
                "MVT_MODEL_DIR",
                str(Path.home() / "Library/Caches/music-video-toolkit/audio-separator"),
            )
        )
        .expanduser()
        .resolve()
    )
    model: SeparationModel | None = None
    config_path, weights_path = _model_paths(model_dir)
    if mode == "four" and config_path.is_file() and weights_path.is_file():
        model = _model_record(model_dir)
    preliminary_key = _cache_key(source.record.canonical.sha256, mode, model)
    if mode == "none" or model is not None:
        cached = _read_cached(project, source.record.canonical.sha256, mode, preliminary_key)
        if cached is not None:
            return cached

    model_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    separation_seconds = 0.0
    with tempfile.TemporaryDirectory(dir=project, prefix=".analysis-") as temporary_name:
        temporary = Path(temporary_name)
        stems: dict[str, Path] = {}
        alignments: dict[str, StemAlignment] = {}
        if mode == "four":
            separation_started = time.perf_counter()
            stems, alignments, model = _separate(
                runtime,
                uv,
                ffmpeg,
                source.canonical_path,
                temporary,
                model_dir,
                source.record.canonical.duration_samples,
            )
            separation_seconds = time.perf_counter() - separation_started
        cache_key = _cache_key(source.record.canonical.sha256, mode, model)
        feature_started = time.perf_counter()
        timeline_temporary = temporary / "timeline.json"
        timeline = _analyze_files(
            runtime,
            uv,
            source.canonical_path,
            stems,
            timeline_temporary,
            source.record.canonical.sha256,
            source.record.canonical.duration_samples,
        )
        timeline.analysis.insert(
            0,
            Provenance(
                tool="music-video-toolkit",
                version=__version__,
                parameters={"cache_key": cache_key, "stems": mode},
            ),
        )
        if model is not None:
            timeline.analysis.insert(
                1,
                Provenance(
                    tool="audio-separator",
                    version=SEPARATOR_VERSION,
                    parameters={"model": MODEL_NAME, "weights_sha256": model.weights_sha256},
                ),
            )
        timeline = Timeline.model_validate(timeline.model_dump())
        feature_seconds = time.perf_counter() - feature_started

        stem_manifest: StemManifest | None = None
        if mode == "four":
            assert model is not None
            stem_manifest = StemManifest(
                schema_version="0.1",
                source=Source(
                    path="../source/canonical.wav",
                    sha256=source.record.canonical.sha256,
                    sample_rate=48000,
                    duration_samples=source.record.canonical.duration_samples,
                ),
                cache_key=cache_key,
                separator=Provenance(
                    tool="audio-separator",
                    version=SEPARATOR_VERSION,
                    parameters={"model": MODEL_NAME, "device_selection": "automatic"},
                ),
                model=model,
                stems={
                    name: StemAudio(
                        path=f"{name}.wav",
                        sha256=sha256_file(stems[name]),
                        sample_rate=48000,
                        channels=2,
                        sample_format="s24le",
                        codec="pcm_s24le",
                        duration_samples=source.record.canonical.duration_samples,
                        alignment=alignments[name],
                    )
                    for name in STEM_NAMES
                },
            )
            stem_directory = project / "stems"
            stem_directory.mkdir(exist_ok=True)
            for name in STEM_NAMES:
                os.replace(stems[name], stem_directory / f"{name}.wav")
            _write_json(project / STEM_MANIFEST_PATH, stem_manifest)

        _write_json(project / TIMELINE_PATH, timeline)
        run_path = project / RUN_PATH
        outputs = {
            "timeline": FileRef(
                path="../timeline.json", sha256=sha256_file(project / TIMELINE_PATH)
            )
        }
        if stem_manifest is not None:
            outputs["stems"] = FileRef(
                path="../stems/stems.json", sha256=sha256_file(project / STEM_MANIFEST_PATH)
            )
        run = AnalysisRun(
            schema_version="0.1",
            source_sha256=source.record.canonical.sha256,
            mode=mode,
            cache_key=cache_key,
            environment={
                "host": f"{platform.system()} {platform.machine()}",
                "runtime_lock_sha256": sha256_file(runtime / "uv.lock"),
                "analyzer": "librosa 0.10.2.post1",
                "separator": (
                    f"audio-separator {SEPARATOR_VERSION}" if mode == "four" else "disabled"
                ),
            },
            timings_seconds={
                "separation": separation_seconds,
                "features": feature_seconds,
                "total": time.perf_counter() - started,
            },
            outputs=outputs,
        )
        _write_json(run_path, run)
    return AnalysisResult(
        run=run,
        run_path=project / RUN_PATH,
        timeline_path=project / TIMELINE_PATH,
        stem_manifest_path=project / STEM_MANIFEST_PATH if mode == "four" else None,
        cached=False,
    )
