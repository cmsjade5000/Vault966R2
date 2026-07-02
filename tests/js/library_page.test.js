const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/library_page.js"),
  "utf8",
);

const loadSupport = () => {
  const window = {};
  const context = {
    URL,
    URLSearchParams,
    document: {
      addEventListener() {},
    },
    window,
  };
  vm.runInNewContext(script, context);
  return window.VaultLibrarySupport;
};

test("clearing a preset removes Hidden Gems and preserves other filters", () => {
  const { buildClearFilterUrl } = loadSupport();
  const result = new URL(
    buildClearFilterUrl(
      "http://127.0.0.1:8000/ui/movies?preset=hidden-gems&view=list&genres=Drama&page=3",
      "preset",
    ),
  );

  assert.equal(result.searchParams.has("preset"), false);
  assert.equal(result.searchParams.get("view"), "list");
  assert.equal(result.searchParams.get("genres"), "Drama");
  assert.equal(result.searchParams.get("_filters"), "1");
  assert.equal(result.searchParams.get("page"), "1");
});

test("clearing a search chip removes q and preserves filters", () => {
  const { buildClearFilterUrl } = loadSupport();
  const result = new URL(
    buildClearFilterUrl(
      "http://127.0.0.1:8000/ui/movies?q=Titanic&genres=Drama&view=grid&order_by=title_asc&page=3",
      "q",
    ),
  );

  assert.equal(result.searchParams.has("q"), false);
  assert.equal(result.searchParams.get("genres"), "Drama");
  assert.equal(result.searchParams.get("view"), "grid");
  assert.equal(result.searchParams.get("order_by"), "title_asc");
  assert.equal(result.searchParams.get("_filters"), "1");
  assert.equal(result.searchParams.get("page"), "1");
});

test("clearing the only search chip removes explicit sort", () => {
  const { buildClearFilterUrl } = loadSupport();
  const result = new URL(
    buildClearFilterUrl(
      "http://127.0.0.1:8000/ui/movies?q=Titanic&view=grid&order_by=title_asc&page=3",
      "q",
    ),
  );

  assert.equal(result.searchParams.has("q"), false);
  assert.equal(result.searchParams.has("order_by"), false);
  assert.equal(result.searchParams.get("_filters"), "1");
  assert.equal(result.searchParams.get("page"), "1");
});

test("clearing a cookie-backed preset marks the URL as authoritative", () => {
  const { buildClearFilterUrl } = loadSupport();
  const result = new URL(
    buildClearFilterUrl("http://127.0.0.1:8000/ui/movies", "preset"),
  );

  assert.equal(result.searchParams.has("preset"), false);
  assert.equal(result.searchParams.get("_filters"), "1");
  assert.equal(result.searchParams.get("page"), "1");
});

test("clear all removes filters and sort while preserving view", () => {
  const { buildClearAllFiltersUrl } = loadSupport();
  const result = new URL(
    buildClearAllFiltersUrl(
      "http://127.0.0.1:8000/ui/movies?q=alien&preset=hidden-gems&genres=Drama&year_min=1990&runtime_max=120&view=list&order_by=title&page=4",
    ),
  );

  assert.equal(result.searchParams.has("q"), false);
  assert.equal(result.searchParams.has("preset"), false);
  assert.equal(result.searchParams.has("genres"), false);
  assert.equal(result.searchParams.has("year_min"), false);
  assert.equal(result.searchParams.has("runtime_max"), false);
  assert.equal(result.searchParams.get("view"), "list");
  assert.equal(result.searchParams.has("order_by"), false);
  assert.equal(result.searchParams.get("_filters"), "1");
  assert.equal(result.searchParams.get("page"), "1");
});

