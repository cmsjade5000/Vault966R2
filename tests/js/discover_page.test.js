const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/discover_page.js"),
  "utf8",
);

const loadSupport = () => {
  const window = {};
  const context = {
    document: {
      addEventListener() {},
    },
    window,
  };
  vm.runInNewContext(script, context);
  return window.VaultDiscoverSupport;
};

const createPoster = () => {
  const fallback = { hidden: true };
  const frame = {
    dataset: {},
    querySelector(selector) {
      return selector === "[data-discover-poster-fallback]" ? fallback : null;
    },
  };
  const listeners = {};
  const image = {
    complete: false,
    hidden: false,
    naturalWidth: 0,
    addEventListener(name, callback) {
      listeners[name] = callback;
    },
    closest(selector) {
      return selector === "[data-discover-poster-frame]" ? frame : null;
    },
  };
  return { fallback, frame, image, listeners };
};

test("marks a successfully loaded poster without changing its source", () => {
  const { markPosterLoaded } = loadSupport();
  const { frame, image } = createPoster();
  image.src = "/ui/posters/42/w185";

  assert.equal(markPosterLoaded(image), true);
  assert.equal(frame.dataset.posterState, "loaded");
  assert.equal(image.src, "/ui/posters/42/w185");
});

test("reveals the themed fallback after a poster error", () => {
  const { revealPosterFallback } = loadSupport();
  const { fallback, frame, image } = createPoster();

  assert.equal(revealPosterFallback(image), true);
  assert.equal(image.hidden, true);
  assert.equal(fallback.hidden, false);
  assert.equal(frame.dataset.posterState, "fallback");
});

test("poster fallback setup handles already failed images", () => {
  const { setupPosterFallbacks } = loadSupport();
  const { fallback, image, listeners } = createPoster();
  image.complete = true;
  const root = {
    querySelectorAll(selector) {
      return selector === "[data-discover-poster]" ? [image] : [];
    },
  };

  assert.equal(setupPosterFallbacks(root), 1);
  assert.equal(typeof listeners.load, "function");
  assert.equal(typeof listeners.error, "function");
  assert.equal(image.hidden, true);
  assert.equal(fallback.hidden, false);
});

test("poster fallback setup accepts an empty page", () => {
  const { setupPosterFallbacks } = loadSupport();
  const root = { querySelectorAll: () => [] };

  assert.equal(setupPosterFallbacks(root), 0);
});
