const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/setup.js"),
  "utf8",
);

const createElement = () => {
  const listeners = new Map();
  return {
    hidden: true,
    listeners,
    textContent: "",
    value: "",
    focusCount: 0,
    validityMessage: "",
    addEventListener(name, callback) {
      listeners.set(name, callback);
    },
    focus() {
      this.focusCount += 1;
    },
    setCustomValidity(message) {
      this.validityMessage = message;
    },
  };
};

const loadSetup = () => {
  const form = createElement();
  const errorEl = createElement();
  const passcode = createElement();
  const confirm = createElement();
  form.querySelector = (selector) => {
    if (selector === 'input[name="passcode"]') return passcode;
    if (selector === 'input[name="passcode_confirm"]') return confirm;
    return null;
  };
  const document = {
    readyState: "complete",
    addEventListener() {},
    querySelector(selector) {
      if (selector === "[data-setup-form]") return form;
      if (selector === ".login-card__error") return errorEl;
      return null;
    },
  };
  vm.runInNewContext(script, { document });
  return { confirm, errorEl, form, passcode };
};

test("setup form blocks mismatched passcodes before submit", () => {
  const { confirm, errorEl, form, passcode } = loadSetup();
  let prevented = 0;
  passcode.value = "9660";
  confirm.value = "wrong";

  form.listeners.get("submit")({
    preventDefault() {
      prevented += 1;
    },
  });

  assert.equal(prevented, 1);
  assert.equal(confirm.validityMessage, "Passcodes do not match.");
  assert.equal(confirm.focusCount, 1);
  assert.equal(errorEl.hidden, false);
  assert.equal(errorEl.textContent, "Passcodes do not match.");
});

test("setup form allows matching passcodes", () => {
  const { confirm, form, passcode } = loadSetup();
  let prevented = 0;
  passcode.value = "9660";
  confirm.value = "9660";

  form.listeners.get("submit")({
    preventDefault() {
      prevented += 1;
    },
  });

  assert.equal(prevented, 0);
  assert.equal(confirm.validityMessage, "");
});
