(() => {
  const isStandalone = () =>
    window.navigator?.standalone === true ||
    Boolean(window.matchMedia?.("(display-mode: standalone)")?.matches);

  const releaseSuspendedInput = () => {
    if (!isStandalone()) return;
    const input = document.activeElement;
    if (input?.matches?.(".login-form input")) input.blur();
  };

  const applyUnlockVisuals = () => {
    document.body.classList.add("auth-page--unlocked");
    const shell = document.querySelector(".login-shell");
    shell?.classList.add("is-unlocked");
    shell?.setAttribute("data-unlocked", "1");
    const archive = document.querySelector(".login-archive");
    archive?.classList.add("is-unlocked");
    const tickerSpans = document.querySelectorAll(".login-ticker__group span");
    tickerSpans.forEach((span) => {
      span.textContent = "Vault Unlocked";
    });
    const buttonValue = document.querySelector(".login-button__value");
    if (buttonValue) {
      buttonValue.textContent = "Vault unlocked";
    }
    document.dispatchEvent(new CustomEvent("vault:unlocked"));
  };

  const initLogin = () => {
    const shell = document.querySelector("[data-unlocked]");
    if (!shell) return;
    if (shell.getAttribute("data-unlocked") === "1") {
      applyUnlockVisuals();
    }

    const form = document.querySelector(".login-form");
    form?.querySelectorAll?.(".login-field input").forEach((input) => {
      input.addEventListener("click", () => {
        // Request focus synchronously inside the tap, preserving native editing.
        // Keep the request in the user gesture instead of scheduling autofocus.
        if (isStandalone() && !input.disabled && !input.readOnly) input.focus();
      });
    });
    const errorEl = document.querySelector(".login-card__error");
    const showProfileBusy = (message = "Unlocking the Vault…") => {
      if (typeof window.setVaultBusy === "function") {
        window.setVaultBusy(message, { delay: 0 });
      }

      const indicator = document.querySelector("[data-vault-busy]");
      const messageTarget = indicator?.querySelector(
        "[data-vault-busy-message]",
      );
      if (!indicator || !messageTarget) return;
      messageTarget.textContent = message;
      indicator.removeAttribute("hidden");
      indicator.setAttribute("aria-busy", "true");
      document.body.setAttribute("aria-busy", "true");
    };
    const clearError = () => {
      if (errorEl) {
        errorEl.textContent = "";
        errorEl.hidden = true;
      }
    };
    const showError = (message) => {
      if (!errorEl) return;
      errorEl.textContent = message;
      errorEl.hidden = false;
      errorEl.setAttribute?.("tabindex", "-1");
      errorEl.focus?.();
    };

    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (form.dataset.submitting === "true") return;
      clearError();
      form.dataset.submitting = "true";
      const submitButton = form.querySelector('button[type="submit"]');
      if (submitButton) submitButton.disabled = true;
      try {
        const response = await fetch(form.action || "/login", {
          method: "POST",
          body: new FormData(form),
          headers: { Accept: "application/json" },
        });
        const payload = await response.json().catch(() => ({}));
        if (
          response.ok &&
          payload.ok &&
          payload.redirect_url === "/ui/movies"
        ) {
          form.reset();
          window.location.assign(payload.redirect_url);
          return;
        }
        if (!response.ok || !payload.unlocked) {
          showError(payload.error || "Unable to unlock the vault.");
          return;
        }
        form.reset();
        applyUnlockVisuals();
      } catch (_error) {
        showError("Unable to unlock the vault.");
      } finally {
        form.dataset.submitting = "false";
        if (submitButton) submitButton.disabled = false;
      }
    });

    document.querySelectorAll(".login-profile-form").forEach((profileForm) => {
      const message =
        profileForm.dataset.vaultBusyMessage || "Unlocking the Vault…";
      const profileButton = profileForm.querySelector(".login-profile");
      let hasIntentionalProfileAction = false;
      const markIntentionalProfileAction = () => {
        hasIntentionalProfileAction = true;
      };
      ["pointerdown", "touchstart", "click"].forEach((eventName) => {
        profileButton?.addEventListener(eventName, () => {
          markIntentionalProfileAction();
          showProfileBusy(message);
        });
      });
      profileButton?.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          markIntentionalProfileAction();
        }
      });
      profileForm.addEventListener("submit", (event) => {
        event.stopPropagation();
        if (!hasIntentionalProfileAction) {
          event.preventDefault();
          return;
        }
        showProfileBusy(message);
      });
    });
  };

  window.addEventListener("pageshow", (event) => {
    if (!event.persisted) return;
    releaseSuspendedInput();
    const form = document.querySelector(".login-form");
    form?.reset();
    if (form) form.dataset.submitting = "false";
    const button = form?.querySelector('button[type="submit"]');
    if (button) button.disabled = false;
  });

  // Release editing focus on suspension so a returning tap starts fresh.
  window.addEventListener("pagehide", releaseSuspendedInput);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) releaseSuspendedInput();
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLogin, { once: true });
  } else {
    initLogin();
  }
})();
