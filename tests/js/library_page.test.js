const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/library_page.js"),
  "utf8",
);

const loadSupport = ({
  href = "http://127.0.0.1:8000/ui/movies",
  stored,
} = {}) => {
  const window = {};
  const storage = new Map();
  if (stored) {
    Object.entries(stored).forEach(([key, value]) => storage.set(key, value));
  }
  const context = {
    FormData: class {
      constructor(form) {
        this.entries = form.entries || [];
      }

      forEach(callback) {
        this.entries.forEach(([key, value]) => callback(value, key));
      }
    },
    URL,
    URLSearchParams,
    document: {
      addEventListener() {},
    },
    window,
  };
  window.location = { href };
  window.scrollY = 1180;
  window.requestAnimationFrame = (callback) => callback();
  window.scrollTo = (_x, y) => {
    window.restoredScrollY = y;
  };
  window.sessionStorage = {
    getItem(key) {
      return storage.get(key) || null;
    },
    setItem(key, value) {
      storage.set(key, value);
    },
    removeItem(key) {
      storage.delete(key);
    },
  };
  vm.runInNewContext(script, context);
  return { support: window.VaultLibrarySupport, storage };
};

test("normalizes return snapshots to the exact result URL without a hash", () => {
  const { support } = loadSupport();

  assert.equal(
    support.normaliseResultUrl(
      "http://127.0.0.1:8000/ui/movies?genres=Comedy&page=2#results",
    ),
    "http://127.0.0.1:8000/ui/movies?genres=Comedy&page=2",
  );
});

test("saves the result URL, scroll offset, and focused movie for app Back", () => {
  const { support, storage } = loadSupport();

  support.saveReturnState(394);

  assert.deepEqual(JSON.parse(storage.get("movies:returnState")), {
    url: "http://127.0.0.1:8000/ui/movies",
    scrollY: 1180,
    movieId: "394",
  });
});

test("restores scroll and focus only for the saved result URL", () => {
  const stored = JSON.stringify({
    url: "http://127.0.0.1:8000/ui/movies?genres=Comedy",
    scrollY: 1180,
    movieId: "394",
  });
  let focused = false;
  const root = {
    querySelectorAll() {
      return [
        {
          dataset: { movieId: "394" },
          querySelector() {
            return {
              focus() {
                focused = true;
              },
            };
          },
        },
      ];
    },
  };
  const { support, storage } = loadSupport({
    href: "http://127.0.0.1:8000/ui/movies?genres=Comedy#results",
    stored: { "movies:returnState": stored },
  });

  support.restoreReturnState(root);

  assert.equal(storage.has("movies:returnState"), false);
  assert.equal(focused, true);
});

test("does not restore or consume a snapshot for a different result URL", () => {
  const stored = JSON.stringify({
    url: "http://127.0.0.1:8000/ui/movies?genres=Comedy",
    scrollY: 1180,
    movieId: "394",
  });
  const { support, storage } = loadSupport({
    href: "http://127.0.0.1:8000/ui/movies?genres=Drama",
    stored: { "movies:returnState": stored },
  });

  support.restoreReturnState({
    querySelectorAll() {
      return [];
    },
  });

  assert.equal(storage.get("movies:returnState"), stored);
});

test("ignores malformed return-state storage", () => {
  const { support, storage } = loadSupport({
    stored: { "movies:returnState": "{" },
  });

  assert.doesNotThrow(() =>
    support.restoreReturnState({
      querySelectorAll() {
        return [];
      },
    }),
  );
  assert.equal(storage.get("movies:returnState"), "{");
});

test("does not capture modified or new-tab detail clicks", () => {
  const { support } = loadSupport();
  const link = {
    target: "",
    hasAttribute() {
      return false;
    },
  };
  const baseEvent = {
    altKey: false,
    button: 0,
    ctrlKey: false,
    defaultPrevented: false,
    metaKey: false,
    shiftKey: false,
  };

  assert.equal(support.shouldCaptureReturnState(baseEvent, link), true);
  assert.equal(
    support.shouldCaptureReturnState({ ...baseEvent, metaKey: true }, link),
    false,
  );
  assert.equal(
    support.shouldCaptureReturnState(baseEvent, { ...link, target: "_blank" }),
    false,
  );
});

test("form URL builder carries the changed sort and resets pagination", () => {
  const { support } = loadSupport();
  const url = new URL(
    support.buildFormSubmitUrl(
      {
        getAttribute() {
          return "/ui/movies";
        },
        entries: [
          ["q", "Liar Liar"],
          ["order_by", "runtime_asc"],
          ["page", "1"],
          ["_filters", "1"],
        ],
      },
      "http://127.0.0.1:8000/ui/movies?view=grid",
    ),
  );

  assert.equal(url.searchParams.get("q"), "Liar Liar");
  assert.equal(url.searchParams.get("order_by"), "runtime_asc");
  assert.equal(url.searchParams.get("page"), "1");
  assert.equal(url.hash, "#results");
});

