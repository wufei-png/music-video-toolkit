import assert from "node:assert/strict";
import {fileURLToPath} from "node:url";
import {test} from "node:test";
import {chromium} from "playwright";

test("ribbon length narrows real canvas ink while omitted legacy length retains pixels", async () => {
  const browser = await chromium.launch({headless: true});
  try {
    for (const [width, height] of [[1920, 1080], [1080, 1920]]) {
      const results = [];
      for (const length of [undefined, 1, 0.75]) {
        const page = await browser.newPage({viewport: {width, height}, deviceScaleFactor: 1});
        await page.setContent(`<canvas id="mvt-canvas" width="${width}" height="${height}"></canvas>`);
        await page.addScriptTag({path: fileURLToPath(new URL("../dist/browser-scene.js", import.meta.url))});
        const parameters = {width: 0.012, amplitude: 0.2, y: 0, color: "#ffffff"};
        if (length !== undefined) parameters.length = length;
        await page.evaluate(async (config) => {
          await window.MvtScene.initialize(config);
          await window.MvtScene.renderFrame(0);
        }, {
          sceneMode: "abstract", width, height, sampleRate: 48000, fpsNum: 30, fpsDen: 1,
          seed: 404, signals: {}, routes: [],
          spans: [{start_sample: 0, end_sample: 144000, transition_samples: 0,
            layers: [{id: "ribbon", kind: "ribbon", category: "abstract",
              enabled: true, opacity: 1, parameters}]}],
        });
        results.push(await page.evaluate(() => {
          const canvas = document.querySelector("canvas");
          const gl = canvas.getContext("webgl2");
          const pixels = new Uint8Array(canvas.width * canvas.height * 4);
          gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
          let left = canvas.width, right = -1, bottom = canvas.height, top = -1;
          for (let y = 0; y < canvas.height; y += 1) {
            for (let x = 0; x < canvas.width; x += 1) {
              if (pixels[(y * canvas.width + x) * 4] > 70) {
                left = Math.min(left, x); right = Math.max(right, x);
                bottom = Math.min(bottom, y); top = Math.max(top, y);
              }
            }
          }
          return {png: window.MvtScene.capturePng(), width: right - left + 1,
            height: top - bottom + 1};
        }));
        await page.close();
      }
      assert.equal(results[0].png, results[1].png);
      assert.ok(results[1].width > width * 0.7);
      assert.ok(Math.abs(results[2].width - results[1].width * 0.75) <= 2);
      assert.ok(Math.abs(results[2].height - results[1].height) <= 2);
    }
  } finally {
    await browser.close();
  }
});
