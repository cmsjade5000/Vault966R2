const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/back_link.js"),
  "utf8",
);

const loadBackLink = () => {
  const events = [];
  const listeners = {};
  const timeoutDelays = [];
  let currentHref = "http://testserver/ui/movies/42";
  const link = {
    dataset: { vaultBusyMessage: "Returning to the Library…" },
    textContent: "← Back to results",
    addEventListener(type, listener) {
      listeners[type] = listener;
    },
    getAttribute(name) {
      return name === "href" ? "/ui/movies" : null;
    },
    setAttribute() {},
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
    cookie: "",
    referrer: "",
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
