(() => {
  const isIos = () => /iphone|ipad|ipod/i.test(window.navigator.userAgent);
  const isStandalone = () =>
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;

  const shouldShow = () => {
    if (!isIos() || isStandalone()) return false;
    if (window.location.pathname !== "/login") return false;
    try {
      const dismissed = localStorage.getItem("vaultInstallPromptDismissed");
      return dismissed !== "true";
    } catch {
      return true;
    }
  };

  const dismiss = (banner) => {
    banner.remove();
    try {
      localStorage.setItem("vaultInstallPromptDismissed", "true");
    } catch {
      // Ignore storage failures.
    }
  };

  const render = () => {
    if (!shouldShow()) return;
    const banner = document.createElement("div");
    banner.className = "install-banner";
    banner.setAttribute("role", "region");
    banner.setAttribute("aria-label", "Install Vault 966");

    const copy = document.createElement("div");
    copy.className = "install-banner__copy";

    const title = document.createElement("strong");
    title.textContent = "Add Vault 966 to your Home Screen";

    const body = document.createElement("p");
    body.textContent = "Tap Share, then Add to Home Screen for the full-screen vault.";

    copy.appendChild(title);
    copy.appendChild(body);

    const close = document.createElement("button");
    close.type = "button";
    close.className = "install-banner__close";
    close.setAttribute("aria-label", "Dismiss install prompt");
    close.textContent = "×";
    close.addEventListener("click", () => dismiss(banner));

    banner.appendChild(copy);
    banner.appendChild(close);

    document.body.appendChild(banner);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
})();
