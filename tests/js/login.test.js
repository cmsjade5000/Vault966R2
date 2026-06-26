const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/login.js"),
  "utf8",
);

const createElement = () => {
  const listeners = new Map();
  return {
    attributes: {},
    classList: {
      values: [],
      add(value) {
        this.values.push(value);
      },
    },
    dataset: {},
    hidden: false,
    listeners,
    textContent: "",
    addEventListener(name, callback) {
      listeners.set(name, callback);
    },
    getAttribute(name) {
      return this.attributes[name] ?? null;
    },
    removeAttribute(name) {
      delete this.attributes[name];
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
  };
};

const loadLogin = () => {
  const body = createElement();
  const shell = createElement();
  shell.attributes["data-unlocked"] = "0";
  const archive = createElement();
  const tickerSpan = createElement();
  const buttonValue = createElement();
  const errorEl = createElement();
  const messageTarget = createElement();
  const busyIndicator = createElement();
  busyIndicator.attributes.hidden = "";
  busyIndicator.querySelector = (selector) =>
    selector === "[data-vault-busy-message]" ? messageTarget : null;

  const loginForm = createElement();
  loginForm.action = "/login";
  loginForm.resetCount = 0;
  loginForm.reset = () => {
    loginForm.resetCount += 1;
  };

  const profileButton = createElement();
  profileButton.focusCount = 0;
  profileButton.focus = () => {
    profileButton.focusCount += 1;
  };

  const profileForm = createElement();
  profileForm.dataset.vaultBusyMessage = "Opening profile…";
  profileForm.querySelector = (selector) =>
    selector === ".login-profile" ? profileButton : null;

  const document = {
    body,
    readyState: "complete",
    dispatched: [],
    addEventListener() {},
    dispatchEvent(event) {
      this.dispatched.push(event.type);
    },
    querySelector(selector) {
      if (selector === "[data-unlocked]" || selector === ".login-shell") {
        return shell;
      }
      if (selector === ".login-archive") return archive;
      if (selector === ".login-button__value") return buttonValue;
      if (selector === ".login-profile") return profileButton;
      if (selector === ".login-form") return loginForm;
      if (selector === ".login-card__error") return errorEl;
      if (selector === "[data-vault-busy]") return busyIndicator;
      return null;
    },
    querySelectorAll(selector) {
      if (selector === ".login-ticker__group span") return [tickerSpan];
      if (selector === ".login-profile-form") return [profileForm];
      return [];
    },
  };

  const fetchCalls = [];
  const window = {
    setTimeout() {
      throw new Error("login unlock should not schedule profile focus");
    },
    setVaultBusy(message) {
      this.busyMessage = message;
    },
  };

  const context = {
    console,
    CustomEvent: class CustomEvent {
      constructor(type) {
        this.type = type;
      }
    },
    document,
    fetch: async (...args) => {
      fetchCalls.push(args);
      return {
        ok: true,
        json: async () => ({ unlocked: true }),
      };
    },
    FormData: class FormData {
      constructor(form) {
        this.form = form;
      }
    },
    window,
  };

  vm.runInNewContext(script, context);
  return {
    body,
    buttonValue,
    document,
    fetchCalls,
    loginForm,
    messageTarget,
    profileButton,
    profileForm,
    shell,
    window,
  };
};

test("unlocking reveals profiles without focusing or submitting one", async () => {
  const { buttonValue, fetchCalls, loginForm, profileButton, shell } =
    loadLogin();
  let prevented = 0;
  let stopped = 0;

  await loginForm.listeners.get("submit")({
    preventDefault() {
      prevented += 1;
    },
    stopPropagation() {
      stopped += 1;
    },
  });

  assert.equal(prevented, 1);
  assert.equal(stopped, 1);
  assert.equal(fetchCalls.length, 1);
  assert.equal(shell.getAttribute("data-unlocked"), "1");
  assert.equal(buttonValue.textContent, "Vault unlocked");
  assert.equal(loginForm.resetCount, 1);
  assert.equal(profileButton.focusCount, 0);
});

test("profile submit is ignored until the user intentionally chooses it", () => {
  const { messageTarget, profileForm, window } = loadLogin();
  let prevented = 0;
  let stopped = 0;

  profileForm.listeners.get("submit")({
    preventDefault() {
      prevented += 1;
    },
    stopPropagation() {
      stopped += 1;
    },
  });

  assert.equal(stopped, 1);
  assert.equal(prevented, 1);
  assert.equal(window.busyMessage, undefined);
  assert.equal(messageTarget.textContent, "");
});

test("profile submit proceeds after a tap or keyboard activation", () => {
  const { messageTarget, profileButton, profileForm, window } = loadLogin();
  let prevented = 0;

  profileButton.listeners.get("keydown")({ key: "Enter" });
  profileForm.listeners.get("submit")({
    preventDefault() {
      prevented += 1;
    },
    stopPropagation() {},
  });

  assert.equal(prevented, 0);
  assert.equal(window.busyMessage, "Opening profile…");
  assert.equal(messageTarget.textContent, "Opening profile…");
});
