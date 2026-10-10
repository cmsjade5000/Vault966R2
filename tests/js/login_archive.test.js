const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/login_archive.js"),
  "utf8",
);

const loadSupport = () => {
  const window = {
    setTimeout: () => 1,
    clearTimeout() {},
    matchMedia: () => ({ matches: false }),
    requestAnimationFrame(callback) {
      callback();
    },
  };
  const context = {
    AbortController,
    Image: class {},
    console,
    document: {
      addEventListener() {},
      readyState: "loading",
    },
    window,
  };
  vm.runInNewContext(script, context);
  return window.VaultLoginArchiveSupport;
};

test("uses a deliberate crossfade duration for poster replacements", () => {
  const support = loadSupport();

  assert.equal(support.IMAGE_FADE_MS, 1300);
});

test("marks a decoded poster as loaded before it becomes visible", async () => {
  const support = loadSupport();
  const classes = [];
  const image = {
    classList: {
      add(value) {
        classes.push(value);
      },
      remove() {},
    },
    complete: true,
    decode: async () => {},
    naturalWidth: 342,
  };

  assert.equal(await support.markImageReady(image), true);
  assert.deepEqual(classes, ["is-pending", "is-loaded"]);
});

test("a cached failed image uses the quiet fallback instead of remaining pending", async () => {
  const support = loadSupport();
  const added = [];
  const removed = [];
  const image = {
    complete: true,
    naturalWidth: 0,
    classList: {
      add(value) {
        added.push(value);
      },
      remove(value) {
        removed.push(value);
      },
    },
  };
  assert.equal(await support.markImageReady(image), false);
  assert.deepEqual(added, ["is-pending", "is-unavailable"]);
  assert.deepEqual(removed, ["is-pending"]);
});

test("failed loads clear handlers and timers without replacing the current poster", async () => {
  const callbacks = new Map();
  const removed = [];
  const timers = [];
  const window = {
    matchMedia: () => ({ matches: false }),
    setTimeout(fn, delay) {
      timers.push({ fn, delay });
      return 1;
    },
    clearTimeout(id) {
      removed.push(id);
    },
    requestAnimationFrame(fn) {
      fn();
    },
  };
  const context = {
    AbortController,
    Image: class {},
    console,
    document: { addEventListener() {}, readyState: "loading" },
    window,
  };
  vm.runInNewContext(script, context);
  const image = {
    complete: false,
    naturalWidth: 0,
    classList: { add() {}, remove() {} },
    addEventListener(name, fn) {
      callbacks.set(name, fn);
    },
    removeEventListener(name) {
      callbacks.delete(name);
    },
  };
  const pending = window.VaultLoginArchiveSupport.markImageReady(image);
  assert.equal(timers[0].delay, 8000);
  timers[0].fn();
  assert.equal(await pending, false);
  assert.equal(callbacks.size, 0);
  assert.deepEqual(removed, [1]);
});

const initRotation = ({
  hidden = false,
  reduced = false,
  decode,
  storageDenied = false,
  slotCount = 1,
  visibleCount = slotCount,
  poolCount = 2,
} = {}) => {
  const timers = [];
  const events = new Map();
  const storage = new Map();
  let preloads = 0;
  const classes = { add() {}, remove() {}, contains: () => false };
  let image = { complete: true, naturalWidth: 342, classList: classes };
  const slot = {
    querySelector: () => image,
    querySelectorAll: () => [],
    replaceChild(next) {
      image = next;
    },
    classList: classes,
  };
  const slots = Array.from({ length: slotCount }, () => ({ ...slot }));
  const origin = "http://localhost";
  const context = {
    AbortController,
    Image: class {
      constructor() {
        preloads += 1;
        this.complete = true;
        this.naturalWidth = 342;
        this.classList = classes;
        this.decode = decode;
      }
      setAttribute() {}
    },
    console,
    document: {
      readyState: "complete",
      hidden,
      body: { classList: classes },
      getElementById: () => ({
        textContent: JSON.stringify({
          posters: Array.from(
            { length: poolCount },
            (_, index) =>
              origin +
              "/static/img/login-posters/poster-" +
              (index + 1) +
              ".jpg",
          ),
        }),
      }),
      querySelectorAll: () => slots,
      addEventListener() {},
    },
    window: {
      location: { origin },
      matchMedia: () => ({ matches: reduced }),
      requestAnimationFrame(fn) {
        fn();
      },
      setTimeout(fn, delay) {
        fn.delay = delay;
        timers.push(fn);
        return timers.length;
      },
      clearTimeout() {},
      addEventListener(name, fn) {
        events.set(name, fn);
      },
      sessionStorage: {
        getItem: (key) => {
          if (storageDenied) throw new Error("Storage denied");
          return storage.get(key) || null;
        },
        setItem: (key, value) => {
          if (storageDenied) throw new Error("Storage denied");
          storage.set(key, value);
        },
      },
      getComputedStyle: (slot) => ({
        display: slots.indexOf(slot) < visibleCount ? "block" : "none",
      }),
    },
  };
  vm.runInNewContext(script, context);
  return {
    timers,
    events,
    storage,
    image: () => image,
    preloads: () => preloads,
  };
};

