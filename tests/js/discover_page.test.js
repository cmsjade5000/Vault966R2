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

test("carousel state exposes start, progress, and end positions", () => {
  const { calculateRailState } = loadSupport();

  assert.deepEqual(
    JSON.parse(
      JSON.stringify(
        calculateRailState({
          clientWidth: 400,
          scrollLeft: 0,
          scrollWidth: 800,
        }),
      ),
    ),
    { atEnd: false, atStart: true, progressScale: 0.32 },
  );

  const end = calculateRailState({
    clientWidth: 400,
    scrollLeft: 400,
    scrollWidth: 800,
  });
  assert.equal(end.atEnd, true);
  assert.equal(end.atStart, false);
  assert.equal(end.progressScale, 1);
});

test("carousel controls advance most of a viewport with a touch-safe minimum", () => {
  const { getScrollDistance } = loadSupport();

  assert.equal(getScrollDistance(200), 240);
  assert.equal(getScrollDistance(1000), 780);
});

test("deferred poster hydration promotes data source once", () => {
  const { hydrateDeferredPoster } = loadSupport();
  const image = {
    dataset: { posterSrc: "/ui/posters/42/w185" },
    removeAttribute(name) {
      if (name === "data-poster-src") delete this.dataset.posterSrc;
    },
  };

  assert.equal(hydrateDeferredPoster(image), true);
  assert.equal(image.src, "/ui/posters/42/w185");
  assert.equal(image.dataset.posterHydrated, "true");
  assert.equal(image.dataset.posterSrc, undefined);
  assert.equal(hydrateDeferredPoster(image), false);
});
