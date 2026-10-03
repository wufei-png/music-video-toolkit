import assert from "node:assert/strict";
import {fileURLToPath} from "node:url";
import {test} from "node:test";
import {chromium} from "playwright";

test("ribbon length fits centered canvas fields while omitted legacy length retains pixels", async () => {
  const browser = await chromium.launch({headless: true});
  try {
    for (const [width, height] of [[1920, 1080], [1080, 1920]]) {
      const results = [];
      for (const length of [undefined, 1, 0.75, 16 / 15, 4 / 3]) {
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
          return {png: window.MvtScene.capturePng(), left, right, width: right - left + 1,
            height: top - bottom + 1};
        }));
        await page.close();
      }
      assert.equal(results[0].png, results[1].png);
      assert.ok(results[1].width > width * 0.7);
      assert.ok(Math.abs(results[2].width - results[1].width * 0.75) <= 2);
      assert.ok(Math.abs(results[2].height - results[1].height) <= 2);
      assert.ok(Math.abs(results[3].width - width * 0.8) <= 2);
      assert.ok(Math.abs(results[3].left - width * 0.1) <= 2);
      assert.ok(Math.abs(results[3].right + 1 - width * 0.9) <= 2);
      assert.ok(Math.abs(results[3].height - results[1].height) <= 2);
      assert.ok(Math.abs(results[4].width - width) <= 2);
    }
  } finally {
    await browser.close();
  }
});

test("ribbon sway can be reduced independently of its shape and retains legacy pixels", async () => {
  const browser = await chromium.launch({headless: true});
  try {
    for (const [width, height] of [[1920, 1080], [1080, 1920]]) {
      const variants = [];
      for (const multiplier of [undefined, 1, 0.2, 0]) {
        const page = await browser.newPage({viewport: {width, height}, deviceScaleFactor: 1});
        await page.setContent(`<canvas id="mvt-canvas" width="${width}" height="${height}"></canvas>`);
        await page.addScriptTag({path: fileURLToPath(new URL("../dist/browser-scene.js", import.meta.url))});
        const parameters = {width: 0.018, amplitude: 0.28, length: 0.85, y: 0, color: "#ffffff"};
        if (multiplier !== undefined) parameters.sway_multiplier = multiplier;
        await page.evaluate(async (config) => window.MvtScene.initialize(config), {
          sceneMode: "abstract", width, height, sampleRate: 48000, fpsNum: 30, fpsDen: 1,
          seed: 404, signals: {}, routes: [],
          spans: [{start_sample: 0, end_sample: 960000, transition_samples: 0,
            layers: [{id: "ribbon", kind: "ribbon", category: "abstract",
              enabled: true, opacity: 1, parameters}]}],
        });
        const frames = [];
        for (const frame of [0, 90, 0, 90]) {
          frames.push(await page.evaluate(async (frame) => {
            await window.MvtScene.renderFrame(frame);
            const canvas = document.querySelector("canvas");
            const gl = canvas.getContext("webgl2");
            const pixels = new Uint8Array(canvas.width * canvas.height * 4);
            gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
            let mass = 0, sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0;
            for (let y = 0; y < canvas.height; y += 1) {
              for (let x = 0; x < canvas.width; x += 1) {
                const weight = pixels[(y * canvas.width + x) * 4];
                if (weight < 40) continue;
                mass += weight; sx += weight * x; sy += weight * y;
                sxx += weight * x * x; syy += weight * y * y; sxy += weight * x * y;
              }
            }
            const vx = sxx / mass - (sx / mass) ** 2;
            const vy = syy / mass - (sy / mass) ** 2;
            const cov = sxy / mass - sx * sy / mass ** 2;
            const discriminant = Math.sqrt((vx - vy) ** 2 + 4 * cov ** 2);
            return {png: window.MvtScene.capturePng(), angle: Math.atan2(2 * cov, vx - vy) / 2,
              major: (vx + vy + discriminant) / 2, minor: (vx + vy - discriminant) / 2};
          }, frame));
        }
        variants.push(frames);
        await page.close();
      }
      assert.deepEqual(variants[0], variants[1]);
      for (const frames of variants) {
        assert.equal(frames[0].png, variants[1][0].png);
        assert.equal(frames[0].png, frames[2].png);
        assert.equal(frames[1].png, frames[3].png);
        // Pure rotation preserves both axes of the observed image covariance.
        assert.ok(Math.abs(frames[1].major / frames[0].major - 1) < 0.01);
        assert.ok(Math.abs(frames[1].minor / frames[0].minor - 1) < 0.01);
      }
      const normal = variants[1][1].angle - variants[1][0].angle;
      const reduced = variants[2][1].angle - variants[2][0].angle;
      assert.ok(Math.abs(normal) > 0.05);
      assert.ok(Math.abs(reduced / normal - 0.2) < 0.005);
      assert.equal(variants[3][0].png, variants[3][1].png);
    }
  } finally {
    await browser.close();
  }
});
