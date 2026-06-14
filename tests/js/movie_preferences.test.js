const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/movie_preferences.js"),
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
  return window.VaultMoviePreferencesSupport;
};

test("builds accessible labels for both preference types", () => {
  const { buildPreferenceLabel } = loadSupport();

  assert.equal(buildPreferenceLabel("like", false, "Alien"), "Like Alien");
  assert.equal(buildPreferenceLabel("like", true, "Alien"), "Unlike Alien");
  assert.equal(
    buildPreferenceLabel("watchlist", false, "Alien"),
    "Add Alien to watchlist",
  );
  assert.equal(
    buildPreferenceLabel("watchlist", true, "Alien"),
    "Remove Alien from watchlist",
  );
});

test("removes an unwatched card only on the watchlist page", () => {
  const { removeUnwatchedCard } = loadSupport();
  let removed = false;
  const card = { remove: () => (removed = true) };
  const root = {
    body: { classList: { contains: (name) => name === "watchlist-page" } },
    querySelectorAll: () => [card],
  };

  removeUnwatchedCard(root, 42, { watchlist: false });
  assert.equal(removed, true);

  removed = false;
  removeUnwatchedCard(root, 42, { watchlist: true });
  assert.equal(removed, false);
});
