const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/movie_preferences.js"),
  "utf8",
);

const dataKey = (attribute) =>
  attribute.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
const flushRequests = () => new Promise((resolve) => setImmediate(resolve));

// A small DOM model exercises the actual click handlers without browser packages.
class Element {
  constructor(root, tag = "div") {
    this.root = root;
    this.tag = tag;
    this.dataset = {};
    this.attributes = {};
    this.childNodes = [];
    this.listeners = {};
    this.hidden = false;
    this.disabled = false;
    this.textContent = "";
    this.classes = new Set();
    this.classList = {
      contains: (name) => this.classes.has(name),
      toggle: (name, active) =>
        active ? this.classes.add(name) : this.classes.delete(name),
    };
  }

  get isConnected() {
    return this === this.root.body || Boolean(this.parentNode?.isConnected);
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  appendChild(child) {
    return this.insertBefore(child, null);
  }

  insertBefore(child, next) {
    child.remove();
    const index = next ? this.childNodes.indexOf(next) : this.childNodes.length;
    assert.notEqual(index, -1);
    this.childNodes.splice(index, 0, child);
    child.parentNode = this;
    return child;
  }

  replaceChild(child, old) {
    this.insertBefore(child, old);
    old.remove();
  }

  remove() {
    if (!this.parentNode) return;
    const index = this.parentNode.childNodes.indexOf(this);
    this.parentNode.childNodes.splice(index, 1);
    this.parentNode = null;
  }

  contains(element) {
    return (
      element === this ||
      this.childNodes.some((child) => child.contains(element))
    );
  }

  matches(selector) {
    if (this.tag === "#comment") return false;
    const tag = selector.match(/^[a-z]+/)?.[0];
    if (tag && tag !== this.tag) return false;
    return Array.from(selector.matchAll(/\[([^=\]]+)(?:="([^"]*)")?\]/g)).every(
      ([, attribute, value]) => {
        const actual = attribute.startsWith("data-")
          ? this.dataset[dataKey(attribute)]
          : this.attributes[attribute];
        return (
          actual !== undefined && (value === undefined || actual === value)
        );
      },
    );
  }

  closest(selector) {
    return this.matches(selector)
      ? this
      : this.parentNode?.closest(selector) || null;
  }

  querySelectorAll(selector) {
    const selectors = selector
      .split(",")
      .map((part) => part.trim().split(/\s+/));
    const descendants = this.childNodes.flatMap((child) => [
      child,
      ...child.querySelectorAll("*"),
    ]);
    return descendants.filter((element) =>
      selectors.some((parts) => {
        if (!element.matches(parts.at(-1))) return false;
        let ancestor = element.parentNode;
        for (let index = parts.length - 2; index >= 0; index--) {
          while (ancestor && !ancestor.matches(parts[index])) {
            ancestor = ancestor.parentNode;
          }
          if (!ancestor) return false;
          ancestor = ancestor.parentNode;
        }
        return true;
      }),
    );
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  addEventListener(type, handler) {
    this.listeners[type] = handler;
  }

  focus() {
    this.root.activeElement = this;
  }
}

const makePage = ({ ids = [1, 2, 3], savedTotal = ids.length } = {}) => {
  const events = [];
  const requests = [];
  const responses = [];
  const root = {
    listeners: {},
    addEventListener(type, handler) {
      this.listeners[type] = handler;
    },
    dispatchEvent(event) {
      events.push(event);
    },
    createElement(tag) {
      return new Element(this, tag);
    },
    createComment() {
      return new Element(this, "#comment");
    },
    querySelector(selector) {
      return this.body.querySelector(selector);
    },
    querySelectorAll(selector) {
      return this.body.querySelectorAll(selector);
    },
  };
  root.body = root.createElement("body");
  root.body.classes.add("watchlist-page");
  root.activeElement = root.body;
  const view = root.body.appendChild(root.createElement("section"));
  view.dataset.watchlistView = "";
  view.dataset.watchlistSavedTotal = String(savedTotal);
  const addHook = (key, text = "") => {
    const element = view.appendChild(root.createElement("span"));
    element.dataset[key] = "";
    element.textContent = text;
    return element;
  };
  const total = addHook("watchlistTotal", String(savedTotal));
  const totalLabel = addHook("watchlistTotalLabel");
  const results = addHook("watchlistResults", String(ids.length));
  const resultLabel = addHook("watchlistResultLabel");
  const input = view.appendChild(root.createElement("input"));
  const grid = addHook("watchlistGrid");
  const empty = addHook("watchlistEmpty");
  const noResults = addHook("watchlistNoResults");
  const cards = new Map();
  ids.forEach((id) => {
    const card = grid.appendChild(root.createElement("article"));
    card.dataset = { movieCard: "", movieId: String(id), watchlist: "true" };
    ["like", "watchlist"].forEach((type) => {
      const button = card.appendChild(root.createElement("button"));
      button.dataset = {
        preferenceButton: "",
        preferenceType: type,
        movieId: String(id),
        movieTitle: `Movie ${id}`,
      };
      if (type === "watchlist") button.classes.add("is-active");
    });
    cards.set(id, card);
  });
  const context = {
    document: root,
    window: {},
    CustomEvent: class {
      constructor(type, options) {
        this.type = type;
        this.detail = options.detail;
      }
    },
    async fetch(url, options) {
      requests.push({ url, ...options });
      const response = responses.shift();
      if (response instanceof Error) throw response;
      if (response) return response;
      return {
        ok: true,
        json: async () => ({
          liked: false,
          watchlist: options.method === "POST",
        }),
      };
    },
  };
  vm.runInNewContext(script, context);
  const button = (id) =>
    cards.get(id).querySelector('[data-preference-type="watchlist"]');
  const click = (target) =>
    root.listeners.click({
      target,
      preventDefault() {},
      stopPropagation() {},
    });
  const undo = () => root.querySelector('[data-watchlist-undo-action="undo"]');
  const dismiss = () =>
    root.querySelector('[data-watchlist-undo-action="dismiss"]');
  const message = () =>
    root.querySelector("[data-watchlist-undo]").childNodes[0];
  const visibleIds = () =>
    grid
      .querySelectorAll("[data-movie-card]")
      .map((card) => card.dataset.movieId);
  return {
    root,
    cards,
    grid,
    empty,
    noResults,
    total,
    totalLabel,
    results,
    resultLabel,
    input,
    requests,
    responses,
    events,
    button,
    click,
    undo,
    dismiss,
    message,
    visibleIds,
    support: context.window.VaultMoviePreferencesSupport,
  };
};

test("Undo restores the original card position, controls, counts and keyboard focus", async () => {
  const page = makePage();
  const original = page.cards.get(2);
  page.button(2).focus();
  await page.click(page.button(2));

  assert.deepEqual(page.visibleIds(), ["1", "3"]);
  assert.equal(page.total.textContent, "2");
  assert.equal(page.results.textContent, "2");
  assert.equal(page.root.activeElement, page.undo());
  assert.equal(page.message().attributes.role, "status");
  assert.equal(page.undo().attributes["aria-label"], "Undo removal of Movie 2");
  await page.undo().listeners.click();

  assert.deepEqual(page.visibleIds(), ["1", "2", "3"]);
  assert.equal(page.cards.get(2), original);
  assert.equal(original.dataset.watchlist, "true");
  assert.equal(page.button(2).attributes["aria-pressed"], "true");
  assert.equal(page.button(2).disabled, false);
  assert.equal(page.total.textContent, "3");
  assert.equal(page.results.textContent, "3");
  assert.equal(page.root.activeElement, page.button(2));
  assert.deepEqual(
    page.requests.map(({ method }) => method),
    ["DELETE", "POST"],
  );
  assert.equal(page.events.length, 2);
  assert.equal(
    page.grid.childNodes.some((node) => node.tag === "#comment"),
    false,
  );
});

test("removing the last visible match preserves saved total and filtered-empty state", async () => {
  const page = makePage({ ids: [2], savedTotal: 5 });
  await page.click(page.button(2));
  assert.equal(page.total.textContent, "4");
  assert.equal(page.results.textContent, "0");
  assert.equal(page.grid.hidden, true);
  assert.equal(page.empty.hidden, true);
  assert.equal(page.noResults.hidden, false);

  await page.undo().listeners.click();
  assert.equal(page.total.textContent, "5");
  assert.equal(page.results.textContent, "1");
  assert.equal(page.resultLabel.textContent, "movie");
  assert.equal(page.grid.hidden, false);
  assert.equal(page.noResults.hidden, true);
});

test("Undo recovers the last saved movie from the true empty state", async () => {
  const page = makePage({ ids: [1] });
  await page.click(page.button(1));
  assert.equal(page.total.textContent, "0");
  assert.equal(page.empty.hidden, false);
  assert.equal(page.noResults.hidden, true);
  await page.undo().listeners.click();
  assert.equal(page.total.textContent, "1");
  assert.equal(page.totalLabel.textContent, "movie");
  assert.equal(page.empty.hidden, true);
});

test("failed removal preserves cards and counts and offers an accessible retry message", async () => {
  const page = makePage();
  page.responses.push({ ok: false });
  await page.click(page.button(2));
  assert.deepEqual(page.visibleIds(), ["1", "2", "3"]);
  assert.equal(page.total.textContent, "3");
  assert.equal(page.button(2).disabled, false);
  assert.equal(page.undo().hidden, true);
  assert.match(page.message().textContent, /Could not update your watchlist/);
  assert.equal(page.events.length, 0);
});

test("failed Undo remains available, keeps the card removed and succeeds on retry", async () => {
  const page = makePage();
  await page.click(page.button(2));
  page.undo().focus();
  page.responses.push(new Error("offline"));
  await page.undo().listeners.click();
  assert.deepEqual(page.visibleIds(), ["1", "3"]);
  assert.equal(page.total.textContent, "2");
  assert.equal(page.undo().disabled, false);
  assert.equal(page.undo().hidden, false);
  assert.equal(page.root.activeElement, page.undo());
  assert.match(page.message().textContent, /Try Undo again/);
  await page.undo().listeners.click();
  assert.deepEqual(page.visibleIds(), ["1", "2", "3"]);
  assert.equal(page.total.textContent, "3");
});

test("a second successful removal replaces only the pending Undo and clears old placeholders", async () => {
  const page = makePage();
  await page.click(page.button(1));
  await page.click(page.button(2));
  assert.equal(
    page.grid.childNodes.filter((node) => node.tag === "#comment").length,
    1,
  );
  assert.match(page.message().textContent, /Movie 2 removed/);
  assert.match(
    page.message().textContent,
    /until you dismiss it, remove another movie, or leave this page/,
  );
  await page.undo().listeners.click();
  assert.deepEqual(page.visibleIds(), ["2", "3"]);
  assert.equal(page.total.textContent, "2");
  assert.equal(
    page.grid.childNodes.some((node) => node.tag === "#comment"),
    false,
  );
});

test("a failed second removal keeps the previous movie's Undo available", async () => {
  const page = makePage();
  await page.click(page.button(1));
  page.responses.push({ ok: false });
  await page.click(page.button(2));
  assert.match(page.message().textContent, /still undo removal of Movie 1/);
  await page.undo().listeners.click();
  assert.deepEqual(page.visibleIds(), ["1", "2", "3"]);
});

test("double clicks and overlapping removals send only one mutation while busy", async () => {
  const page = makePage();
  let finish;
  page.responses.push({
    ok: true,
    json: () => new Promise((resolve) => (finish = resolve)),
  });
  const removal = page.click(page.button(1));
  await flushRequests();
  await page.click(page.button(1));
  await page.click(page.button(2));
  assert.equal(page.requests.length, 1);
  assert.equal(page.button(2).disabled, true);
  finish({ liked: false, watchlist: false });
  await removal;
  assert.equal(page.button(2).disabled, false);

  page.responses.push({
    ok: true,
    json: () => new Promise((resolve) => (finish = resolve)),
  });
  const undo = page.undo().listeners.click();
  await flushRequests();
  await page.undo().listeners.click();
  await page.click(page.button(2));
  assert.equal(page.requests.length, 2);
  assert.equal(page.dismiss().disabled, true);
  finish({ liked: false, watchlist: true });
  await undo;
  assert.deepEqual(page.visibleIds(), ["1", "2", "3"]);
  assert.equal(page.total.textContent, "3");
});

test("Dismiss finalizes Undo without a request or orphan placeholder, and moves keyboard focus", async () => {
  const page = makePage({ ids: [1] });
  await page.click(page.button(1));
  page.dismiss().focus();
  page.dismiss().listeners.click();
  assert.equal(page.root.querySelector("[data-watchlist-undo]").hidden, true);
  assert.equal(page.grid.childNodes.length, 0);
  assert.equal(page.root.activeElement, page.input);
  await page.support.undoWatchlistRemoval(page.root);
  assert.equal(page.requests.length, 1);
});

test("the persistent Undo has no timer and renders movie titles as text", async () => {
  const page = makePage();
  page.button(2).dataset.movieTitle = '<img src=x onerror="alert(1)">';
  await page.click(page.button(2));
  assert.match(page.message().textContent, /^<img src=x/);
  assert.equal(page.message().childNodes.length, 0);
  assert.equal(page.undo().hidden, false);
  // The VM intentionally provides no timer API: a timed Undo would fail this test.
});

test("malformed successful responses do not remove cards or change counts", async () => {
  const page = makePage();
  page.responses.push({ ok: true, json: async () => ({ watchlist: false }) });
  await page.click(page.button(2));
  assert.deepEqual(page.visibleIds(), ["1", "2", "3"]);
  assert.equal(page.total.textContent, "3");
  assert.equal(page.events.length, 0);
});

test("Undo does not steal focus from a filter entered while its request was pending", async () => {
  const page = makePage();
  await page.click(page.button(2));
  page.undo().focus();
  let finish;
  page.responses.push({
    ok: true,
    json: () => new Promise((resolve) => (finish = resolve)),
  });
  const undo = page.undo().listeners.click();
  await flushRequests();
  page.input.focus();
  finish({ liked: false, watchlist: true });
  await undo;
  assert.equal(page.root.activeElement, page.input);
});
