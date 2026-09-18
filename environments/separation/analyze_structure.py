"""Deterministic beat-synchronous repeated-structure analysis from a saved timeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import librosa
import numpy as np

CHROMA_NAMES = (
    "c",
    "c_sharp",
    "d",
    "d_sharp",
    "e",
    "f",
    "f_sharp",
    "g",
    "g_sharp",
    "a",
    "a_sharp",
    "b",
)
SILENCE_EPSILON = 1e-12
PARAMETERS = {
    "anchor_policy": "canonical endpoints plus sorted unique interior mix beat estimates",
    "feature_policy": "mean beat-synchronized mix RMS plus L2-normalized 12-bin mix chroma",
    "similarity": "cosine self-similarity on beat-synchronized feature cells",
    "novelty_window_cells": 4,
    "novelty_threshold": 0.12,
    "novelty_energy_weight": 0.25,
    "repetition_similarity_threshold": 0.86,
    "minimum_repeated_cells": 3,
    "maximum_repeated_cells": 16,
    "maximum_repeated_groups": 8,
    "silence_epsilon": SILENCE_EPSILON,
    "semantics": "unlabeled candidates; no downbeat, bar, pitch, melody or section-name inference",
}


def _signal(timeline: dict[str, object], name: str) -> tuple[np.ndarray, int, int]:
    signals = timeline.get("signals")
    if not isinstance(signals, dict) or name not in signals:
        raise ValueError(f"timeline is missing {name}")
    signal = signals[name]
    if not isinstance(signal, dict):
        raise ValueError(f"timeline signal {name} is invalid")
    values = np.asarray(signal.get("values"), dtype=np.float64)
    start = int(signal.get("start_sample", 0))
    hop = int(signal["hop_samples"])
    if values.ndim != 1 or not np.all(np.isfinite(values)) or hop <= 0:
        raise ValueError(f"timeline signal {name} is invalid")
    return values, start, hop


def _anchors(timeline: dict[str, object], duration: int) -> tuple[list[int], list[int]]:
    events = timeline.get("events", [])
    beats = sorted(
        {
            int(event["sample"])
            for event in events
            if isinstance(event, dict)
            and event.get("name") == "beat"
            and event.get("source") == "mix"
            and 0 < int(event["sample"]) < duration
        }
    )
    return [0, *beats, duration], beats


def _synchronize(
    values: np.ndarray,
    start_sample: int,
    hop_samples: int,
    anchors: list[int],
) -> np.ndarray:
    frame_samples = start_sample + np.arange(values.size, dtype=np.int64) * hop_samples
    synchronized = []
    for left, right in zip(anchors, anchors[1:], strict=False):
        selected = values[(frame_samples >= left) & (frame_samples < right)]
        synchronized.append(float(np.mean(selected)) if selected.size else 0.0)
    return np.asarray(synchronized, dtype=np.float64)


def _features(timeline: dict[str, object], anchors: list[int]) -> tuple[np.ndarray, np.ndarray]:
    rms, start, hop = _signal(timeline, "mix.rms")
    energy = _synchronize(rms, start, hop, anchors)
    chroma_rows = []
    for name in CHROMA_NAMES:
        values, chroma_start, chroma_hop = _signal(timeline, f"mix.chroma.{name}")
        chroma_rows.append(_synchronize(values, chroma_start, chroma_hop, anchors))
    chroma = np.vstack(chroma_rows)
    chroma_norm = np.linalg.norm(chroma, axis=0)
    nonzero = chroma_norm > SILENCE_EPSILON
    chroma[:, nonzero] /= chroma_norm[nonzero]
    combined = np.vstack((chroma, energy[np.newaxis, :] * 0.5)).T
    feature_norm = np.linalg.norm(combined, axis=1)
    normalized = np.zeros_like(combined)
    active = feature_norm > SILENCE_EPSILON
    normalized[active] = combined[active] / feature_norm[active, np.newaxis]
    return normalized, energy


def _novelty(similarity: np.ndarray, energy: np.ndarray) -> list[tuple[int, float]]:
    count = similarity.shape[0]
    scores = np.zeros(count, dtype=np.float64)
    for boundary in range(1, count):
        window = min(int(PARAMETERS["novelty_window_cells"]), boundary, count - boundary)
        if window <= 0:
            continue
        left = similarity[boundary - window : boundary, boundary - window : boundary]
        right = similarity[boundary : boundary + window, boundary : boundary + window]
        cross = similarity[boundary - window : boundary, boundary : boundary + window]
        contrast = max(
            0.0, (float(np.mean(left)) + float(np.mean(right))) / 2 - float(np.mean(cross))
        )
        energy_change = abs(float(energy[boundary]) - float(energy[boundary - 1]))
        weight = float(PARAMETERS["novelty_energy_weight"])
        scores[boundary] = np.clip((1 - weight) * contrast + weight * energy_change, 0, 1)
    threshold = float(PARAMETERS["novelty_threshold"])
    return [
        (index, float(score))
        for index, score in enumerate(scores)
        if index > 0
        and score >= threshold
        and score >= scores[index - 1]
        and (index + 1 == count or score >= scores[index + 1])
    ]


def _repetitions(similarity: np.ndarray, energy: np.ndarray) -> list[tuple[int, int, int, float]]:
    count = similarity.shape[0]
    minimum = int(PARAMETERS["minimum_repeated_cells"])
    maximum = int(PARAMETERS["maximum_repeated_cells"])
    threshold = float(PARAMETERS["repetition_similarity_threshold"])
    candidates: list[tuple[int, int, int, float]] = []
    for left in range(count):
        for right in range(left + minimum, count):
            limit = min(maximum, right - left, count - right)
            length = 0
            while length < limit and similarity[left + length, right + length] >= threshold:
                length += 1
            if length < minimum:
                continue
            score = float(np.mean([similarity[left + i, right + i] for i in range(length)]))
            if (
                max(
                    float(np.max(energy[left : left + length])),
                    float(np.max(energy[right : right + length])),
                )
                <= SILENCE_EPSILON
            ):
                continue
            candidates.append((left, right, length, score))
    selected: list[tuple[int, int, int, float]] = []
    for candidate in sorted(candidates, key=lambda item: (-item[2], -item[3], item[0], item[1])):
        left, right, length, _ = candidate
        spans = {(left, left + length), (right, right + length)}
        if any(
            spans & {(item[0], item[0] + item[2]), (item[1], item[1] + item[2])}
            for item in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) >= int(PARAMETERS["maximum_repeated_groups"]):
            break
    return sorted(selected, key=lambda item: (item[0], item[1]))


def analyze(timeline: dict[str, object]) -> dict[str, object]:
    source = timeline.get("source")
    if not isinstance(source, dict):
        raise ValueError("timeline source is missing")
    duration = int(source["duration_samples"])
    anchors, beats = _anchors(timeline, duration)
    features, energy = _features(timeline, anchors)
    if features.size == 0 or float(np.max(np.abs(features))) <= SILENCE_EPSILON:
        similarity = np.zeros((len(anchors) - 1, len(anchors) - 1), dtype=np.float64)
        novelty = []
        repetitions = []
    else:
        similarity = np.clip(features @ features.T, 0, 1)
        novelty = _novelty(similarity, energy)
        repetitions = _repetitions(similarity, energy)

    groups = []
    boundary_sources: dict[int, list[tuple[str, float]]] = {}
    for index, score in novelty:
        boundary_sources.setdefault(anchors[index], []).append(("novelty", score))
    for group_index, (left, right, length, score) in enumerate(repetitions, 1):
        group_id = f"repeat-{group_index:03d}"
        spans = []
        for span_index, start in enumerate((left, right), 1):
            spans.append(
                {
                    "id": f"{group_id}-{span_index}",
                    "group_id": group_id,
                    "start_sample": anchors[start],
                    "end_sample": anchors[start + length],
                    "confidence": score,
                    "start_anchor_index": start,
                    "end_anchor_index": start + length,
                }
            )
            for boundary in (anchors[start], anchors[start + length]):
                if 0 < boundary < duration:
                    boundary_sources.setdefault(boundary, []).append((group_id, score))
        groups.append({"id": group_id, "confidence": score, "spans": spans})

    boundaries = []
    for index, (sample, evidence) in enumerate(sorted(boundary_sources.items()), 1):
        boundaries.append(
            {
                "id": f"boundary-{index:03d}",
                "sample": sample,
                "confidence": max(score for _, score in evidence),
                "sources": sorted({source for source, _ in evidence}),
            }
        )
    return {
        "librosa_version": librosa.__version__,
        "parameters": PARAMETERS,
        "beat_samples": beats,
        "boundaries": boundaries,
        "repeated_groups": groups,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    timeline = json.loads(args.timeline.read_text(encoding="utf-8"))
    result = analyze(timeline)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
