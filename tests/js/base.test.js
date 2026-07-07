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

const loadBase = ({ withNav = false } = {}) => {
  const documentListeners = {};
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
  const window = {
    clearTimeout,
    location: { href: "http://testserver/ui/movies" },
    matchMedia() {
      return { matches: false };
    },
    navigator: {},
    setTimeout(callback) {
      callback();
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
    body,
    documentListeners,
    indicator,
    messageTarget,
    navMenu,
    navToggle,
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
