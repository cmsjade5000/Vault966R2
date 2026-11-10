(() => {
  const init = () => {
    const menu = document.querySelector("[data-profile-menu]");
    const trigger = menu?.querySelector("[data-profile-menu-trigger]");
    const panel = menu?.querySelector("[data-profile-menu-panel]");
    if (!menu || !trigger || !panel) return;

    const nav = document.querySelector("[data-nav-menu]");
    const navToggles = Array.from(
      document.querySelectorAll("[data-nav-toggle]"),
    );
    const items = () => Array.from(panel.querySelectorAll("a[href], button"));
    const sync = () => {
      trigger.setAttribute("aria-expanded", String(menu.open));
      trigger.setAttribute(
        "aria-label",
        `${menu.open ? "Close" : "Open"} profile menu`,
      );
    };
    const closeNav = () => {
      nav?.classList.remove("is-open");
      navToggles.forEach((toggle) => {
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-label", "Open primary navigation");
      });
    };
    const close = (restoreFocus = false) => {
      if (!menu.open) return;
      menu.open = false;
      sync();
      if (restoreFocus) trigger.focus();
    };
    menu.addEventListener("toggle", () => {
      sync();
      if (menu.open) closeNav();
    });
    trigger.addEventListener("keydown", (event) => {
      if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
      event.preventDefault();
      menu.open = true;
      sync();
      closeNav();
      const entries = items();
      (event.key === "ArrowDown" ? entries[0] : entries.at(-1))?.focus();
    });
    panel.addEventListener("keydown", (event) => {
      const entries = items();
      const index = entries.indexOf(document.activeElement);
      if (index < 0) return;
      let next;
      if (event.key === "ArrowDown") next = (index + 1) % entries.length;
      else if (event.key === "ArrowUp")
        next = (index - 1 + entries.length) % entries.length;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = entries.length - 1;
      else return;
      event.preventDefault();
      entries[next]?.focus();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && menu.open) {
        event.preventDefault();
        close(true);
      }
    });
    document.addEventListener("pointerdown", (event) => {
      if (!menu.contains(event.target)) close();
    });
    menu.addEventListener("focusout", (event) => {
      if (event.relatedTarget && !menu.contains(event.relatedTarget)) close();
    });
    navToggles.forEach((toggle) =>
      toggle.addEventListener("click", () => close()),
    );
    window.addEventListener("blur", () => close());
    window.addEventListener("pageshow", () => {
      close();
      closeNav();
    });
    sync();
  };
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init);
  else init();
})();
