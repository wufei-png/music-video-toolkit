import assert from "node:assert/strict";
import {fileURLToPath} from "node:url";
import {test} from "node:test";
import {chromium} from "playwright";

test("fixed particles retain positions at global times while legacy rotation retains pixels", async () => {
  const browser = await chromium.launch({headless: true});
  try {
    for (const [width, height] of [[1920, 1080], [1080, 1920]]) {
      const results = [];
      for (const speed of [undefined, 0.05, 0]) {
        const page = await browser.newPage({viewport: {width, height}, deviceScaleFactor: 1});
        await page.setContent(`<canvas id="mvt-canvas" width="${width}" height="${height}"></canvas>`);
        await page.addScriptTag({path: fileURLToPath(new URL("../dist/browser-scene.js", import.meta.url))});
        const parameters = {count: 40, size: 0.015, spread: 0.6, color: "#ffffff"};
        if (speed !== undefined) parameters.rotation_speed = speed;
        await page.evaluate(async (config) => window.MvtScene.initialize(config), {
          sceneMode: "abstract", width, height, sampleRate: 48000, fpsNum: 30, fpsDen: 1,
          seed: 404, signals: {}, routes: [],
          spans: [{start_sample: 0, end_sample: 960000, transition_samples: 0,
            layers: [{id: "particles", kind: "particles", category: "abstract",
              enabled: true, opacity: 1, parameters}]}],
        });
        const frames = [];
        // Seek in both directions: static positions must not depend on render history.
        for (const frame of [300, 0, 300]) {
          frames.push(await page.evaluate(async (frame) => {
            await window.MvtScene.renderFrame(frame);
            return window.MvtScene.capturePng();
          }, frame));
        }
        results.push(frames);
        await page.close();
      }
      assert.deepEqual(results[0], results[1]);
      assert.notEqual(results[1][0], results[1][1]);
      assert.equal(results[1][0], results[1][2]);
      assert.equal(results[2][0], results[2][1]);
      assert.equal(results[2][0], results[2][2]);
      assert.equal(results[2][1], results[1][1]);
    }
  } finally {
    await browser.close();
  }
});
