const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/install_prompt.js"),
  "utf8",
);

const loadSupport = () => {
  const window = {
    navigator: {},
    location: { pathname: "/ui/movies" },
    matchMedia: () => ({ matches: false }),
  };
  const context = {
    window,
    document: { readyState: "loading", addEventListener() {} },
    localStorage: { getItem() {}, setItem() {} },
  };
  vm.runInNewContext(script, context);
  return window.VaultInstallSupport;
};

test("detects modern iPadOS desktop-class user agents", () => {
  const { isIosDevice } = loadSupport();
  assert.equal(
    isIosDevice({
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 Version/15.6.8 Safari/605.1.15",
      platform: "MacIntel",
      maxTouchPoints: 5,
    }),
    true,
  );
});

test("detects traditional iPad user agents", () => {
  const { isIosDevice } = loadSupport();
  assert.equal(
    isIosDevice({
      userAgent: "Mozilla/5.0 (iPad; CPU OS 12_5 like Mac OS X)",
      platform: "iPad",
      maxTouchPoints: 5,
    }),
    true,
  );
});

test("does not treat desktop Safari as iPadOS", () => {
  const { isIosDevice } = loadSupport();
  assert.equal(
    isIosDevice({
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15",
      platform: "MacIntel",
      maxTouchPoints: 0,
    }),
    false,
  );
});

test("detects standalone mode from either Safari signal", () => {
  const { isStandaloneMode } = loadSupport();
  assert.equal(
    isStandaloneMode({
      navigatorLike: { standalone: true },
      matchMediaLike: () => ({ matches: false }),
    }),
    true,
  );
  assert.equal(
    isStandaloneMode({
      navigatorLike: {},
      matchMediaLike: () => ({ matches: true }),
    }),
    true,
  );
});
