"""Bundle independently checked provider previews for S11 comparison."""

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from pydantic import ValidationError

from .contracts import FileRef, PreviewRequest, RenderManifest, SampleRange
from .documents import read_document
from .project import resolve_record_path, sha256_file
from .provider import ProviderError, validate_provider_result


class BundleError(Exception):
    def __init__(self, code: str, details: object):
        super().__init__(str(details))
        self.code = code
        self.details = details


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _bound_file(record: Path, reference: dict[str, str]) -> Path:
    path = resolve_record_path(record, reference["path"])
    if not path.is_file() or sha256_file(path) != reference["sha256"]:
        raise BundleError("provider_bundle_binding_mismatch", {"path": str(path)})
    return path


def bundle_provider_previews(compositions: list[Path], output: Path) -> dict[str, object]:
    output = output.resolve()
    if output.exists() or not output.parent.is_dir():
        raise BundleError("invalid_provider_bundle_output", str(output))
    if not compositions:
        raise BundleError("empty_provider_bundle", "at least one composition is required")
    prepared = []
    for index, value in enumerate(compositions, 1):
        binding_path = value.resolve()
        try:
            binding = read_document(binding_path)
            request_path = _bound_file(binding_path, binding["request"])
            manifest_path = _bound_file(binding_path, binding["provider_manifest"])
            provider = validate_provider_result(request_path, manifest_path)
            assert provider.video is not None
            preview_path = binding_path.parent / "preview/preview.render.json"
            if sha256_file(preview_path) != binding["preview_manifest_sha256"]:
                raise BundleError("provider_bundle_binding_mismatch", str(preview_path))
            preview = RenderManifest.model_validate(read_document(preview_path))
            plan_path = binding_path.parent / "resolved-plan.json"
            if sha256_file(plan_path) != binding["resolved_plan_sha256"]:
                raise BundleError("provider_bundle_binding_mismatch", str(plan_path))
            if (
                preview.status != "completed"
                or preview.ranges != [provider.range]
                or preview.profile != provider.profile
                or len(preview.outputs) != 1
                or preview.canonical_audio_sha256 != binding["canonical_audio_sha256"]
                or preview.inputs.get("asset.provider-video") != binding["provider_video_sha256"]
                or preview.inputs.get("preview_request")
                != sha256_file(binding_path.parent / "ranges.json")
                or "preview_adapter" not in preview.inputs
                or binding["provider_video_sha256"] != provider.video.sha256
                or binding["canonical_audio_sha256"] != provider.source_sha256
                or binding["profile"] != provider.profile.model_dump(mode="json")
                or binding["range"] != provider.range.model_dump(mode="json")
                or (
                    binding.get("lyrics_sha256") is not None
                    and preview.inputs.get("lyrics") != binding["lyrics_sha256"]
                )
            ):
                raise BundleError("provider_bundle_preview_mismatch", str(preview_path))
            clip = resolve_record_path(preview_path, preview.outputs[0].path)
            if (
                not clip.is_relative_to(preview_path.parent)
                or sha256_file(clip) != preview.outputs[0].sha256
            ):
                raise BundleError("provider_bundle_clip_mismatch", str(clip))
            prepared.append(
                (index, binding_path, manifest_path, preview_path, preview, provider, clip)
            )
        except (OSError, KeyError, TypeError, ValueError, ValidationError, ProviderError) as exc:
            raise BundleError(
                "invalid_provider_bundle_input",
                {"path": str(binding_path), "details": str(exc)},
            ) from exc
    baseline = prepared[0][4]
    previous_end = -1
    for _, _, _, _, preview, provider, _ in prepared:
        if (
            preview.source_sha256 != baseline.source_sha256
            or preview.canonical_audio_sha256 != baseline.canonical_audio_sha256
            or preview.profile != baseline.profile
            or provider.range.start_sample < previous_end
        ):
            raise BundleError("provider_bundle_identity_mismatch", "source/profile/ranges differ")
        previous_end = provider.range.end_sample
    job = Path(tempfile.mkdtemp(dir=output.parent, prefix=f".{output.name}.tmp-"))
    try:
        ranges = PreviewRequest.model_validate(
            {
                "schema_version": "0.1",
                "ranges": [
                    {
                        "id": f"provider-{index:02d}",
                        "start_sample": provider.range.start_sample,
                        "end_sample": provider.range.end_sample,
                        "role": "other",
                    }
                    for index, _, _, _, _, provider, _ in prepared
                ],
            }
        )
        ranges_path = job / "ranges.json"
        ranges_path.write_text(ranges.model_dump_json(indent=2) + "\n", encoding="utf-8")
        inputs = {
            "preview_request": sha256_file(ranges_path),
            "preview_adapter": sha256_file(Path(__file__)),
        }
        outputs = []
        for index, binding_path, manifest_path, preview_path, _, _, clip in prepared:
            inputs[f"composition.{index:02d}"] = sha256_file(binding_path)
            inputs[f"provider_manifest.{index:02d}"] = sha256_file(manifest_path)
            inputs[f"source_preview.{index:02d}"] = sha256_file(preview_path)
            destination = job / f"{index:02d}-provider.mp4"
            shutil.copy2(clip, destination)
            outputs.append(FileRef(path=destination.name, sha256=sha256_file(destination)))
        manifest = RenderManifest(
            schema_version="0.1",
            cache_key=_hash({"inputs": inputs, "outputs": [o.sha256 for o in outputs]}),
            status="completed",
            source_sha256=baseline.source_sha256,
            canonical_audio_sha256=baseline.canonical_audio_sha256,
            profile=baseline.profile,
            inputs=inputs,
            seed=0,
            environment={"adapter": "checked-provider-bundle"},
            ranges=[
                SampleRange(
                    start_sample=provider.range.start_sample,
                    end_sample=provider.range.end_sample,
                )
                for _, _, _, _, _, provider, _ in prepared
            ],
            outputs=outputs,
        )
        (job / "preview.render.json").write_text(
            manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        os.replace(job, output)
        return {
            "ok": True,
            "manifest": str(output / "preview.render.json"),
            "ranges": str(output / "ranges.json"),
            "clips": len(outputs),
            "cache_key": manifest.cache_key,
        }
    finally:
        shutil.rmtree(job, ignore_errors=True)
