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
  const window = {
    matchMedia: () => ({ matches: false }),
  };
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

test("builds a show-picks query for partial preferences", () => {
  const { showPicksQuery } = loadSupport();

  assert.equal(
    showPicksQuery(["funny", "any_energy"]),
    "answers=funny%2Cany_energy&show=1",
  );
  assert.equal(showPicksQuery([]), "show=1");
});

test("formats remaining count labels", () => {
  const { countLabel } = loadSupport();

  assert.equal(countLabel(42), "42 left");
  assert.equal(countLabel("1"), "1 left");
  assert.equal(countLabel("sideways"), "0 left");
});

test("exposes reduced motion preference", () => {
  const window = {
    matchMedia: () => ({ matches: true }),
  };
  const document = {
    addEventListener() {},
  };
  const context = {
    document,
    window,
  };

  vm.runInNewContext(script, context);

  assert.equal(window.VaultMatchSupport.prefersReducedMotion(), true);
});

const loadInteractions = () => {
  const classes = new Set();
  const attributes = new Map();
  const listeners = new Map();
  const windowListeners = new Map();
  const link = {
    classList: {
      add: (value) => classes.add(value),
      remove: (value) => classes.delete(value),
    },
    setAttribute: (name, value) => attributes.set(name, value),
    removeAttribute: (name) => attributes.delete(name),
  };
  const page = {
    classList: {
      add: (value) => classes.add(value),
      remove: (value) => classes.delete(value),
    },
    querySelectorAll: () => [link],
  };
  const window = {
    matchMedia: () => ({ matches: false }),
    addEventListener: (name, callback) => windowListeners.set(name, callback),
    setVaultBusy() {},
  };
  const document = {
    querySelector: () => page,
    addEventListener: (name, callback) => listeners.set(name, callback),
  };
  vm.runInNewContext(script, { document, window });
  const click = (extra = {}) => {
    const event = {
      target: { closest: () => link },
      button: 0,
      prevented: 0,
      preventDefault() {
        this.prevented += 1;
      },
      ...extra,
    };
    listeners.get("click")(event);
    return event;
  };
  return { classes, attributes, windowListeners, click };
};

test("Picker navigation blocks repeated clicks until the next pageshow", () => {
  const { click, classes, attributes, windowListeners } = loadInteractions();
  assert.equal(click().prevented, 0);
  assert.equal(classes.has("is-loading"), true);
  assert.equal(attributes.get("aria-busy"), "true");
  assert.equal(click().prevented, 1);
  windowListeners.get("pageshow")({ persisted: true });
  assert.equal(classes.has("is-loading"), false);
  assert.equal(classes.has("is-pressed"), false);
  assert.equal(attributes.has("aria-busy"), false);
  assert.equal(click().prevented, 0);
});

for (const extra of [
  { metaKey: true },
  { ctrlKey: true },
  { shiftKey: true },
  { altKey: true },
  { button: 1 },
  { defaultPrevented: true },
]) {
  test(`Picker preserves native alternate navigation ${JSON.stringify(extra)}`, () => {
    const { click, classes } = loadInteractions();
    assert.equal(click(extra).prevented, 0);
    assert.equal(classes.has("is-loading"), false);
  });
}
