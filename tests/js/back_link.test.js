const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/back_link.js"),
  "utf8",
);

const loadBackLink = ({
  backContext = "",
  cookie = "",
  href = "/ui/movies",
  referrer = "",
} = {}) => {
  const events = [];
  const listeners = {};
  const timeoutDelays = [];
  let currentHref = "http://testserver/ui/movies/42";
  let linkHref = href;
  const link = {
    dataset: {
      backContext,
      vaultBusyMessage: "Returning to the Library…",
    },
    textContent: "← Back to results",
    addEventListener(type, listener) {
      listeners[type] = listener;
    },
    getAttribute(name) {
      return name === "href" ? linkHref : null;
    },
    setAttribute(name, value) {
      if (name === "href") linkHref = value;
    },
  };
  const window = {
    location: {
      get href() {
        return currentHref;
      },
      set href(value) {
        currentHref = value;
        events.push({ type: "navigate", value });
      },
      origin: "http://testserver",
    },
    setTimeout(_callback, delay) {
      timeoutDelays.push(delay);
      return 1;
    },
    setVaultBusy(message, options) {
      events.push({ message, options, type: "busy" });
    },
  };
  const document = {
    cookie,
    referrer,
    querySelector(selector) {
      return selector === "[data-back-link]" ? link : null;
    },
  };

  vm.runInNewContext(script, { console, document, URL, window });

  return {
    click() {
      const event = {
        defaultPrevented: false,
        preventDefault() {
          this.defaultPrevented = true;
        },
      };
      listeners.click(event);
      return event;
    },
    events,
    getCurrentHref() {
      return currentHref;
    },
    link,
    timeoutDelays,
  };
};

test("back links set busy state and navigate immediately", () => {
  const { click, events, getCurrentHref, timeoutDelays } = loadBackLink();

  const event = click();

  assert.equal(event.defaultPrevented, true);
  assert.deepEqual(JSON.parse(JSON.stringify(events)), [
    {
      message: "Returning to the Library…",
      options: { delay: 0 },
      type: "busy",
    },
    {
      type: "navigate",
      value: "http://testserver/ui/movies",
    },
  ]);
  assert.equal(getCurrentHref(), "http://testserver/ui/movies");
  assert.deepEqual(timeoutDelays, []);
});

test("explicit Picker context preserves answer and reroll state", () => {
  const { click, getCurrentHref, link } = loadBackLink({
    backContext: "explicit",
    href: "/ui/match?answers=cozy,low,short&reroll=2",
  });

  assert.equal(link.textContent, "← Back to Picker");
  assert.equal(link.dataset.vaultBusyMessage, "Returning to the Picker…");

  click();

  assert.equal(
    getCurrentHref(),
    "http://testserver/ui/match?answers=cozy,low,short&reroll=2",
  );
});

test("same-origin Discover referrer returns to Discover instead of Library", () => {
  const { click, getCurrentHref, link } = loadBackLink({
    referrer: "http://testserver/ui/discover?rail=flic#shortlist",
  });

  assert.equal(link.textContent, "← Back to Discover");
  assert.equal(link.dataset.backContext, "referrer");

  click();

  assert.equal(
    getCurrentHref(),
    "http://testserver/ui/discover?rail=flic#shortlist",
  );
});

test("explicit Library context wins over stale persisted filters", () => {
  const cookieValue = encodeURIComponent(
    JSON.stringify({ q: "stale", page: 9, view: "grid" }),
  );
  const { click, getCurrentHref } = loadBackLink({
    backContext: "explicit",
    cookie: `movies:lastFilters=${cookieValue}`,
    href: "/ui/movies?q=current&page=2&view=list#results",
  });

  click();

  assert.equal(
    getCurrentHref(),
    "http://testserver/ui/movies?q=current&page=2&view=list#results",
  );
});

test("cross-origin referrers cannot become return targets", () => {
  const { click, getCurrentHref, link } = loadBackLink({
    referrer: "https://evil.test/ui/watchlist",
  });

  assert.equal(link.textContent, "← Back to results");
  click();
  assert.equal(getCurrentHref(), "http://testserver/ui/movies");
});
