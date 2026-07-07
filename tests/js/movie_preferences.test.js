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
    querySelector: () => null,
    querySelectorAll: () => [card],
  };

  removeUnwatchedCard(root, 42, { watchlist: false });
  assert.equal(removed, true);

  removed = false;
  removeUnwatchedCard(root, 42, { watchlist: true });
  assert.equal(removed, false);
});

test("keeps the watchlist grid visible after removing a non-final card", () => {
  const { removeUnwatchedCard } = loadSupport();
  const cards = [
    { dataset: { movieId: "42" }, remove: () => cards.splice(0, 1) },
    { dataset: { movieId: "43" }, remove() {} },
  ];
  const grid = {
    hidden: false,
    querySelectorAll: (selector) =>
      selector === "[data-movie-card]" ? cards : [],
  };
  const emptyState = { hidden: true };
  const total = { textContent: "2" };
  const totalLabel = { textContent: "movies" };
  const root = {
    body: { classList: { contains: (name) => name === "watchlist-page" } },
    querySelector(selector) {
      return {
        "[data-watchlist-grid]": grid,
        "[data-watchlist-empty]": emptyState,
        "[data-watchlist-total]": total,
        "[data-watchlist-total-label]": totalLabel,
      }[selector];
    },
    querySelectorAll: () => [cards[0]],
  };

  removeUnwatchedCard(root, 42, { watchlist: false });

  assert.equal(grid.hidden, false);
  assert.equal(emptyState.hidden, true);
  assert.equal(total.textContent, "1");
  assert.equal(totalLabel.textContent, "movie");
});

test("shows the watchlist empty state after removing the final card", () => {
  const { removeUnwatchedCard } = loadSupport();
  const cards = [{ remove: () => cards.splice(0, 1) }];
  const grid = {
    hidden: false,
    querySelectorAll: (selector) =>
      selector === "[data-movie-card]" ? cards : [],
  };
  const emptyState = { hidden: true };
  const total = { textContent: "1" };
  const totalLabel = { textContent: "movie" };
  const root = {
    body: { classList: { contains: (name) => name === "watchlist-page" } },
    querySelector(selector) {
      return {
        "[data-watchlist-grid]": grid,
        "[data-watchlist-empty]": emptyState,
        "[data-watchlist-total]": total,
        "[data-watchlist-total-label]": totalLabel,
      }[selector];
    },
    querySelectorAll: () => cards,
  };

  removeUnwatchedCard(root, 42, { watchlist: false });

  assert.equal(grid.hidden, true);
  assert.equal(emptyState.hidden, false);
  assert.equal(total.textContent, "0");
  assert.equal(totalLabel.textContent, "movies");
});
