const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/base.js"),
  "utf8",
);

const createElement = (tagName) => ({
  tagName: tagName.toUpperCase(),
  attributes: {},
  children: [],
  className: "",
  dataset: {},
  textContent: "",
  classList: {
    add() {},
    remove() {},
  },
  appendChild(child) {
    this.children.push(child);
    child.parentNode = this;
  },
  remove() {
    this.removed = true;
  },
  setAttribute(name, value) {
    this.attributes[name] = value;
  },
  addEventListener() {},
});

const loadBase = ({ toastContainer = null, immediateTimers = true } = {}) => {
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
  const document = {
    body,
    readyState: "complete",
    addEventListener(type, listener) {
      documentListeners[type] = listener;
    },
    createElement,
    getElementById(id) {
      if (id === "toast-container") return toastContainer;
      return null;
    },
    querySelector(selector) {
      if (selector === "[data-vault-busy]") return indicator;
      if (selector === "[data-nav-menu]") return null;
      return null;
    },
    querySelectorAll() {
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
      if (immediateTimers) callback();
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
  return { body, documentListeners, indicator, messageTarget, window };
};

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

test("global busy release updates the active loading message", () => {
  const { body, indicator, messageTarget, window } = loadBase();

  const release = window.setVaultBusy("Choosing from the full Vault…", {
    delay: 0,
  });
  release.update("Still checking trusted picks…");

  assert.equal(indicator.attributes.hidden, undefined);
  assert.equal(body.attributes["aria-busy"], "true");
  assert.equal(messageTarget.textContent, "Still checking trusted picks…");

  release();
  assert.equal(indicator.attributes.hidden, "");
  assert.equal(body.attributes["aria-busy"], undefined);
});

test("toast helper renders optional label, message, and tone", () => {
  const toastContainer = createElement("div");
  const { window } = loadBase({ toastContainer, immediateTimers: false });

  window.showToast({
    label: "Connection issue",
    message: "The Vault could not connect. Try again.",
    tone: "error",
  });

  assert.equal(toastContainer.children.length, 1);
  const toast = toastContainer.children[0];
  assert.equal(toast.dataset.tone, "error");
  assert.equal(toast.children[0].children[0].textContent, "Connection issue");
  assert.equal(
    toast.children[0].children[1].textContent,
    "The Vault could not connect. Try again.",
  );
});
