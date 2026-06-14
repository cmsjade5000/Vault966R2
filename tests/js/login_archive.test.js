const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/login_archive.js"),
  "utf8",
);

const loadSupport = () => {
  const window = {
    matchMedia: () => ({ matches: false }),
    requestAnimationFrame(callback) {
      callback();
    },
  };
  const context = {
    Image: class {},
    console,
    document: {
      addEventListener() {},
      readyState: "loading",
    },
    window,
  };
  vm.runInNewContext(script, context);
  return window.VaultLoginArchiveSupport;
};

test("uses a deliberate crossfade duration for poster replacements", () => {
  const support = loadSupport();

  assert.equal(support.IMAGE_FADE_MS, 1300);
});

test("marks a decoded poster as loaded before it becomes visible", async () => {
  const support = loadSupport();
  const classes = [];
  const image = {
    classList: {
      add(value) {
        classes.push(value);
      },
    },
    complete: true,
    decode: async () => {},
    naturalWidth: 342,
  };

  assert.equal(await support.markImageReady(image), true);
  assert.deepEqual(classes, ["is-loaded"]);
});
