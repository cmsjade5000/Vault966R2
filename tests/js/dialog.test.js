const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/dialog.js"),
  "utf8",
);

const makeClassList = () => {
  const values = new Set();
  return {
    add: (value) => values.add(value),
    contains: (value) => values.has(value),
    remove: (value) => values.delete(value),
    toggle(value, force) {
      if (force === true) values.add(value);
      else if (force === false) values.delete(value);
      else if (values.has(value)) values.delete(value);
      else values.add(value);
    },
  };
};

const makeFocusable = () => ({
  attributes: {},
  classList: makeClassList(),
  disabled: false,
  focused: false,
  isConnected: true,
  closest() {
    return null;
  },
  focus() {
    this.focused = true;
  },
  getAttribute(name) {
    return this.attributes[name];
  },
  setAttribute(name, value) {
    this.attributes[name] = value;
  },
});

const loadDialog = ({
  focusable = [],
  selectors = {},
  toggles = [],
  trigger = makeFocusable(),
} = {}) => {
  const listeners = {};
  const dialog = {
    classList: makeClassList(),
    attributes: {},
    open: false,
    addEventListener(type, listener) {
      listeners[type] = listener;
    },
    close() {
      this.open = false;
      listeners.close?.();
    },
    getAttribute(name) {
      return this.attributes[name];
    },
    querySelector(selector) {
      if (selector.includes("a[href]")) return focusable[0] || null;
      return selectors[selector] || null;
    },
    querySelectorAll(selector) {
      return selector === "[data-dialog-toggle][aria-pressed]"
        ? toggles
        : focusable;
    },
    removeAttribute(name) {
      delete this.attributes[name];
      if (name === "open") this.open = false;
      else delete this[name];
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
      this[name] = value;
    },
    showModal() {
      this.open = true;
    },
  };
  const document = {
    activeElement: trigger,
    body: { classList: makeClassList() },
  };
  [trigger, ...focusable, ...toggles].forEach((element) => {
    element.focus = function () {
      this.focused = true;
      document.activeElement = this;
    };
  });
  const window = {};
  vm.runInNewContext(script, { document, window, WeakMap });
  return { dialog, document, listeners, trigger, window };
};

test("opens and closes a native dialog with body lock and focus restore", () => {
  const { dialog, document, trigger, window } = loadDialog();
  const controller = window.VaultDialog.bind(dialog);

  controller.open(trigger);
  assert.equal(dialog.open, true);
  assert.equal(dialog.classList.contains("is-open"), true);
  assert.equal(document.body.classList.contains("modal-open"), true);
  assert.equal(dialog["aria-hidden"], "false");

  controller.close();
  assert.equal(dialog.open, false);
  assert.equal(dialog.classList.contains("is-open"), false);
  assert.equal(document.body.classList.contains("modal-open"), false);
  assert.equal(dialog["aria-hidden"], "true");
  assert.equal(trigger.focused, true);
});

test("cancel and backdrop requests close the bound dialog", () => {
  const { dialog, listeners, window } = loadDialog();
  const controller = window.VaultDialog.bind(dialog);
  let prevented = false;

  controller.open();
  listeners.cancel({ preventDefault: () => (prevented = true) });
  assert.equal(prevented, true);
  assert.equal(dialog.open, false);

  controller.open();
  listeners.click({ target: dialog });
  assert.equal(dialog.open, false);
});

test("moves focus to the requested initial target and restores it on Escape", () => {
  const field = makeFocusable();
  const { dialog, listeners, trigger, window } = loadDialog({
    selectors: { "#field": field },
  });
  const controller = window.VaultDialog.bind(dialog, {
    initialFocus: "#field",
  });
  let prevented = false;

  controller.open(trigger);
  assert.equal(field.focused, true);

  listeners.keydown({
    key: "Escape",
    preventDefault: () => (prevented = true),
  });
  assert.equal(prevented, true);
  assert.equal(dialog.open, false);
  assert.equal(trigger.focused, true);
});

test("skips restoring focus when the opener is no longer focusable", () => {
  const trigger = makeFocusable();
  trigger.isConnected = false;
  const { dialog, window } = loadDialog({ trigger });
  const controller = window.VaultDialog.bind(dialog);

  controller.open(trigger);
  controller.close();
  assert.equal(trigger.focused, false);
});

test("traps forward and reverse Tab navigation inside the dialog", () => {
  const first = makeFocusable();
  const summary = makeFocusable();
  const last = makeFocusable();
  const { document, listeners, window, dialog } = loadDialog({
    focusable: [first, summary, last],
  });
  const controller = window.VaultDialog.bind(dialog);

  controller.open();
  assert.equal(document.activeElement, first);

  document.activeElement = summary;
  let prevented = false;
  listeners.keydown({
    key: "Tab",
    preventDefault: () => (prevented = true),
    shiftKey: false,
  });
  assert.equal(prevented, false);
  assert.equal(document.activeElement, summary);

  document.activeElement = last;
  prevented = false;
  listeners.keydown({
    key: "Tab",
    preventDefault: () => (prevented = true),
    shiftKey: false,
  });
  assert.equal(prevented, true);
  assert.equal(document.activeElement, first);

  prevented = false;
  document.activeElement = first;
  listeners.keydown({
    key: "Tab",
    preventDefault: () => (prevented = true),
    shiftKey: true,
  });
  assert.equal(prevented, true);
  assert.equal(document.activeElement, last);
});

test("skips hidden initial controls when choosing dialog focus", () => {
  const hidden = makeFocusable();
  hidden.matches = (selector) => selector === "input[type='hidden']";
  const visible = makeFocusable();
  const { dialog, document, window } = loadDialog({
    focusable: [hidden, visible],
    selectors: { "#hidden": hidden },
  });
  const controller = window.VaultDialog.bind(dialog, {
    initialFocus: "#hidden",
  });

  controller.open();
  assert.equal(hidden.focused, false);
  assert.equal(document.activeElement, visible);
});

test("synchronizes aria-pressed for marked dialog toggles", () => {
  const toggle = makeFocusable();
  toggle.setAttribute("aria-pressed", "false");
  toggle.classList.add("is-active");
  const { dialog, listeners, window } = loadDialog({ toggles: [toggle] });
  const controller = window.VaultDialog.bind(dialog);

  controller.open();
  assert.equal(toggle.getAttribute("aria-pressed"), "true");

  toggle.classList.remove("is-active");
  listeners.click({ target: toggle });
  assert.equal(toggle.getAttribute("aria-pressed"), "false");
});
