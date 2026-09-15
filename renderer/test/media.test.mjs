import assert from "node:assert/strict";
import {test} from "node:test";
import {videoFrameAtSample} from "../dist/index.js";

const clock = {fpsNum: 30, fpsDen: 1, frameCount: 6};

test("video mapping honors offset and trim points", () => {
  const policy = {offset_samples: 48000, in_frame: 1, out_frame: 5, end_behavior: "hold"};
  assert.equal(videoFrameAtSample(0, 48000, clock, policy), 1);
  assert.equal(videoFrameAtSample(48000, 48000, clock, policy), 1);
  assert.equal(videoFrameAtSample(49600, 48000, clock, policy), 2);
});

test("video loop and hold end behaviors select exact numbered frames", () => {
  const base = {offset_samples: 0, in_frame: 1, out_frame: 4};
  assert.equal(videoFrameAtSample(3 * 1600, 48000, clock, {...base, end_behavior: "loop"}), 1);
  assert.equal(videoFrameAtSample(8 * 1600, 48000, clock, {...base, end_behavior: "loop"}), 3);
  assert.equal(videoFrameAtSample(8 * 1600, 48000, clock, {...base, end_behavior: "hold"}), 3);
  assert.throws(
    () => videoFrameAtSample(8 * 1600, 48000, clock, {...base, end_behavior: "error"}),
    RangeError,
  );
});
