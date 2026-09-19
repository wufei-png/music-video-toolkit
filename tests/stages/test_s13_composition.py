"""Public synthetic provider media enters existing MVT preview contracts."""

import json
from pathlib import Path

from test_s13_protocol import fake_provider as protocol_fixture

from music_video_toolkit.audio import decode_audio
from music_video_toolkit.contracts import RenderManifest
from music_video_toolkit.documents import read_document
from music_video_toolkit.project import sha256_file
from music_video_toolkit.provider_composition import compose_provider_preview


def test_checked_provider_video_gets_canonical_audio_and_preview_manifest(tmp_path):
    request_path, manifest_path, _, request, manifest = protocol_fixture.__wrapped__(tmp_path)
    project = tmp_path / "mvt-project"
    decoded = decode_audio(tmp_path / "canonical.wav", project)
    timeline_path = project / "timeline.json"
    timeline_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "source": {
                    "path": "source/canonical.wav",
                    "sha256": decoded.record.canonical.sha256,
                    "sample_rate": 48000,
                    "duration_samples": 48000,
                },
                "analysis": [],
                "signals": {},
                "events": [],
                "sections": [],
            }
        ),
        encoding="utf-8",
    )
    request["source"]["path"] = str(decoded.canonical_path)
    request["source"]["sha256"] = decoded.record.canonical.sha256
    request["canonical_audio"] = {
        "path": str(decoded.canonical_path),
        "sha256": decoded.record.canonical.sha256,
    }
    request_path.write_text(json.dumps(request), encoding="utf-8")
    manifest["source_sha256"] = decoded.record.canonical.sha256
    manifest["request"]["sha256"] = sha256_file(request_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    output = tmp_path / "composed"
    report = compose_provider_preview(project, request_path, manifest_path, timeline_path, output)
    preview = RenderManifest.model_validate(read_document(Path(report["preview_manifest"])))
    assert preview.status == "completed"
    assert preview.canonical_audio_sha256 == decoded.record.canonical.sha256
    assert preview.inputs["asset.provider-video"] == manifest["video"]["sha256"]
    assert preview.inputs["preview_request"] == sha256_file(output / "ranges.json")
    assert (output / "preview/01-provider-range.mp4").is_file()
