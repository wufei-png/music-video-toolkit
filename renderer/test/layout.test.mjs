import assert from "node:assert/strict";
import {test} from "node:test";
import {
  fitCaptionLayout,
  layoutForOutput,
  lyricBounds,
  mediaScale,
  normalizedX,
} from "../dist/index.js";

test("only the closed landscape and portrait dimensions have layouts", () => {
  const landscape = layoutForOutput(1920, 1080);
  const portrait = layoutForOutput(1080, 1920);
  assert.equal(landscape.portrait, false);
  assert.equal(portrait.portrait, true);
  assert.equal(normalizedX(landscape, 1), 16 / 9);
  assert.equal(normalizedX(portrait, 1), 9 / 16);
  assert.throws(() => layoutForOutput(3840, 2160), RangeError);
  assert.throws(() => layoutForOutput(1080, 1080), RangeError);
});

test("cover and contain preserve media aspect in both profiles", () => {
  for (const layout of [layoutForOutput(1920, 1080), layoutForOutput(1080, 1920)]) {
    for (const assetAspect of [1, 16 / 9, 9 / 16]) {
      const cover = mediaScale(layout, assetAspect, "cover");
      const contain = mediaScale(layout, assetAspect, "contain");
      assert.ok(cover.x >= layout.aspect - 1e-12);
      assert.ok(cover.y >= 1 - 1e-12);
      assert.ok(contain.x <= layout.aspect + 1e-12);
      assert.ok(contain.y <= 1 + 1e-12);
      assert.ok(Math.abs(cover.x / cover.y - assetAspect) < 1e-12);
      assert.ok(Math.abs(contain.x / contain.y - assetAspect) < 1e-12);
    }
  }
});

test("portrait lyric mesh stays inside its explicit safe area through motion", () => {
  const layout = layoutForOutput(1080, 1920);
  for (const lift of [-0.047, 0, 0.022]) {
    const bounds = lyricBounds(layout, 1, lift);
    assert.ok(bounds.left >= layout.lyrics.safeLeft);
    assert.ok(bounds.right <= layout.lyrics.safeRight);
    assert.ok(bounds.top >= layout.lyrics.safeTop);
    assert.ok(bounds.bottom <= layout.lyrics.safeBottom);
  }
  assert.equal(layout.lyrics.maximumLines, 5);
  assert.deepEqual(
    [layout.lyrics.meshWidth, layout.lyrics.meshHeight],
    [(2 * 9 * 0.82) / 16, 0.62],
  );
});

test("caption fitting tests the minimum font and rejects remaining overflow", () => {
  const lyrics = layoutForOutput(1080, 1920).lyrics;
  const visited = [];
  const fit = fitCaptionLayout(lyrics, (fontSize) => {
    visited.push(fontSize);
    return fontSize === lyrics.minimumFontSize ? lyrics.maximumLines : lyrics.maximumLines + 1;
  });
  assert.deepEqual(fit, {fontSize: 52, lineCount: 5});
  assert.equal(visited.at(-1), lyrics.minimumFontSize);
  assert.ok(!visited.includes(lyrics.minimumFontSize - lyrics.fontStep));

  assert.throws(
    () => fitCaptionLayout(lyrics, () => lyrics.maximumLines + 1),
    /caption exceeds 5 lines at minimum font size 52/,
  );
});
