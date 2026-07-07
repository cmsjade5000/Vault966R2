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

test("clearing a cookie-backed preset marks the URL as authoritative", () => {
  const { buildClearFilterUrl } = loadSupport();
  const result = new URL(
    buildClearFilterUrl("http://127.0.0.1:8000/ui/movies", "preset"),
  );

  assert.equal(result.searchParams.has("preset"), false);
  assert.equal(result.searchParams.get("_filters"), "1");
  assert.equal(result.searchParams.get("page"), "1");
});

test("clear all removes filters while preserving view and sort", () => {
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
  assert.equal(result.searchParams.get("order_by"), "title");
  assert.equal(result.searchParams.get("_filters"), "1");
  assert.equal(result.searchParams.get("page"), "1");
});

test("table sort toggles active ascending column to descending", () => {
  const { buildTableSortUrl } = loadSupport();
  const result = new URL(
    buildTableSortUrl(
      "http://127.0.0.1:8000/ui/movies?view=list&order_by=title_asc&page=4&genres=Drama",
      {
        asc: "title_asc",
        currentOrder: "title_asc",
        desc: "title_desc",
      },
    ),
  );

  assert.equal(result.searchParams.get("order_by"), "title_desc");
  assert.equal(result.searchParams.get("view"), "list");
  assert.equal(result.searchParams.get("genres"), "Drama");
  assert.equal(result.searchParams.get("_filters"), "1");
  assert.equal(result.searchParams.get("page"), "1");
});

test("table sort preserves form-backed filters and switches inactive column to ascending", () => {
  const { buildTableSortUrl } = loadSupport();
  const result = new URL(
    buildTableSortUrl("http://127.0.0.1:8000/ui/movies?view=list&page=3", {
      asc: "id_asc",
      currentOrder: "title_desc",
      desc: "id_desc",
      values: {
        genres: "Drama",
        moods: "Moody",
        q: "alien",
        runtime_max: "120",
        view: "list",
        year_min: "1990",
      },
    }),
  );

  assert.equal(result.searchParams.get("order_by"), "id_asc");
  assert.equal(result.searchParams.get("q"), "alien");
  assert.equal(result.searchParams.get("genres"), "Drama");
  assert.equal(result.searchParams.get("moods"), "Moody");
  assert.equal(result.searchParams.get("runtime_max"), "120");
  assert.equal(result.searchParams.get("year_min"), "1990");
  assert.equal(result.searchParams.get("view"), "list");
  assert.equal(result.searchParams.get("page"), "1");
});

test("random pick params include the full selected filter set", () => {
  const { buildPickParams } = loadSupport();
  const params = buildPickParams({
    genres: "Sci-Fi, Action",
    moods: "High-energy, Mind-bending",
    q: "Matrix",
    runtime_max: "140",
    runtime_min: "120",
    year_max: "2000",
    year_min: "1990",
  });

  assert.equal(params.get("q"), "Matrix");
  assert.equal(params.get("genres"), "Sci-Fi, Action");
  assert.equal(params.get("moods"), "High-energy, Mind-bending");
  assert.equal(params.get("year_min"), "1990");
  assert.equal(params.get("year_max"), "2000");
  assert.equal(params.get("runtime_min"), "120");
  assert.equal(params.get("runtime_max"), "140");
  assert.equal(params.has("genre"), false);
  assert.equal(params.has("mood"), false);
});

test("random pick params omit blank filters", () => {
  const { buildPickParams } = loadSupport();
  const params = buildPickParams({
    genres: "  ",
    moods: "",
    q: " Blade Runner ",
  });

  assert.deepEqual(Array.from(params.entries()), [["q", "Blade Runner"]]);
});

test("builds pending filter summary and counts each visible chip", () => {
  const { buildPendingSummary, formatApplyLabel } = loadSupport();
  const summary = buildPendingSummary({
    genres: ["Drama", "Science Fiction"],
    moods: ["Atmospheric", "Thoughtful"],
    presetName: "Thoughtful Dramas",
    runtimeMax: "120",
    yearLabel: "1990s",
  });

  assert.deepEqual(JSON.parse(JSON.stringify(summary)), [
    { kind: "preset", label: "Fliclist: Thoughtful Dramas" },
    { kind: "genre", label: "Drama" },
    { kind: "genre", label: "Science Fiction" },
    { kind: "mood", label: "Atmospheric" },
    { kind: "mood", label: "Thoughtful" },
    { kind: "year", label: "1990s" },
    { kind: "runtime", label: "≤ 120 min" },
  ]);
  assert.equal(formatApplyLabel(summary.length), "Show results · 7 filters");
  assert.equal(formatApplyLabel(1), "Show results · 1 filter");
  assert.equal(formatApplyLabel(0), "Show results");
});

test("reset state clears only filter values", () => {
  const { emptyFilterState } = loadSupport();

  assert.deepEqual(JSON.parse(JSON.stringify(emptyFilterState())), {
    genres: [],
    moods: [],
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