test("builds pending filter summary and counts each visible chip", () => {
  const { buildPendingSummary, formatApplyLabel } = loadSupport();
  const summary = buildPendingSummary({
    genres: ["Drama", "Science Fiction"],
    presetName: "Thoughtful Dramas",
    runtimeMax: "120",
    yearLabel: "1990s",
  });

  assert.deepEqual(JSON.parse(JSON.stringify(summary)), [
    { kind: "preset", label: "Fliclist: Thoughtful Dramas" },
    { kind: "genre", label: "Drama" },
    { kind: "genre", label: "Science Fiction" },
    { kind: "year", label: "1990s" },
    { kind: "runtime", label: "≤ 120 min" },
  ]);
  assert.equal(formatApplyLabel(summary.length), "Show results · 5 filters");
  assert.equal(formatApplyLabel(1), "Show results · 1 filter");
  assert.equal(formatApplyLabel(0), "Show results");
});

test("reset state clears only filter values", () => {
  const { emptyFilterState } = loadSupport();

  assert.deepEqual(JSON.parse(JSON.stringify(emptyFilterState())), {
    genres: [],
    presetName: "",
    runtimeMax: "",
    yearMax: "",
    yearMin: "",
  });
});

test("formats URL preset names for the pending summary", () => {
  const { formatPresetName, parseCsv } = loadSupport();

  assert.equal(formatPresetName("hidden-gems"), "Hidden Gems");
  assert.deepEqual(Array.from(parseCsv("Drama, Science Fiction, ")), [
    "Drama",
    "Science Fiction",
  ]);
});

test("recommendation params use the first genre and mood", () => {
  const { buildRecommendationParams, buildRecommendationUrl } = loadSupport();
  const params = buildRecommendationParams({
    genres: new Set(["Drama", "Science Fiction"]),
    moodsValue: "Moody, Exciting",
    runtimeMax: "120",
    yearMax: "1999",
    yearMin: "1980",
  });

  assert.equal(params.get("genre"), "Drama");
  assert.equal(params.get("mood"), "Moody");
  assert.equal(params.get("runtime_max"), "120");
  assert.equal(params.get("year_min"), "1980");
  assert.equal(params.get("year_max"), "1999");
  assert.equal(
    buildRecommendationUrl("/movies/picks", params),
    "/movies/picks?genre=Drama&mood=Moody&year_min=1980&year_max=1999&runtime_max=120",
  );
});

test("double feature params do not treat single-movie runtime as pair cap", () => {
  const { buildRecommendationParams } = loadSupport();
  const params = buildRecommendationParams(
    {
      genres: ["Action"],
      moodsValue: "Exciting",
      runtimeMax: "90",
    },
    { includeRuntime: false },
  );

  assert.equal(params.get("genre"), "Action");
  assert.equal(params.get("mood"), "Exciting");
  assert.equal(params.has("runtime_max"), false);
});

test("recommendation busy messages reflect scope and slow states", () => {
  const { recommendationBusyMessage } = loadSupport();
  const empty = new URLSearchParams();
  const filtered = new URLSearchParams({ genre: "Drama" });

  assert.equal(
    recommendationBusyMessage(empty),
    "Choosing from the full Vault…",
  );
  assert.equal(
    recommendationBusyMessage(filtered),
    "Choosing from your filtered results…",
  );
  assert.equal(
    recommendationBusyMessage(filtered, { kind: "double-feature" }),
    "Pairing movies from your filters…",
  );
  assert.equal(
    recommendationBusyMessage(filtered, { stage: "slow" }),
    "Still checking trusted picks…",
  );
  assert.equal(
    recommendationBusyMessage(filtered, { stage: "long" }),
    "This is taking longer than usual…",
  );
});

test("shows custom controls only when selected or holding a non-preset value", () => {
  const { shouldShowCustomControl } = loadSupport();

  assert.equal(shouldShowCustomControl(), false);
  assert.equal(shouldShowCustomControl({ selected: true }), true);
  assert.equal(
    shouldShowCustomControl({ value: "117", hasPresetMatch: false }),
    true,
  );
  assert.equal(
    shouldShowCustomControl({ value: "120", hasPresetMatch: true }),
    false,
  );
});
