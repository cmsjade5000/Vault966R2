(() => {
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

    const firstProfile = document.querySelector(".login-profile");
    window.setTimeout(() => {
      firstProfile?.focus();
    }, 260);
  };

  const initLogin = () => {
    const shell = document.querySelector("[data-unlocked]");
    if (!shell) return;
    if (shell.getAttribute("data-unlocked") === "1") {
      applyUnlockVisuals();
    }

    const form = document.querySelector(".login-form");
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

    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (form.dataset.submitting === "true") return;
      clearError();
      applyUnlockVisuals();
    });

    document.querySelectorAll(".login-profile-form").forEach((profileForm) => {
      const message =
        profileForm.dataset.vaultBusyMessage || "Unlocking the Vault…";
      const profileButton = profileForm.querySelector(".login-profile");
      ["pointerdown", "touchstart", "click"].forEach((eventName) => {
        profileButton?.addEventListener(eventName, () => {
          showProfileBusy(message);
        });
      });
      profileForm.addEventListener("submit", (event) => {
        event.stopPropagation();
        showProfileBusy(message);
      });
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLogin, { once: true });
  } else {
    initLogin();
  }
})();