test("reduced motion gets a fresh static visit without scheduling rotation", async () => {
  const state = initRotation({ reduced: true });
  await new Promise(setImmediate);
  assert.equal(state.timers.filter((fn) => fn.delay >= 12000).length, 0);
  assert.equal(state.preloads(), 1);
});

test("a hidden tab does not preload replacement posters", () => {
  const state = initRotation({ hidden: true });
  state.timers.find((fn) => fn.delay >= 12000)();
  assert.equal(state.preloads(), 0);
});

test("successive visits select fresh posters before reusing the prior lineup", () => {
  const support = loadSupport();
  const urls = Array.from({ length: 36 }, (_, index) => `poster-${index}`);
  const first = Array.from(support.selectLineup(urls, 12));
  const second = Array.from(support.selectLineup(urls, 12, first));
  assert.equal(new Set(second).size, 12);
  assert.ok(second.every((url) => !first.includes(url)));
  const third = Array.from(support.selectLineup(urls, 12, second));
  assert.ok(third.every((url) => !second.includes(url)));
});

test("small pools avoid immediately repeating the same lineup order", () => {
  const support = loadSupport();
  const previous = ["a", "b"];
  for (let visit = 0; visit < 20; visit += 1) {
    assert.notDeepEqual(
      Array.from(support.selectLineup(previous, 2, previous)),
      previous,
    );
  }
});

test("a persisted pageshow selects a new lineup and restarts rotation", async () => {
  const state = initRotation();
  await new Promise(setImmediate);
  const first = state.image().src;
  state.events.get("pagehide")();
  state.events.get("pageshow")({ persisted: true });
  await new Promise(setImmediate);
  assert.notEqual(state.image().src, first);
  assert.equal(state.preloads(), 2);
  assert.equal(state.timers.filter((fn) => fn.delay >= 12000).length, 2);
});

test("ordinary pageshow does not replace the lineup twice", async () => {
  const state = initRotation();
  state.events.get("pageshow")({ persisted: false });
  await new Promise(setImmediate);
  assert.equal(state.preloads(), 1);
});

test("visit replacement preserves initial markup until the poster is decoded", async () => {
  let release;
  const decode = () =>
    new Promise((resolve) => {
      release = resolve;
    });
  const state = initRotation({ decode });
  const original = state.image();
  await new Promise(setImmediate);
  assert.equal(state.image(), original);
  release();
  await new Promise(setImmediate);
  assert.notEqual(state.image(), original);
});

test("pagehide cancels an in-flight visit replacement", async () => {
  let release;
  const state = initRotation({
    decode: () =>
      new Promise((resolve) => {
        release = resolve;
      }),
  });
  const original = state.image();
  state.events.get("pagehide")();
  release();
  await new Promise(setImmediate);
  assert.equal(state.image(), original);
});

test("reduced-motion BFCache restores select a fresh static lineup", async () => {
  const state = initRotation({ reduced: true });
  await new Promise(setImmediate);
  const first = state.image().src;
  state.events.get("pagehide")();
  state.events.get("pageshow")({ persisted: true });
  await new Promise(setImmediate);
  assert.notEqual(state.image().src, first);
  assert.equal(state.timers.filter((fn) => fn.delay >= 12000).length, 0);
});

test("mobile visits select six distinct fresh posters from the 36-poster pool", () => {
  const support = loadSupport();
  const urls = Array.from({ length: 36 }, (_, index) => `poster-${index}`);
  const previous = urls.slice(0, 6);
  const next = Array.from(support.selectLineup(urls, 6, previous));
  assert.equal(next.length, 6);
  assert.equal(new Set(next).size, 6);
  assert.ok(next.every((url) => !previous.includes(url)));
});

test("storage denial preserves BFCache variety using the in-memory lineup", async () => {
  const state = initRotation({ storageDenied: true, reduced: true });
  await new Promise(setImmediate);
  const first = state.image().src;
  state.events.get("pagehide")();
  state.events.get("pageshow")({ persisted: true });
  await new Promise(setImmediate);
  assert.notEqual(state.image().src, first);
  assert.equal(state.storage.size, 0);
});

test("aborting a pending decode settles readiness and clears its timeout", async () => {
  const callbacks = [];
  const cleared = [];
  const window = {
    setTimeout(fn) {
      callbacks.push(fn);
      return 9;
    },
    clearTimeout(id) {
      cleared.push(id);
    },
  };
  vm.runInNewContext(script, {
    window,
    console,
    Image: class {},
    document: { readyState: "loading", addEventListener() {} },
  });
  const controller = new AbortController();
  const image = {
    complete: true,
    naturalWidth: 342,
    classList: { add() {}, remove() {} },
    decode: () => new Promise(() => {}),
  };
  const pending = window.VaultLoginArchiveSupport.markImageReady(
    image,
    controller.signal,
  );
  controller.abort();
  assert.equal(await pending, false);
  assert.deepEqual(cleared, [9]);
});

test("mobile initialization preloads only six visible slots from the full pool", async () => {
  const state = initRotation({
    slotCount: 12,
    visibleCount: 6,
    poolCount: 36,
    reduced: true,
  });
  await new Promise(setImmediate);
  assert.equal(state.preloads(), 6);
  const lineup = JSON.parse([...state.storage.values()][0]);
  assert.equal(lineup.length, 6);
  assert.equal(new Set(lineup).size, 6);
});
