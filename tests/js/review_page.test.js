const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/review_page.js"),
  "utf8",
);

const loadSupport = () => {
  const window = {};
  class FormDataStub {
    constructor(form) {
      this.form = form;
    }

    get(name) {
      return this.form.values[name] ?? null;
    }
  }
  const context = {
    document: {
      addEventListener() {},
      querySelectorAll() {
        return [];
      },
    },
    FormData: FormDataStub,
    window,
  };
  vm.runInNewContext(script, context);
  return window.VaultReviewPageSupport;
};

const plain = (value) => JSON.parse(JSON.stringify(value));

test("OMDb candidates can be applied with only an IMDb ID", () => {
  const { buildApplyPayload, canApplyCandidate, selectionSource } =
    loadSupport();
  const search = { title: "Possession", year: 1981 };
  const candidate = {
    imdb_id: "tt0082933",
    source: "omdb",
    tmdb_id: null,
  };

  assert.equal(canApplyCandidate(candidate), true);
  assert.equal(selectionSource(candidate), "omdb");
  assert.deepEqual(plain(buildApplyPayload(search, candidate)), {
    imdb_id: "tt0082933",
    source: "omdb",
    title: "Possession",
    tmdb_id: null,
    year: 1981,
  });
});

test("TMDB candidates still require a TMDB ID", () => {
  const { canApplyCandidate } = loadSupport();

  assert.equal(
    canApplyCandidate({ imdb_id: "tt0082933", source: "tmdb" }),
    false,
  );
  assert.equal(canApplyCandidate({ source: "tmdb", tmdb_id: 500 }), true);
});

test("flag match search validates title and optional year", () => {
  const { parseSearchForm } = loadSupport();

  assert.deepEqual(
    plain(parseSearchForm({ values: { title: "  Alien  ", year: "1979" } })),
    {
      key: "Alien\n1979",
      title: "Alien",
      year: 1979,
    },
  );
  assert.deepEqual(
    plain(parseSearchForm({ values: { title: "Alien", year: "" } })),
    {
      key: "Alien\n",
      title: "Alien",
      year: null,
    },
  );
  assert.throws(
    () => parseSearchForm({ values: { title: "", year: "" } }),
    /Enter a title/,
  );
  assert.throws(
    () => parseSearchForm({ values: { title: "Alien", year: "1700" } }),
    /Year must be between/,
  );
});
