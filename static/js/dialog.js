(function () {
  const controllers = new WeakMap();

  const bind = (
    dialog,
    { bodyClass = "modal-open", closeSelector, onClose } = {},
  ) => {
    if (!dialog) return null;
    if (controllers.has(dialog)) return controllers.get(dialog);

    let trigger = null;
    let restoreFocus = true;
    let closing = false;

    const finishClose = () => {
      dialog.classList.remove("is-open");
      dialog.setAttribute("aria-hidden", "true");
      if (bodyClass) document.body.classList.remove(bodyClass);
      onClose?.();
      if (restoreFocus) trigger?.focus();
      trigger = null;
      restoreFocus = true;
      closing = false;
    };

    const close = (options = {}) => {
      if (closing) return;
      closing = true;
      restoreFocus = options.restoreFocus !== false;
      if (dialog.open && typeof dialog.close === "function") {
        dialog.close();
      } else {
        finishClose();
      }
    };

    const open = (nextTrigger = document.activeElement) => {
      trigger = nextTrigger;
      dialog.classList.add("is-open");
      dialog.setAttribute("aria-hidden", "false");
      if (bodyClass) document.body.classList.add(bodyClass);
      if (typeof dialog.showModal === "function" && !dialog.open) {
        dialog.showModal();
      } else {
        dialog.setAttribute("open", "");
      }
    };

    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      close();
    });
    dialog.addEventListener("close", finishClose);
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) close();
    });
    if (closeSelector) {
      dialog.addEventListener("click", (event) => {
        if (event.target.closest(closeSelector)) close();
      });
    }

    const controller = { close, open };
    controllers.set(dialog, controller);
    return controller;
  };

  window.VaultDialog = { bind };
})();
