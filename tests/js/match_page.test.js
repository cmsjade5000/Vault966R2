const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/match_page.js"),
  "utf8",
);

const loadSupport = () => {
  const window = {};
  const document = {
    addEventListener() {},
  };
  const context = {
    document,
    window,
  };
  vm.runInNewContext(script, context);
  return window.VaultMatchSupport;
};

test("counts selected answers from a query value", () => {
  const { answerCount } = loadSupport();

  assert.equal(answerCount("funny,short,older"), 3);
  assert.equal(answerCount(""), 0);
});

test("builds the next answer sequence", () => {
  const { nextAnswers } = loadSupport();

  assert.equal(nextAnswers(["funny", "short"], "older"), "funny,short,older");
  assert.equal(nextAnswers([], "scary"), "scary");
});
