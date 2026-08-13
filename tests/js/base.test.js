const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/base.js"),
  "utf8",
);

const makeClassList = (initial = []) => {
  const classes = new Set(initial);
  return {
    add(name) {
      classes.add(name);
    },
    contains(name) {
      return classes.has(name);
    },
    toggle(name, force) {
      const next = force ?? !classes.has(name);
      if (next) {
        classes.add(name);
      } else {
        classes.delete(name);
      }
      return next;
    },
  };
};

const makeNavToggle = () => {
  const listeners = {};
  return {
    attributes: {},
    addEventListener(type, listener) {
      listeners[type] = listener;
    },
    click() {
      listeners.click?.({});
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
  };
};

const makeAnchor = ({
  backLink = false,
  download = false,
  href = "http://testserver/ui/movies?page=2",
  target = "",
} = {}) => ({
  dataset: {},
  href,
  target,
  hasAttribute(name) {
    return (
      (name === "data-back-link" && backLink) ||
      (name === "download" && download)
    );
  },
});

const makeAnchorClick = (link, overrides = {}) => ({
  altKey: false,
  button: 0,
  ctrlKey: false,
  defaultPrevented: false,
  metaKey: false,
  shiftKey: false,
  target: {
    closest(selector) {
      return selector === "a[href]" ? link : null;
    },
  },
  preventDefault() {
    this.defaultPrevented = true;
  },
  ...overrides,
});

const loadBase = ({ runScheduled = true, withNav = false } = {}) => {
  const documentListeners = {};
  const assignedUrls = [];
  const timeoutDelays = [];
  const body = {
    attributes: {},
    classList: { add() {} },
    removeAttribute(name) {
      delete this.attributes[name];
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
  };
  const messageTarget = { textContent: "" };
  const indicator = {
    attributes: { hidden: "" },
    querySelector(selector) {
      return selector === "[data-vault-busy-message]" ? messageTarget : null;
    },
    removeAttribute(name) {
      delete this.attributes[name];
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
  };
  const navMenu = withNav ? { classList: makeClassList() } : null;
  const navToggle = withNav ? makeNavToggle() : null;
  const document = {
    body,
    readyState: "complete",
    addEventListener(type, listener) {
      documentListeners[type] = listener;
    },
    getElementById() {
      return null;
    },
    querySelector(selector) {
      if (selector === "[data-vault-busy]") return indicator;
      if (selector === "[data-nav-menu]") return navMenu;
      return null;
    },
    querySelectorAll(selector) {
      if (selector === "[data-nav-toggle]" && navToggle) {
        return [navToggle];
      }
      return [];
    },
  };
  const currentUrl = new URL("http://testserver/ui/movies");
  const window = {
    clearTimeout,
    location: {
      assign(url) {
        assignedUrls.push(url);
      },
      href: currentUrl.href,
      origin: currentUrl.origin,
      pathname: currentUrl.pathname,
      search: currentUrl.search,
    },
    matchMedia() {
      return { matches: false };
    },
    navigator: {},
    setTimeout(callback, delay) {
      timeoutDelays.push(delay);
      if (runScheduled) callback();
      return 1;
    },
    addEventListener() {},
  };
  vm.runInNewContext(script, {
    console,
    document,
    requestAnimationFrame(callback) {
      callback();
    },
    sessionStorage: {
      getItem() {
        return null;
      },
      removeItem() {},
      setItem() {},
    },
    setTimeout,
    Symbol,
    URL,
    URLSearchParams,
    window,
  });
  return {
    assignedUrls,
    body,
    documentListeners,
    indicator,
    messageTarget,
    navMenu,
    navToggle,
    timeoutDelays,
    window,
  };
};

test("nav toggle opens and closes the primary navigation", () => {
  const { navMenu, navToggle } = loadBase({ withNav: true });

  navToggle.click();

  assert.equal(navMenu.classList.contains("is-open"), true);
  assert.equal(navToggle.attributes["aria-expanded"], "true");
  assert.equal(navToggle.attributes["aria-label"], "Close primary navigation");

  navToggle.click();

  assert.equal(navMenu.classList.contains("is-open"), false);
  assert.equal(navToggle.attributes["aria-expanded"], "false");
  assert.equal(navToggle.attributes["aria-label"], "Open primary navigation");
});

test("global busy ignores JavaScript-handled form submissions", () => {
  const { body, documentListeners, indicator, messageTarget } = loadBase();

  documentListeners.submit({
    defaultPrevented: true,
    target: { method: "get" },
  });

  assert.equal(indicator.attributes.hidden, "");
  assert.equal(body.attributes["aria-busy"], undefined);
  assert.equal(messageTarget.textContent, "");
});

test("global busy still handles normal form submissions", () => {
  const { body, documentListeners, indicator, messageTarget } = loadBase();

  documentListeners.submit({
    defaultPrevented: false,
    target: { method: "get" },
  });

  assert.equal(indicator.attributes.hidden, undefined);
  assert.equal(body.attributes["aria-busy"], "true");
  assert.equal(messageTarget.textContent, "Searching the Vault…");
});

test("ordinary same-origin links set busy state and navigate immediately", () => {
  const {
    assignedUrls,
    body,
    documentListeners,
    indicator,
    messageTarget,
    timeoutDelays,
  } = loadBase({ runScheduled: false });
  const event = makeAnchorClick(makeAnchor());

  documentListeners.click(event);

  assert.equal(event.defaultPrevented, true);
  assert.equal(body.attributes["aria-busy"], "true");
  assert.equal(indicator.attributes.hidden, undefined);
  assert.equal(messageTarget.textContent, "Opening the Vault…");
  assert.deepEqual(assignedUrls, ["http://testserver/ui/movies?page=2"]);
  assert.deepEqual(timeoutDelays, []);
});

test("global navigation observes a click canceled by the Library pager", () => {
  const { assignedUrls, body, documentListeners, timeoutDelays } = loadBase({
    runScheduled: false,
  });
  const event = makeAnchorClick(makeAnchor(), { defaultPrevented: true });

  documentListeners.click(event);

  assert.deepEqual(assignedUrls, []);
  assert.deepEqual(timeoutDelays, []);
  assert.equal(body.attributes["aria-busy"], undefined);
});

test("global navigation preserves native handling for special links", () => {
  const cases = [
    {
      event: { metaKey: true },
      label: "modifier click",
      link: makeAnchor(),
    },
    {
      label: "new tab target",
      link: makeAnchor({ target: "_blank" }),
    },
    {
      label: "download",
      link: makeAnchor({ download: true }),
    },
    {
      label: "same-page hash",
      link: makeAnchor({ href: "http://testserver/ui/movies#results" }),
    },
    {
      label: "external origin",
      link: makeAnchor({ href: "https://example.com/movies" }),
    },
    {
      label: "dedicated back link",
      link: makeAnchor({ backLink: true }),
    },
  ];

  cases.forEach(({ event: eventOverrides, label, link }) => {
    const { assignedUrls, body, documentListeners, timeoutDelays } = loadBase({
      runScheduled: false,
    });
    const event = makeAnchorClick(link, eventOverrides);

    documentListeners.click(event);

    assert.equal(event.defaultPrevented, false, label);
    assert.deepEqual(assignedUrls, [], label);
    assert.deepEqual(timeoutDelays, [], label);
    assert.equal(body.attributes["aria-busy"], undefined, label);
  });
});
