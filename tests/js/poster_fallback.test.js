const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/poster_fallback.js"),
  "utf8",
);

const createPoster = () => {
  const fallback = { hidden: true };
  const frame = {
    dataset: {},
    querySelector(selector) {
      return selector === "[data-poster-fallback]" ? fallback : null;
    },
  };
  const image = {
    complete: false,
    hidden: false,
    naturalWidth: 0,
    closest(selector) {
      return selector === "[data-poster-frame]" ? frame : null;
    },
    matches(selector) {
      return selector === "[data-poster-image]";
    },
  };
  return { fallback, frame, image };
};

const loadSupport = () => {
  const rootListeners = {};
  const document = {
    readyState: "loading",
    addEventListener(name, callback) {
      rootListeners[name] = callback;
    },
    querySelectorAll() {
      return [];
    },
  };
  const window = {};
  vm.runInNewContext(script, { document, window });
  return { rootListeners, support: window.VaultPosterFallbackSupport };
};

test("swaps a failed poster for its existing themed fallback", () => {
  const { support } = loadSupport();
  const { fallback, frame, image } = createPoster();

  assert.equal(support.revealPosterFallback(image), true);
  assert.equal(image.hidden, true);
  assert.equal(fallback.hidden, false);
  assert.equal(frame.dataset.posterState, "fallback");
});

test("marks a loaded poster and keeps its fallback hidden", () => {
  const { support } = loadSupport();
  const { fallback, frame, image } = createPoster();
  image.hidden = true;
  fallback.hidden = false;

  assert.equal(support.markPosterLoaded(image), true);
  assert.equal(image.hidden, false);
  assert.equal(fallback.hidden, true);
  assert.equal(frame.dataset.posterState, "loaded");
});

test("captured resource events cover posters added after setup", () => {
  const { support } = loadSupport();
  const listeners = {};
  const root = {
    addEventListener(name, callback, capture) {
      listeners[name] = { callback, capture };
    },
    querySelectorAll() {
      return [];
    },
  };
  const { fallback, image } = createPoster();

  assert.equal(support.setupPosterFallbacks(root), 0);
  assert.equal(listeners.error.capture, true);
  listeners.error.callback({ target: image });
  assert.equal(image.hidden, true);
  assert.equal(fallback.hidden, false);
});

test("setup resolves images that completed before listeners attached", () => {
  const { support } = loadSupport();
  const failed = createPoster();
  const loaded = createPoster();
  failed.image.complete = true;
  loaded.image.complete = true;
  loaded.image.naturalWidth = 185;
  const root = {
    addEventListener() {},
    querySelectorAll() {
      return [failed.image, loaded.image];
    },
  };

  assert.equal(support.setupPosterFallbacks(root), 2);
  assert.equal(failed.fallback.hidden, false);
  assert.equal(loaded.fallback.hidden, true);
  assert.equal(loaded.frame.dataset.posterState, "loaded");
});
