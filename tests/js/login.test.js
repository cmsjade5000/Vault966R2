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
    disabled: false,
    focusCount: 0,
    hidden: false,
    listeners,
    textContent: "",
    addEventListener(name, callback) {
      listeners.set(name, callback);
    },
    focus() {
      this.focusCount += 1;
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

const loadLogin = ({
  fetchResponse,
  fetchError,
  standalone = false,
  mediaStandalone = false,
} = {}) => {
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
  const inputs = [createElement(), createElement()];
  loginForm.querySelectorAll = () => inputs;
  const submitButton = createElement();
  loginForm.action = "/login";
  loginForm.querySelector = (selector) =>
    selector === 'button[type="submit"]' ? submitButton : null;
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
    activeElement: body,
    hidden: false,
    listeners: new Map(),
    readyState: "complete",
    dispatched: [],
    addEventListener(name, callback) {
      this.listeners.set(name, callback);
    },
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
  inputs.forEach((input) => {
    input.readOnly = false;
    input.blurCount = 0;
    input.matches = (selector) => selector === ".login-form input";
    input.focus = () => {
      input.focusCount += 1;
      document.activeElement = input;
    };
    input.blur = () => {
      input.blurCount += 1;
      document.activeElement = body;
    };
  });

  const fetchCalls = [];
  const redirects = [];
  const window = {
    navigator: { standalone },
    matchMedia: () => ({ matches: mediaStandalone }),
    listeners: new Map(),
    addEventListener(name, callback) {
      this.listeners.set(name, callback);
    },
    location: {
      assign(url) {
        redirects.push(url);
      },
    },
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
      if (fetchError) throw fetchError;
      if (fetchResponse) return fetchResponse;
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
    errorEl,
    fetchCalls,
    loginForm,
    inputs,
    messageTarget,
    profileButton,
    profileForm,
    redirects,
    shell,
    submitButton,
    window,
  };
};

const submitEvent = () => ({
  prevented: 0,
  stopped: 0,
  preventDefault() {
    this.prevented += 1;
  },
  stopPropagation() {
    this.stopped += 1;
  },
});

const jsonResponse = (payload, ok = true) => ({
  ok,
  json: async () => payload,
});

test("personal sign-in opens the movie library directly", async () => {
  const {
    document,
    errorEl,
    fetchCalls,
    loginForm,
    profileButton,
    redirects,
    shell,
    submitButton,
  } = loadLogin({
    fetchResponse: jsonResponse({ ok: true, redirect_url: "/ui/movies" }),
  });
  const event = submitEvent();
  errorEl.hidden = false;
  errorEl.textContent = "Previous error";

  await loginForm.listeners.get("submit")(event);

  assert.equal(event.prevented, 1);
  assert.equal(event.stopped, 1);
  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0][0], "/login");
  assert.equal(fetchCalls[0][1].method, "POST");
  assert.equal(fetchCalls[0][1].headers.Accept, "application/json");
  assert.equal(fetchCalls[0][1].body.form, loginForm);
  assert.deepEqual(redirects, ["/ui/movies"]);
  assert.equal(loginForm.resetCount, 1);
  assert.equal(shell.getAttribute("data-unlocked"), "0");
  assert.deepEqual(document.dispatched, []);
  assert.equal(profileButton.focusCount, 0);
  assert.equal(errorEl.hidden, true);
  assert.equal(errorEl.textContent, "");
  assert.equal(submitButton.disabled, false);
  assert.equal(loginForm.dataset.submitting, "false");
});

test("switch-profile sign-in uses the form action", async () => {
  const { fetchCalls, loginForm, redirects } = loadLogin({
    fetchResponse: jsonResponse({ ok: true, redirect_url: "/ui/movies" }),
  });
  loginForm.action = "/login/switch";

  await loginForm.listeners.get("submit")(submitEvent());

  assert.equal(fetchCalls[0][0], "/login/switch");
  assert.deepEqual(redirects, ["/ui/movies"]);
});

