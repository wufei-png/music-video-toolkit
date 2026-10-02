import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import {fileURLToPath} from "node:url";
import {test} from "node:test";
import {chromium} from "playwright";

test("preserved canvas capture retains frame pixels without animation-frame callbacks", async () => {
  const browser = await chromium.launch({headless: true});
  try {
    for (const [width, height] of [[1920, 1080], [1080, 1920]]) {
      const page = await browser.newPage({viewport: {width, height}, deviceScaleFactor: 1});
      await page.setContent(`<canvas id="mvt-canvas" width="${width}" height="${height}"></canvas>`);
      await page.evaluate(() => {
        window.requestAnimationFrame = () => {
          throw new Error("capture must not depend on real-time animation frames");
        };
      });
      await page.addScriptTag({path: fileURLToPath(new URL("../dist/browser-scene.js", import.meta.url))});
      await page.evaluate(async (config) => {
        await window.MvtScene.initialize(config);
      }, {
        sceneMode: "fixture", width, height, fpsNum: 30, fpsDen: 1,
        pulseFrames: [30], title: "固定帧 · Capture",
        imageDataUrl: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLttAAAAABJRU5ErkJggg==",
      });
      const buffers = [];
      for (const frame of [29, 30, 31, 30]) {
        const dataUrl = await page.evaluate(async (frame) => {
          await window.MvtScene.renderFrame(frame);
          return window.MvtScene.capturePng();
        }, frame);
        assert.ok(dataUrl.startsWith("data:image/png;base64,"));
        const png = Buffer.from(dataUrl.split(",")[1], "base64");
        assert.equal(png.readUInt32BE(16), width);
        assert.equal(png.readUInt32BE(20), height);
        buffers.push(png);
      }
      assert.deepEqual(buffers[1], buffers[3]);
      const luminance = buffers.slice(0, 3).map((png) => execFileSync("ffmpeg", [
        "-v", "error", "-f", "image2pipe", "-i", "pipe:0", "-vf", "scale=1:1,format=gray",
        "-frames:v", "1", "-f", "rawvideo", "pipe:1",
      ], {input: png})[0]);
      assert.ok(luminance[1] > luminance[0] + 100);
      assert.equal(luminance[0], luminance[2]);
      await page.close();
    }
  } finally {
    await browser.close();
  }
});
