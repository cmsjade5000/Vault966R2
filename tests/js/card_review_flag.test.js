const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/card_review_flag.js"),
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
  return window.VaultCardReviewFlagSupport;
};

test("uses a deliberate hold before revealing the review flag", () => {
  const support = loadSupport();

  assert.equal(support.HOLD_DELAY_MS, 550);
  assert.equal(support.MOVE_TOLERANCE_PX, 12);
});

test("cancels a hold when the finger moves far enough to scroll", () => {
  const { movedBeyondTolerance } = loadSupport();

  assert.equal(movedBeyondTolerance(10, 10, 16, 16), false);
  assert.equal(movedBeyondTolerance(10, 10, 23, 10), true);
});