test("a pending sign-in disables submit and ignores duplicate submissions", async () => {
  let resolveResponse;
  const response = new Promise((resolve) => {
    resolveResponse = resolve;
  });
  const { fetchCalls, loginForm, redirects, submitButton } = loadLogin({
    fetchResponse: response,
  });
  const submit = loginForm.listeners.get("submit");
  const firstSubmission = submit(submitEvent());
  const duplicateEvent = submitEvent();

  assert.equal(submitButton.disabled, true);
  assert.equal(loginForm.dataset.submitting, "true");
  await submit(duplicateEvent);
  assert.equal(duplicateEvent.prevented, 1);
  assert.equal(duplicateEvent.stopped, 1);
  assert.equal(fetchCalls.length, 1);

  resolveResponse(jsonResponse({ ok: true, redirect_url: "/ui/movies" }));
  await firstSubmission;

  assert.deepEqual(redirects, ["/ui/movies"]);
  assert.equal(submitButton.disabled, false);
  assert.equal(loginForm.dataset.submitting, "false");
});

test("rejected credentials focus the error and allow another attempt", async () => {
  const { errorEl, fetchCalls, loginForm, redirects, shell, submitButton } =
    loadLogin({
      fetchResponse: jsonResponse(
        { error: "Invalid dummy credentials." },
        false,
      ),
    });

  await loginForm.listeners.get("submit")(submitEvent());

  assert.equal(errorEl.textContent, "Invalid dummy credentials.");
  assert.equal(errorEl.hidden, false);
  assert.equal(errorEl.getAttribute("tabindex"), "-1");
  assert.equal(errorEl.focusCount, 1);
  assert.equal(loginForm.resetCount, 0);
  assert.equal(shell.getAttribute("data-unlocked"), "0");
  assert.deepEqual(redirects, []);
  assert.equal(submitButton.disabled, false);
  assert.equal(loginForm.dataset.submitting, "false");

  await loginForm.listeners.get("submit")(submitEvent());
  assert.equal(fetchCalls.length, 2);
});

test("network failure shows a focused error and restores submit", async () => {
  const { errorEl, loginForm, redirects, submitButton } = loadLogin({
    fetchError: new Error("Synthetic connection failure"),
  });

  await loginForm.listeners.get("submit")(submitEvent());

  assert.equal(errorEl.textContent, "Unable to unlock the vault.");
  assert.equal(errorEl.hidden, false);
  assert.equal(errorEl.focusCount, 1);
  assert.equal(loginForm.resetCount, 0);
  assert.deepEqual(redirects, []);
  assert.equal(submitButton.disabled, false);
  assert.equal(loginForm.dataset.submitting, "false");
});

test("invalid response JSON shows an error and restores submit", async () => {
  const { errorEl, loginForm, redirects, submitButton } = loadLogin({
    fetchResponse: {
      ok: true,
      json: async () => {
        throw new SyntaxError("Synthetic invalid JSON");
      },
    },
  });

  await loginForm.listeners.get("submit")(submitEvent());

  assert.equal(errorEl.textContent, "Unable to unlock the vault.");
  assert.equal(errorEl.focusCount, 1);
  assert.deepEqual(redirects, []);
  assert.equal(submitButton.disabled, false);
});

test("direct sign-in accepts only the movie-library redirect", async () => {
  const { errorEl, loginForm, redirects, shell } = loadLogin({
    fetchResponse: jsonResponse({
      ok: true,
      redirect_url: "https://example.invalid/dummy",
    }),
  });

  await loginForm.listeners.get("submit")(submitEvent());

  assert.deepEqual(redirects, []);
  assert.equal(shell.getAttribute("data-unlocked"), "0");
  assert.equal(errorEl.hidden, false);
});

test("returning from the back-forward cache clears credentials and submit state", () => {
  const { loginForm, submitButton, window } = loadLogin();
  loginForm.dataset.submitting = "true";
  submitButton.disabled = true;

  window.listeners.get("pageshow")({ persisted: true });

  assert.equal(loginForm.resetCount, 1);
  assert.equal(loginForm.dataset.submitting, "false");
  assert.equal(submitButton.disabled, false);
});

