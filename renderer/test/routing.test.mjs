import assert from "node:assert/strict";
import {test} from "node:test";
import {sampleSignal, smoothValue, targetValue} from "../dist/index.js";

const signal = {start_sample: 0, hop_samples: 100, values: [0, 1, 0.5]};

test("signal sampling linearly interpolates and holds endpoint values", () => {
  assert.equal(sampleSignal(signal, 0), 0);
  assert.equal(sampleSignal(signal, 50), 0.5);
  assert.equal(sampleSignal(signal, 100), 1);
  assert.equal(sampleSignal(signal, 150), 0.75);
  assert.equal(sampleSignal(signal, 999), 0.5);
});

test("registered transforms map normalized signals into resolved bounds", () => {
  assert.equal(targetValue(0.25, {kind: "linear", parameters: {min: 0.2, max: 1}}), 0.4);
  assert.equal(
    targetValue(0.5, {kind: "threshold", parameters: {threshold: 0.5, low: 0.1, high: 0.9}}),
    0.9,
  );
});

test("attack and release smoothing are explicit and deterministic", () => {
  const transform = {
    kind: "smooth",
    parameters: {min: 0, max: 1, attack_seconds: 0.1, release_seconds: 0.5},
  };
  const attack = smoothValue(0, 1, 1 / 30, transform);
  const release = smoothValue(1, 0, 1 / 30, transform);
  assert.ok(attack > 1 - release);
  assert.equal(smoothValue(0.2, 0.8, 1 / 30, {kind: "linear", parameters: {}}), 0.8);
});