const loadDisabledPager = (pagerHref) => {
  let clickListener = null;
  const nativeNavigations = [];
  const pagerLink = {
    href: pagerHref,
    addEventListener(type, listener) {
      if (type === "click") clickListener = listener;
    },
    getAttribute(name) {
      return name === "aria-disabled" ? "true" : null;
    },
  };
  const shell = {
    dataset: {},
    classList: { add() {}, remove() {} },
    matches(selector) {
      return selector === "[data-results-shell]";
    },
    querySelector() {
      return null;
    },
    removeAttribute() {},
    setAttribute() {},
  };
  const document = {
    addEventListener() {},
    getElementById() {
      return null;
    },
    querySelector() {
      return null;
    },
    querySelectorAll(selector) {
      if (selector === "[data-results-pager] a") return [pagerLink];
      return [];
    },
  };
  const window = {
    addEventListener() {},
    location: { href: "http://127.0.0.1:8000/ui/movies" },
  };

  vm.runInNewContext(script, { document, URL, URLSearchParams, window });
  window.VaultLibrarySupport.initLibraryPage(shell);

  const clickPager = () => {
    const event = {
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
    };
    clickListener(event);
    if (!event.defaultPrevented) nativeNavigations.push(pagerLink.href);
    return event;
  };

  return {
    clickPager,
    nativeNavigations,
    shell,
  };
};

test("clearing a preset removes Hidden Gems and preserves other filters", () => {
  const { support } = loadSupport();
  const { buildClearFilterUrl } = support;
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
  const { support } = loadSupport();
  const { buildClearFilterUrl } = support;
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
  const { support } = loadSupport();
  const { buildClearFilterUrl } = support;
  const result = new URL(
    buildClearFilterUrl("http://127.0.0.1:8000/ui/movies", "preset"),
  );

  assert.equal(result.searchParams.has("preset"), false);
  assert.equal(result.searchParams.get("_filters"), "1");
  assert.equal(result.searchParams.get("page"), "1");
});

test("clear all removes filters while preserving view and sort", () => {
  const { support } = loadSupport();
  const { buildClearAllFiltersUrl } = support;
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
  const { support } = loadSupport();
  const { buildTableSortUrl } = support;
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
  const { support } = loadSupport();
  const { buildTableSortUrl } = support;
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

test("library request URLs mark filter state and default to the first page", () => {
  const { support } = loadSupport();
  const { buildLibraryRequestUrl } = support;
  const result = new URL(
    buildLibraryRequestUrl("http://127.0.0.1:8000/ui/movies?view=list"),
  );

  assert.equal(result.searchParams.get("view"), "list");
  assert.equal(result.searchParams.get("_filters"), "1");
  assert.equal(result.searchParams.get("page"), "1");
});

test("library request URLs preserve explicit pagination", () => {
  const { support } = loadSupport();
  const { buildLibraryRequestUrl } = support;
  const result = new URL(
    buildLibraryRequestUrl(
      "http://127.0.0.1:8000/ui/movies?view=grid&page=3&_filters=1",
    ),
  );

  assert.equal(result.searchParams.get("view"), "grid");
  assert.equal(result.searchParams.get("_filters"), "1");
  assert.equal(result.searchParams.get("page"), "3");
});

test("disabled Library page boundaries cancel DOM navigation", () => {
  const boundaries = [
    {
      label: "previous on the first page",
      pagerHref: "http://127.0.0.1:8000/ui/movies?page=1#results",
    },
    {
      label: "next on the last page",
      pagerHref: "http://127.0.0.1:8000/ui/movies?page=5#results",
    },
  ];

  boundaries.forEach(({ label, pagerHref }) => {
    const { clickPager, nativeNavigations, shell } =
      loadDisabledPager(pagerHref);

    const event = clickPager();

    assert.equal(shell.dataset.libraryInitialized, "true", label);
    assert.equal(event.defaultPrevented, true, label);
    assert.deepEqual(nativeNavigations, [], label);
  });
});

test("random pick params include the full selected filter set", () => {
  const { support } = loadSupport();
  const { buildPickParams } = support;
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
  const { support } = loadSupport();
  const { buildPickParams } = support;
  const params = buildPickParams({
    genres: "  ",
    moods: "",
    q: " Blade Runner ",
  });

  assert.deepEqual(Array.from(params.entries()), [["q", "Blade Runner"]]);
});

test("builds pending filter summary and counts each visible chip", () => {
  const { support } = loadSupport();
  const { buildPendingSummary, formatApplyLabel } = support;
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
  const { support } = loadSupport();
  const { emptyFilterState } = support;

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
  const { support } = loadSupport();
  const { formatPresetName, parseCsv } = support;

  assert.equal(formatPresetName("hidden-gems"), "Hidden Gems");
  assert.deepEqual(Array.from(parseCsv("Drama, Science Fiction, ")), [
    "Drama",
    "Science Fiction",
  ]);
});

test("shows custom controls only when selected or holding a non-preset value", () => {
  const { support } = loadSupport();
  const { shouldShowCustomControl } = support;

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
