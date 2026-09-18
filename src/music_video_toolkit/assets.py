"""Strict local asset preflight and typed media metadata."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from pydantic import ValidationError

from .contracts import AssetManifest, AssetProbe, CheckedAssetManifest, FileRef
from .documents import read_document
from .project import resolve_record_path, sha256_file

DEFAULT_MANIFEST = Path("assets.json")


class AssetError(Exception):
    """A stable asset preflight failure for the CLI and plan resolver."""

    def __init__(self, code: str, details: object, exit_code: int = 2):
        super().__init__(str(details))
        self.code = code
        self.details = details
        self.exit_code = exit_code


def _load(path: Path) -> AssetManifest:
    try:
        return AssetManifest.model_validate(read_document(path))
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        details = (
            exc.errors(include_url=False, include_context=False, include_input=False)
            if isinstance(exc, ValidationError)
            else str(exc)
        )
        raise AssetError("invalid_asset_manifest", details) from exc


def _run(command: list[str], code: str) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise AssetError(code, {"message": str(exc)}, 3) from exc
    if result.returncode != 0:
        raise AssetError(
            code,
            {"returncode": result.returncode, "stderr": result.stderr.strip()},
            4,
        )
    return result


def _ffprobe() -> str:
    tool = shutil.which("ffprobe")
    if tool is None:
        raise AssetError("missing_dependency", {"tool": "ffprobe"}, 3)
    return tool


def _probe_media(path: Path, asset_id: str, asset_type: str, digest: str) -> AssetProbe:
    result = _run(
        [
            _ffprobe(),
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            (
                "stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,"
                "nb_read_frames,duration:format=duration"
            ),
            "-of",
            "json",
            str(path),
        ],
        "asset_probe_failed",
    )
    try:
        document = json.loads(result.stdout)
        streams = document["streams"]
        video = next(item for item in streams if item["codec_type"] == "video")
        width = int(video["width"])
        height = int(video["height"])
    except (json.JSONDecodeError, KeyError, StopIteration, TypeError, ValueError) as exc:
        raise AssetError("asset_type_mismatch", {"id": asset_id, "expected": asset_type}) from exc
    common = {"id": asset_id, "path": str(path), "sha256": digest, "width": width, "height": height}
    if asset_type == "image":
        if (
            video.get("codec_name") not in {"mjpeg", "png", "webp"}
            or video.get("nb_read_frames") != "1"
        ):
            raise AssetError("asset_type_mismatch", {"id": asset_id, "expected": "image"})
        return AssetProbe(type="image", **common)
    try:
        frame_count = int(video["nb_read_frames"])
        rate = Fraction(video["r_frame_rate"])
        average_rate = Fraction(video["avg_frame_rate"])
        duration = float(video.get("duration") or document["format"]["duration"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise AssetError(
            "asset_probe_failed", {"id": asset_id, "message": "incomplete video clock"}
        ) from exc
    if frame_count <= 0 or rate <= 0 or duration <= 0:
        raise AssetError("asset_probe_failed", {"id": asset_id, "message": "invalid video clock"})
    if average_rate != rate:
        raise AssetError(
            "variable_frame_rate_forbidden",
            {"id": asset_id, "r_frame_rate": str(rate), "avg_frame_rate": str(average_rate)},
        )
    return AssetProbe(
        type="video",
        frame_count=frame_count,
        fps_num=rate.numerator,
        fps_den=rate.denominator,
        duration_seconds=duration,
        has_audio=any(item.get("codec_type") == "audio" for item in streams),
        **common,
    )


def _probe_font(path: Path, asset_id: str, digest: str) -> AssetProbe:
    if platform.system() != "Darwin":
        raise AssetError(
            "font_probe_unavailable",
            {"id": asset_id, "message": "S05 font preflight currently requires macOS mdls"},
            3,
        )
    mdls = shutil.which("mdls")
    if mdls is None:
        raise AssetError("missing_dependency", {"tool": "mdls"}, 3)
    result = subprocess.run(
        [mdls, "-raw", "-name", "kMDItemFonts", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout.strip()
    families = (
        [
            line.strip().strip('",')
            for line in output.strip("()\n ").splitlines()
            if line.strip().strip('",')
        ]
        if result.returncode == 0 and output not in {"", "(null)"}
        else []
    )
    if not families:
        mdimport = shutil.which("mdimport")
        plutil = shutil.which("plutil")
        if mdimport is None or plutil is None:
            raise AssetError("missing_dependency", {"tool": "mdimport/plutil"}, 3)
        descriptor, metadata_name = tempfile.mkstemp(prefix="mvt-font-metadata-", suffix=".plist")
        os.close(descriptor)
        metadata = Path(metadata_name)
        try:
            imported = subprocess.run(
                [mdimport, "-t", "-o", str(metadata), str(path)],
                text=True,
                capture_output=True,
                check=False,
            )
            extracted = subprocess.run(
                [plutil, "-extract", "kMDItemFonts", "json", "-o", "-", str(metadata)],
                text=True,
                capture_output=True,
                check=False,
            )
            if imported.returncode == 0 and extracted.returncode == 0:
                decoded = json.loads(extracted.stdout)
                if isinstance(decoded, list):
                    families = [str(item) for item in decoded if str(item).strip()]
        except (OSError, json.JSONDecodeError):
            families = []
        finally:
            metadata.unlink(missing_ok=True)
    if not families:
        raise AssetError("font_probe_failed", {"id": asset_id, "path": str(path)})
    return AssetProbe(
        id=asset_id,
        path=str(path),
        sha256=digest,
        type="font",
        font_families=families,
    )


def _write(path: Path, checked: CheckedAssetManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(checked.model_dump_json(indent=2))
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def check_assets(
    project: Path,
    manifest_path: Path | None = None,
    output_path: Path | None = None,
) -> tuple[CheckedAssetManifest, Path, bool]:
    project = project.resolve()
    manifest_path = (manifest_path or project / DEFAULT_MANIFEST).resolve()
    manifest = _load(manifest_path)
    output_path = (
        output_path or manifest_path.with_name(f"{manifest_path.stem}.checked.json")
    ).resolve()
    source_hash = sha256_file(manifest_path)
    probes: list[AssetProbe] = []
    identities = []
    for asset in manifest.assets:
        if "://" in asset.path:
            raise AssetError("remote_asset_forbidden", {"id": asset.id, "path": asset.path})
        path = resolve_record_path(manifest_path, asset.path)
        if not path.is_file():
            raise AssetError("missing_asset", {"id": asset.id, "path": str(path)}, 4)
        actual_hash = sha256_file(path)
        if actual_hash != asset.sha256:
            raise AssetError(
                "asset_hash_mismatch",
                {"id": asset.id, "expected": asset.sha256, "actual": actual_hash},
                4,
            )
        probe = (
            _probe_font(path, asset.id, actual_hash)
            if asset.type == "font"
            else _probe_media(path, asset.id, asset.type, actual_hash)
        )
        probe = probe.model_copy(update={"path": os.path.relpath(path, output_path.parent)})
        probes.append(probe)
        identities.append({"id": asset.id, "type": asset.type, "sha256": actual_hash})
    cache_key = hashlib.sha256(
        json.dumps(
            {"manifest": source_hash, "assets": identities}, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    checked = CheckedAssetManifest(
        schema_version="0.1",
        source_manifest=FileRef(
            path=os.path.relpath(manifest_path, output_path.parent), sha256=source_hash
        ),
        cache_key=cache_key,
        assets=probes,
    )
    cached = False
    try:
        existing = CheckedAssetManifest.model_validate(read_document(output_path))
        cached = existing == checked
    except (OSError, UnicodeError, ValueError, ValidationError):
        pass
    if not cached:
        _write(output_path, checked)
    return checked, output_path, cached
