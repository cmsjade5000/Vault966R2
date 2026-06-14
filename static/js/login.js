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
  };

  const runUnlockRedirect = () => {
    window.setTimeout(() => {
      window.location.replace("/ui/discover");
    }, 2200);
  };

  const initLogin = () => {
    const shell = document.querySelector("[data-unlocked]");
    if (!shell) return;
    if (shell.getAttribute("data-unlocked") === "1") {
      applyUnlockVisuals();
      runUnlockRedirect();
      return;
    }

    const form = document.querySelector(".login-form");
    if (!form) return;
    const errorEl = document.querySelector(".login-card__error");
    const submitButton = form.querySelector("button[type='submit']");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (form.dataset.submitting === "true") return;
      form.dataset.submitting = "true";
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.setAttribute("aria-busy", "true");
      }
      if (errorEl) {
        errorEl.textContent = "";
        errorEl.hidden = true;
      }
      try {
        const response = await fetch(form.action || "/login", {
          method: "POST",
          headers: {
            Accept: "application/json",
          },
          body: new FormData(form),
        });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          const message = data.error || "Login failed.";
          if (errorEl) {
            errorEl.textContent = message;
            errorEl.hidden = false;
          }
          return;
        }
        applyUnlockVisuals();
        runUnlockRedirect();
      } catch (error) {
        if (errorEl) {
          errorEl.textContent = "Login failed.";
          errorEl.hidden = false;
        }
      } finally {
        delete form.dataset.submitting;
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.removeAttribute("aria-busy");
        }
      }
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLogin, { once: true });
  } else {
    initLogin();
  }
})();