test("ordinary page show does not reset the form", () => {
  const { loginForm, window } = loadLogin();

  window.listeners.get("pageshow")({ persisted: false });

  assert.equal(loginForm.resetCount, 0);
});

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

for (const eventName of ["pointerdown", "touchstart", "click"]) {
  test(`profile submit proceeds after intentional ${eventName}`, () => {
    const { messageTarget, profileButton, profileForm, window } = loadLogin();
    const event = submitEvent();

    profileButton.listeners.get(eventName)({});
    profileForm.listeners.get("submit")(event);

    assert.equal(event.prevented, 0);
    assert.equal(event.stopped, 1);
    assert.equal(window.busyMessage, "Opening profile…");
    assert.equal(messageTarget.textContent, "Opening profile…");
  });
}

test("unrelated keys do not select a legacy shared profile", () => {
  const { profileButton, profileForm, window } = loadLogin();
  const event = submitEvent();

  profileButton.listeners.get("keydown")({ key: "Tab" });
  profileForm.listeners.get("submit")(event);

  assert.equal(event.prevented, 1);
  assert.equal(window.busyMessage, undefined);
});

for (const flag of ["standalone", "mediaStandalone"]) {
  test(`standalone input taps request synchronous native focus via ${flag}`, () => {
    const { inputs, document, fetchCalls } = loadLogin({ [flag]: true });
    assert.equal(inputs[0].focusCount, 0);
    const event = submitEvent();
    inputs[0].listeners.get("click")(event);
    assert.equal(inputs[0].focusCount, 1);
    assert.equal(document.activeElement, inputs[0]);
    assert.equal(event.prevented, 0);
    assert.equal(event.stopped, 0);
    assert.equal(fetchCalls.length, 0);
  });
}

test("ordinary Safari input taps leave focus to the native default", () => {
  const { inputs } = loadLogin();
  inputs[0].listeners.get("click")({});
  assert.equal(inputs[0].focusCount, 0);
});

test("standalone focus does not alter disabled or read-only controls", () => {
  const { inputs } = loadLogin({ standalone: true });
  inputs[0].disabled = true;
  inputs[1].readOnly = true;
  inputs.forEach((input) => input.listeners.get("click")({}));
  assert.equal(inputs[0].focusCount, 0);
  assert.equal(inputs[1].focusCount, 0);
});

test("suspending a standalone login releases editing without reading credential values", () => {
  const { inputs, document, window, loginForm } = loadLogin({
    standalone: true,
  });
  Object.defineProperty(inputs[1], "value", {
    get() {
      throw Error("Credential value read");
    },
  });
  inputs[1].focus();
  window.listeners.get("pagehide")({});
  assert.equal(inputs[1].blurCount, 1);
  assert.equal(document.activeElement, document.body);
  assert.equal(loginForm.resetCount, 0);
});

test("only hidden standalone visibility releases the active login input", () => {
  const { inputs, document } = loadLogin({ standalone: true });
  inputs[0].focus();
  document.listeners.get("visibilitychange")();
  assert.equal(inputs[0].blurCount, 0);
  document.hidden = true;
  document.listeners.get("visibilitychange")();
  assert.equal(inputs[0].blurCount, 1);
});

test("page suspension leaves ordinary Safari editing focus alone", () => {
  const { inputs, window } = loadLogin();
  inputs[0].focus();
  window.listeners.get("pagehide")({});
  assert.equal(inputs[0].blurCount, 0);
});

test("a standalone cached login return releases focus and clears submission state", () => {
  const { inputs, window, loginForm, submitButton } = loadLogin({
    standalone: true,
  });
  inputs[0].focus();
  loginForm.dataset.submitting = "true";
  submitButton.disabled = true;
  window.listeners.get("pageshow")({ persisted: true });
  assert.equal(inputs[0].blurCount, 1);
  assert.equal(loginForm.resetCount, 1);
  assert.equal(submitButton.disabled, false);
});
