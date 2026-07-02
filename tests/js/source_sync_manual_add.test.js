const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/source_sync_manual_add.js"),
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
  return window.VaultSourceSyncManualAddSupport;
};

test("normalizes optional source sync manual add year", () => {
  const { normalizeYear } = loadSupport();

  assert.equal(normalizeYear("2026"), 2026);
  assert.equal(normalizeYear(""), null);
  assert.equal(normalizeYear("unknown"), null);
});

test("builds compact preview metadata summary", () => {
  const { buildPreviewSummary } = loadSupport();

  assert.equal(
    buildPreviewSummary({
      year: 1999,
      runtime: 136,
      genres: ["Science Fiction", "Action", "Adventure", "Drama"],
    }),
    "1999 • 136 min • Science Fiction, Action, Adventure",
  );
});
