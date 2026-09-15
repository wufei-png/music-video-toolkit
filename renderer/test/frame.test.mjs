import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { sampleAtFrame, firstFrameAtSample, frameContext } from "../dist/index.js";

const cases = JSON.parse(readFileSync(new URL("../../tests/fixtures/clock.json", import.meta.url)));
for (const row of cases.frames) {
  test(`frame ${row.frame} at ${row.clock.fpsNum}/${row.clock.fpsDen}`, () => {
    assert.equal(sampleAtFrame(row.frame, row.clock), row.sample);
  });
}
for (const row of cases.events) {
  test(`event at sample ${row.sample}`, () => {
    assert.equal(firstFrameAtSample(row.sample, row.clock), row.frame);
    assert.ok(sampleAtFrame(row.frame, row.clock) >= row.sample);
    if (row.frame > 0) assert.ok(sampleAtFrame(row.frame - 1, row.clock) < row.sample);
  });
}
const clock = {sampleRate: 48000, fpsNum: 30, fpsDen: 1};
test("excerpt context retains whole-song time", () => {
  const first = frameContext(900, clock, 42);
  assert.equal(first.sample, 1440000);
  assert.equal(first.seconds, 30);
  assert.equal(first.deltaSeconds, 1/30);
  assert.ok(Object.isFrozen(first));
});
test("invalid and overflowing times are rejected", () => {
  for (const value of [-1, 1.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(() => sampleAtFrame(value, clock), RangeError);
  }
  assert.throws(() => sampleAtFrame(1, {...clock, fpsDen: 0}), RangeError);
  assert.throws(() => sampleAtFrame(Number.MAX_SAFE_INTEGER, clock), RangeError);
  assert.throws(() => frameContext(0, clock, -1), RangeError);
});
