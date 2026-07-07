(() => {
  const initSetup = () => {
    const form = document.querySelector("[data-setup-form]");
    if (!form) return;
    const errorEl = document.querySelector(".login-card__error");
    const passcode = form.querySelector('input[name="passcode"]');
    const confirm = form.querySelector('input[name="passcode_confirm"]');

    const showError = (message) => {
      if (!errorEl) return;
      errorEl.textContent = message;
      errorEl.hidden = false;
    };

    const clearError = () => {
      if (!errorEl) return;
      errorEl.textContent = "";
      errorEl.hidden = true;
    };

    form.addEventListener("input", () => {
      clearError();
      confirm?.setCustomValidity("");
    });

    form.addEventListener("submit", (event) => {
      if (!passcode || !confirm) return;
      if (passcode.value !== confirm.value) {
        event.preventDefault();
        confirm.setCustomValidity("Passcodes do not match.");
        showError("Passcodes do not match.");
        confirm.focus();
        return;
      }
      confirm.setCustomValidity("");
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSetup, { once: true });
  } else {
    initSetup();
  }
})();
