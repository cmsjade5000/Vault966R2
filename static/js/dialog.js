(function () {
  const controllers = new WeakMap();
  const focusableSelector = [
    "a[href]",
    "button:not([disabled])",
    "input:not([disabled])",
    "summary",
    "select:not([disabled])",
    "textarea:not([disabled])",
    "[tabindex]:not([tabindex='-1'])",
  ].join(",");

  const isFocusable = (element) =>
    Boolean(
      element &&
      typeof element.focus === "function" &&
      !element.disabled &&
      !element.hidden &&
      element.getAttribute?.("tabindex") !== "-1" &&
      !element.matches?.("input[type='hidden']") &&
      element.getAttribute?.("aria-hidden") !== "true" &&
      !element.closest?.("[hidden], [aria-hidden='true'], [inert]") &&
      (!element.getClientRects || element.getClientRects().length > 0) &&
      element.isConnected !== false,
    );

  const focusableElements = (dialog) =>
    Array.from(dialog.querySelectorAll?.(focusableSelector) || []).filter(
      isFocusable,
    );

  const resolveFocusTarget = (dialog, initialFocus) => {
    const candidate =
      typeof initialFocus === "function" ? initialFocus(dialog) : initialFocus;
    if (typeof candidate === "string") {
      const selected = dialog.querySelector(candidate);
      if (isFocusable(selected)) return selected;
    }
    if (isFocusable(candidate)) return candidate;
    const marked = dialog.querySelector("[data-dialog-initial-focus]");
    if (isFocusable(marked)) return marked;
    return focusableElements(dialog)[0];
  };

  const focusElement = (element) => {
    if (!isFocusable(element)) return false;
    element.focus({ preventScroll: true });
    return true;
  };

  const syncPressedToggles = (dialog) => {
    dialog
      .querySelectorAll?.("[data-dialog-toggle][aria-pressed]")
      .forEach((button) => {
        button.setAttribute(
          "aria-pressed",
          button.classList.contains("is-active") ? "true" : "false",
        );
      });
  };

  const bind = (
    dialog,
    { bodyClass = "modal-open", closeSelector, initialFocus, onClose } = {},
  ) => {
    if (!dialog) return null;
    if (controllers.has(dialog)) return controllers.get(dialog);

    let trigger = null;
    let restoreFocus = true;
    let closing = false;
    let opened = false;

    const finishClose = () => {
      if (!opened && !closing) return;
      opened = false;
      dialog.classList.remove("is-open");
      dialog.setAttribute("aria-hidden", "true");
      dialog.removeAttribute?.("open");
      if (bodyClass) document.body.classList.remove(bodyClass);
      onClose?.();
      if (restoreFocus) focusElement(trigger);
      trigger = null;
      restoreFocus = true;
      closing = false;
    };

    const close = (options = {}) => {
      if (closing || !opened) return;
      closing = true;
      restoreFocus = options.restoreFocus !== false;
      if (dialog.open && typeof dialog.close === "function") {
        dialog.close();
      } else {
        finishClose();
      }
    };

    const open = (nextTrigger = document.activeElement) => {
      if (opened) return;
      opened = true;
      trigger = isFocusable(nextTrigger) ? nextTrigger : document.activeElement;
      dialog.classList.add("is-open");
      dialog.setAttribute("aria-hidden", "false");
      if (bodyClass) document.body.classList.add(bodyClass);
      if (typeof dialog.showModal === "function" && !dialog.open) {
        dialog.showModal();
      } else {
        dialog.setAttribute("open", "");
      }
      syncPressedToggles(dialog);
      if (!focusElement(resolveFocusTarget(dialog, initialFocus))) {
        focusElement(dialog);
      }
    };

    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      close();
    });
    dialog.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = focusableElements(dialog);
      if (focusable.length === 0) {
        event.preventDefault();
        focusElement(dialog);
        return;
      }

      const currentIndex = focusable.indexOf(document.activeElement);
      const movingBeforeFirst = event.shiftKey && currentIndex <= 0;
      const movingPastLast =
        !event.shiftKey &&
        (currentIndex === -1 || currentIndex === focusable.length - 1);
      if (!movingBeforeFirst && !movingPastLast) return;

      event.preventDefault();
      focusElement(
        event.shiftKey ? focusable[focusable.length - 1] : focusable[0],
      );
    });
    dialog.addEventListener("close", finishClose);
    dialog.addEventListener("click", (event) => {
      syncPressedToggles(dialog);
      if (event.target === dialog) close();
    });
    dialog.addEventListener("input", () => syncPressedToggles(dialog));
    if (closeSelector) {
      dialog.addEventListener("click", (event) => {
        if (event.target.closest?.(closeSelector)) close();
      });
    }

    const controller = { close, open };
    controllers.set(dialog, controller);
    return controller;
  };

  window.VaultDialog = { bind };
})();
