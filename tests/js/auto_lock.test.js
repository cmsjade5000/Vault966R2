const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/auto_lock.js"),
  "utf8",
);

const loadSupport = () => {
  const windowListeners = new Map();
  const documentListeners = new Map();
  const body = {
    appendChild() {},
    getAttribute(name) {
      return name === "data-vault-auto-lock-ms" ? "1200000" : null;
    },
    hasAttribute(name) {
      return name === "data-vault-auto-lock";
    },
  };
  const document = {
    body,
    readyState: "loading",
    visibilityState: "visible",
    addEventListener(name, callback) {
      documentListeners.set(name, callback);
    },
    createElement() {
      return { submit() {} };
    },
  };
  const window = {
    addEventListener(name, callback) {
      windowListeners.set(name, callback);
    },
    clearTimeout() {},
    localStorage: {
      getItem() {
        return null;
      },
      removeItem() {},
      setItem() {},
    },
    setTimeout() {},
  };
  const context = {
    console,
    document,
    window,
  };
  vm.runInNewContext(script, context);
  return {
    document,
    documentListeners,
    support: window.VaultAutoLockSupport,
    window,
    windowListeners,
  };
};

test("uses a 20 minute default inactivity timeout", () => {
  const { support } = loadSupport();
  assert.equal(support.DEFAULT_TIMEOUT_MS, 20 * 60 * 1000);
});

test("locks when the inactivity deadline expires", () => {
  const { document, support, window } = loadSupport();
  let currentTime = 1000;
  let scheduled = null;
  let locked = 0;

  const controller = support.createController({
    documentLike: document,
    windowLike: window,
    storageLike: window.localStorage,
    now: () => currentTime,
    setTimer(callback, delay) {
      scheduled = { callback, delay };
      return 1;
    },
    clearTimer() {},
    lock() {
      locked += 1;
    },
  });

  assert.equal(controller.timeoutMs, 1200000);
  assert.equal(scheduled.delay, 1200000);

  currentTime += scheduled.delay;
  scheduled.callback();
  assert.equal(locked, 1);
});

test("activity resets the inactivity deadline", () => {
  const { document, support, window } = loadSupport();
  let currentTime = 5000;
  const delays = [];

  const controller = support.createController({
    documentLike: document,
    windowLike: window,
    storageLike: window.localStorage,
    now: () => currentTime,
    setTimer(callback, delay) {
      delays.push(delay);
      return delays.length;
    },
    clearTimer() {},
    lock() {},
  });

  currentTime += 300000;
  controller.markActivity();

  assert.equal(controller.getLastActivity(), currentTime);
  assert.equal(delays.at(-1), 1200000);
});

test("checks elapsed time when the page becomes visible again", () => {
  const { document, support, window } = loadSupport();
  let currentTime = 1000;
  let locked = 0;

  const controller = support.createController({
    documentLike: document,
    windowLike: window,
    storageLike: window.localStorage,
    now: () => currentTime,
    setTimer() {
      return 1;
    },
    clearTimer() {},
    lock() {
      locked += 1;
    },
  });

  currentTime += 1200001;
  controller.checkElapsed();
  assert.equal(locked, 1);
});
