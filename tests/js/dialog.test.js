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
  };
};

const makeFocusable = () => ({
  disabled: false,
  focused: false,
  isConnected: true,
  focus() {
    this.focused = true;
  },
});

const loadDialog = ({ selectors = {}, trigger = makeFocusable() } = {}) => {
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
      return selectors[selector] || null;
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
