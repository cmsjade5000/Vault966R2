const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const script = fs.readFileSync(
  path.resolve(__dirname, "../../static/js/profile_menu.js"),
  "utf8",
);

const load = ({ count = 3, absent = false, loading = false } = {}) => {
  const documentEvents = {};
  const windowEvents = {};
  const document = {
    activeElement: null,
    readyState: loading ? "loading" : "complete",
  };
  const node = () => {
    const events = {};
    return {
      attributes: {},
      events,
      addEventListener(type, callback) {
        events[type] = callback;
      },
      setAttribute(name, value) {
        this.attributes[name] = value;
      },
      focus() {
        document.activeElement = this;
      },
    };
  };
  const trigger = node();
  const panel = node();
  const items = Array.from({ length: count }, node);
  panel.querySelectorAll = () => items;
  const menu = node();
  menu.open = false;
  menu.querySelector = (selector) =>
    selector === "[data-profile-menu-trigger]" ? trigger : panel;
  menu.contains = (target) =>
    target === menu ||
    target === trigger ||
    target === panel ||
    items.includes(target);
  const toggle = node();
  const nav = {
    expanded: true,
    classList: {
      remove() {
        nav.expanded = false;
      },
    },
  };
  document.querySelector = (selector) =>
    selector === "[data-profile-menu]" ? (absent ? null : menu) : nav;
  document.querySelectorAll = () => [toggle];
  document.addEventListener = (type, callback) => {
    documentEvents[type] = callback;
  };
  const window = {
    addEventListener(type, callback) {
      windowEvents[type] = callback;
    },
  };
  vm.runInNewContext(script, { document, window });
  const event = (key) => ({
    key,
    prevented: false,
    preventDefault() {
      this.prevented = true;
    },
  });
  const open = () => {
    menu.open = true;
    menu.events.toggle();
  };
  return {
    document,
    documentEvents,
    windowEvents,
    trigger,
    panel,
    menu,
    items,
    toggle,
    nav,
    event,
    open,
  };
};

test("profile disclosure synchronizes accessible state and closes primary navigation", () => {
  const h = load();
  assert.equal(h.trigger.attributes["aria-expanded"], "false");
  h.open();
  assert.equal(h.trigger.attributes["aria-expanded"], "true");
  assert.equal(h.trigger.attributes["aria-label"], "Close profile menu");
  assert.equal(h.nav.expanded, false);
  assert.equal(h.toggle.attributes["aria-expanded"], "false");
});
test("Escape closes disclosure and returns focus to the avatar", () => {
  const h = load();
  h.open();
  h.items[1].focus();
  const e = h.event("Escape");
  h.documentEvents.keydown(e);
  assert.equal(h.menu.open, false);
  assert.equal(h.document.activeElement, h.trigger);
  assert.equal(e.prevented, true);
});
test("Escape does not steal focus when the disclosure is closed", () => {
  const h = load();
  h.items[0].focus();
  const e = h.event("Escape");
  h.documentEvents.keydown(e);
  assert.equal(h.document.activeElement, h.items[0]);
  assert.equal(e.prevented, false);
});
test("outside pointer dismisses without moving focus", () => {
  const h = load();
  h.open();
  const outside = {};
  h.document.activeElement = outside;
  h.documentEvents.pointerdown({ target: outside });
  assert.equal(h.menu.open, false);
  assert.equal(h.document.activeElement, outside);
});
test("inside pointer does not close disclosure", () => {
  const h = load();
  h.open();
  h.documentEvents.pointerdown({ target: h.items[0] });
  assert.equal(h.menu.open, true);
});
test("tabbing outside dismisses while moving between account actions does not", () => {
  const h = load();
  h.open();
  h.menu.events.focusout({ relatedTarget: h.items[1] });
  assert.equal(h.menu.open, true);
  h.menu.events.focusout({ relatedTarget: {} });
  assert.equal(h.menu.open, false);
});
test("avatar arrows open and focus the first or last account action", () => {
  const h = load();
  h.trigger.events.keydown(h.event("ArrowDown"));
  assert.equal(h.menu.open, true);
  assert.equal(h.document.activeElement, h.items[0]);
  h.trigger.events.keydown(h.event("ArrowUp"));
  assert.equal(h.document.activeElement, h.items.at(-1));
});
test("arrows, Home and End follow visible account actions for both roles", () => {
  for (const count of [2, 3]) {
    const h = load({ count });
    h.open();
    h.items.at(-1).focus();
    h.panel.events.keydown(h.event("ArrowDown"));
    assert.equal(h.document.activeElement, h.items[0]);
    h.panel.events.keydown(h.event("ArrowUp"));
    assert.equal(h.document.activeElement, h.items.at(-1));
    h.panel.events.keydown(h.event("Home"));
    assert.equal(h.document.activeElement, h.items[0]);
    h.panel.events.keydown(h.event("End"));
    assert.equal(h.document.activeElement, h.items.at(-1));
  }
});
test("Tab remains native and is not trapped", () => {
  const h = load();
  h.open();
  h.items[0].focus();
  const e = h.event("Tab");
  h.panel.events.keydown(e);
  assert.equal(e.prevented, false);
});
test("opening primary navigation closes account disclosure", () => {
  const h = load();
  h.open();
  h.toggle.events.click();
  assert.equal(h.menu.open, false);
});
test("back/forward pageshow resets both overlays without stealing focus", () => {
  const h = load();
  h.open();
  const outside = {};
  h.document.activeElement = outside;
  h.nav.expanded = true;
  h.windowEvents.pageshow({ persisted: true });
  assert.equal(h.menu.open, false);
  assert.equal(h.nav.expanded, false);
  assert.equal(h.document.activeElement, outside);
});
test("window blur dismisses account disclosure", () => {
  const h = load();
  h.open();
  h.windowEvents.blur();
  assert.equal(h.menu.open, false);
});
test("unauthenticated page is safe without account elements", () => {
  assert.doesNotThrow(() => load({ absent: true }));
});
test("initialization supports deferred loading", () => {
  const h = load({ loading: true });
  assert.equal(h.trigger.attributes["aria-expanded"], undefined);
  h.documentEvents.DOMContentLoaded();
  assert.equal(h.trigger.attributes["aria-expanded"], "false");
});
