import assert from "node:assert/strict";
import {test} from "node:test";
import {activeCueAtSample, firstFrameAtSample, lyricOpacity} from "../dist/index.js";

const cues = [
  {start_sample: 1, end_sample: 1600, text: "第一行\nFirst line"},
  {start_sample: 4800, end_sample: 9600, text: "Repeated chorus"},
];

test("lyric cues use half-open sample ownership and preserve interludes", () => {
  assert.equal(activeCueAtSample(cues, 0), -1);
  assert.equal(activeCueAtSample(cues, 1), 0);
  assert.equal(activeCueAtSample(cues, 1599), 0);
  assert.equal(activeCueAtSample(cues, 1600), -1);
  assert.equal(activeCueAtSample(cues, 4800), 1);
});

test("cue onset quantizes forward and fade remains visible at its first sample", () => {
  assert.equal(firstFrameAtSample(1, {sampleRate: 48000, fpsNum: 30, fpsDen: 1}), 1);
  assert.ok(lyricOpacity(cues[0], 1, 480) > 0);
  assert.equal(lyricOpacity(cues[0], 1600, 480), 0);
  assert.equal(lyricOpacity(cues[1], 7000, 480), 1);
});
