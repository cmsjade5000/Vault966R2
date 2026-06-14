const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/movie_detail_edit.js"),
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
  return window.VaultMovieDetailEditSupport;
};

test("builds a minimal update payload", () => {
  const { buildMovieUpdate } = loadSupport();
  const payload = buildMovieUpdate(
    {
      title: "Alien",
      year: 1979,
      runtime: 117,
      plot: "Original",
      poster_url: "",
      genres: ["Horror", "Science Fiction"],
    },
    {
      title: "Alien",
      year: "1979",
      runtime: "116",
      plot: "Updated",
      poster_url: "",
      genres: "science fiction, Horror",
      resolve_flag: true,
    },
  );

  assert.deepEqual(JSON.parse(JSON.stringify(payload)), {
    runtime: 116,
    plot: "Updated",
    resolve_flag: true,
  });
});

test("rejects an empty title and normalizes genre input", () => {
  const { buildMovieUpdate, parseGenresInput } = loadSupport();

  assert.deepEqual(Array.from(parseGenresInput("Drama,  Comedy, ")), [
    "Drama",
    "Comedy",
  ]);
  assert.throws(
    () =>
      buildMovieUpdate(
        { title: "Alien", genres: [] },
        {
          title: " ",
          year: "",
          runtime: "",
          plot: "",
          poster_url: "",
          genres: "",
          resolve_flag: false,
        },
      ),
    /Title cannot be empty/,
  );
});
