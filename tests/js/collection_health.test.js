const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/collection_health.js"),
  "utf8",
);

const loadSupport = () => {
  const window = {
    clearTimeout() {},
    setTimeout() {},
  };
  const document = { addEventListener() {} };
  vm.runInNewContext(script, { console, document, fetch: () => {}, window });
  return window.VaultCollectionHealthSupport;
};

test("maintenance controls preserve busy and cancellation state", () => {
  const { shouldDisableCancelButton, shouldDisableUpdateButton } =
    loadSupport();
  const readyButton = { dataset: { previewBlocked: "false" } };
  const blockedButton = { dataset: { previewBlocked: "true" } };

  assert.equal(shouldDisableUpdateButton(readyButton, true), true);
  assert.equal(shouldDisableUpdateButton(readyButton, false), false);
  assert.equal(shouldDisableUpdateButton(blockedButton, false), true);
  assert.equal(shouldDisableCancelButton(true, false), true);
  assert.equal(shouldDisableCancelButton(true, true), false);
  assert.equal(shouldDisableCancelButton(false, false), true);
  assert.equal(
    shouldDisableCancelButton(
      true,
      !{ cancel_requested: true }.cancel_requested,
    ),
    true,
  );
});

test("maintenance polling is single-flight and ignores a stopped response", async () => {
  const { createSingleFlightPoller } = loadSupport();
  const scheduled = [];
  const cancelled = [];
  const responses = [];
  let finishes = 0;
  const poller = createSingleFlightPoller({
    cancel: (handle) => cancelled.push(handle),
    delay: 25,
    maxAttempts: 3,
    onFinish: () => {
      finishes += 1;
    },
    poll: () =>
      new Promise((resolve) => {
        responses.push(resolve);
      }),
    schedule: (callback) => {
      const handle = { callback };
      scheduled.push(handle);
      return handle;
    },
  });

  poller.start();
  const first = scheduled.shift();
  const firstRun = first.callback();
  assert.equal(scheduled.length, 0);

  poller.start();
  assert.deepEqual(cancelled, [first]);
  assert.equal(scheduled.length, 1);

  responses.shift()({ state: "success" });
  await firstRun;
  assert.equal(finishes, 0);
  assert.equal(scheduled.length, 1);

  const secondRun = scheduled.shift().callback();
  responses.shift()({ state: "running" });
  await secondRun;
  assert.equal(finishes, 0);
  assert.equal(scheduled.length, 1);
});

test("max-attempt polling leaves a running cancel request under rendered-state control", async () => {
  const { createSingleFlightPoller } = loadSupport();
  const scheduled = [];
  const finishedPayloads = [];
  const poller = createSingleFlightPoller({
    cancel() {},
    maxAttempts: 1,
    onFinish: (payload) => finishedPayloads.push(payload),
    poll: async () => ({ state: "running", cancel_requested: true }),
    schedule: (callback) => {
      scheduled.push(callback);
      return callback;
    },
  });

  poller.start();
  await scheduled.shift()();

  assert.equal(scheduled.length, 0);
  assert.deepEqual(JSON.parse(JSON.stringify(finishedPayloads)), [
    { state: "running", cancel_requested: true },
  ]);
});
