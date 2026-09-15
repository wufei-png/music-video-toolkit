import {build} from "esbuild";

await build({
  entryPoints: ["src/browser-scene.ts"],
  bundle: true,
  format: "iife",
  globalName: "MvtScene",
  outfile: "dist/browser-scene.js",
});
