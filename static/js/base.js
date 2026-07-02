(() => {
  const initNav = () => {
    const navToggles = Array.from(
      document.querySelectorAll("[data-nav-toggle]"),
    );
    const navMenu = document.querySelector("[data-nav-menu]");

    if (!navToggles.length || !navMenu) {
      return;
    }

    const isMobileNav = () => window.matchMedia("(max-width: 820px)").matches;

    const setExpanded = (next) => {
      navToggles.forEach((toggle) =>
        toggle.setAttribute("aria-expanded", String(next)),
      );
    };

    navToggles.forEach((toggle) => {
      toggle.addEventListener("click", (event) => {
        if (isMobileNav()) {
          event.preventDefault();
        }
        const expanded = navMenu.classList.contains("is-open");
        const next = !expanded;
        navMenu.classList.toggle("is-open", next);
        setExpanded(next);
      });
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initNav, { once: true });
  } else {
    initNav();
  }

  const isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
  if (isStandalone) {
    document.body.classList.add("is-standalone");
  }
})();

window.showToast = function (input) {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const options =
    input && typeof input === "object" && !Array.isArray(input)
      ? input
      : { message: input };
  const label = String(options.label || "").trim();
  const message = String(options.message ?? "").trim();
  const tone = String(options.tone || "").trim();
  const toast = document.createElement("div");
  toast.className = "toast";
  if (tone) {
    toast.dataset.tone = tone;
  }
  const content = document.createElement("span");
  content.className = "toast__content";
  if (label) {
    const labelNode = document.createElement("strong");
    labelNode.className = "toast__label";
    labelNode.textContent = label;
    content.appendChild(labelNode);
  }
  const messageNode = document.createElement("span");
  messageNode.className = "toast__message";
  messageNode.textContent = message;
  content.appendChild(messageNode);
  const button = document.createElement("button");
  button.setAttribute("aria-label", "Dismiss toast");
  button.textContent = "\u00d7";
  toast.appendChild(content);
  toast.appendChild(button);
  const dismiss = () => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 200);
  };
  button.addEventListener("click", dismiss);
  container.appendChild(toast);
  requestAnimationFrame(() => {
    toast.classList.add("show");
  });
  setTimeout(dismiss, 6000);
};

window.persistToastMessage = function (message) {
  try {
    sessionStorage.setItem(
      "flicToast",
      typeof message === "string" ? message : JSON.stringify(message),
    );
  } catch (err) {
    console.warn("Failed to persist toast message", err);
  }
};

(() => {
  const indicator = document.querySelector("[data-vault-busy]");
  const messageTarget = indicator?.querySelector("[data-vault-busy-message]");
  let activeToken = null;
  let showTimer = null;

  const clearBusy = () => {
    activeToken = null;
    window.clearTimeout(showTimer);
    showTimer = null;
    indicator?.setAttribute("hidden", "");
    document.body.removeAttribute("aria-busy");
  };

  window.setVaultBusy = function setVaultBusy(
    message = "Vault is thinking…",
    { delay = 120 } = {},
  ) {
    if (!indicator || !messageTarget) return () => {};
    const token = Symbol("vault-busy");
    activeToken = token;
    window.clearTimeout(showTimer);
    messageTarget.textContent = String(message);
    document.body.setAttribute("aria-busy", "true");
    const show = () => {
      if (activeToken === token) indicator.removeAttribute("hidden");
    };
    if (delay > 0) {
      showTimer = window.setTimeout(show, delay);
    } else {
      show();
    }
    const release = () => {
      if (activeToken === token) clearBusy();
    };
    release.update = (nextMessage) => {
      if (activeToken === token) {
        messageTarget.textContent = String(nextMessage);
      }
    };
    return release;
  };

  document.addEventListener("click", (event) => {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }
    const link = event.target.closest("a[href]");
    if (
      !link ||
      link.hasAttribute("download") ||
      link.target === "_blank" ||
      link.hasAttribute("data-back-link")
    )
      return;
    const url = new URL(link.href, window.location.href);
    if (
      url.origin !== window.location.origin ||
      (url.pathname === window.location.pathname &&
        url.search === window.location.search &&
        url.hash)
    ) {
      return;
    }
    const message =
      link.dataset.vaultBusyMessage ||
      (url.pathname.match(/^\/ui\/movies\/\d+/)
        ? "Opening movie details…"
        : "Opening the Vault…");
    event.preventDefault();
    window.setVaultBusy(message, { delay: 0 });
    window.setTimeout(() => {
      window.location.assign(url.toString());
    }, 400);
  });

  document.addEventListener("submit", (event) => {
    if (event.defaultPrevented) {
      return;
    }
    const form = event.target;
    const method = String(form?.method || "get").toLowerCase();
    const message =
      form?.dataset?.vaultBusyMessage ||
      (method === "get" ? "Searching the Vault…" : "Updating the Vault…");
    window.setVaultBusy(message);
  });
  window.addEventListener("pageshow", clearBusy);
})();

const collectFallbackPickParams = () => {
  const params = new URLSearchParams();
  const firstGenre = document
    .querySelector(".hero-tags [data-genre]")
    ?.getAttribute("data-genre");
  if (firstGenre) params.set("genre", firstGenre);
  const runtimeMax = document
    .querySelector(".hero-tags [data-runtime]")
    ?.getAttribute("data-runtime");
  if (runtimeMax) params.set("runtime_max", runtimeMax);
  return params;
};

window.runFlicPick = async function runFlicPick(options = {}) {
  const { indicator, params: initialParams } = options;
  const params = new URLSearchParams();
  if (initialParams && typeof initialParams === "object") {
    Object.entries(initialParams).forEach(([key, value]) => {
      if (
        value !== undefined &&
        value !== null &&
        String(value).trim() !== ""
      ) {
        params.set(key, value);
      }
    });
  }
  if (!params.has("genre") || !params.has("runtime_max")) {
    const fallbackParams = collectFallbackPickParams();
    for (const [key, value] of fallbackParams.entries()) {
      if (!params.has(key)) params.set(key, value);
    }
  }

  if (window.runFlicPick.pending) {
    return;
  }
  window.runFlicPick.pending = true;
  if (indicator) {
    indicator.setAttribute("aria-busy", "true");
    if ("disabled" in indicator) {
      indicator.disabled = true;
    }
  }
  try {
    const query = params.toString();
    const url = query ? `/movies/picks?${query}` : "/movies/picks";
    const response = await fetch(url);
    if (response.status === 404) {
      if (typeof window.showToast === "function") {
        window.showToast({
          label: "No match",
          message: "No trusted movie fits those filters yet.",
          tone: "notice",
        });
      }
      return;
    }
    if (!response.ok) {
      if (typeof window.showToast === "function") {
        window.showToast({
          label: "Pick failed",
          message: "The Vault could not choose right now. Try again.",
          tone: "error",
        });
      }
      return;
    }
    const data = await response.json();
    const successMessage = {
      label: "Pick ready",
      message: `Queued "${data.title}" for you.`,
      tone: "success",
    };
    if (typeof window.persistToastMessage === "function") {
      window.persistToastMessage(successMessage);
    }
    if (typeof window.showToast === "function") {
      window.showToast(successMessage);
    }
    setTimeout(() => {
      window.location.href = `/ui/movies/${data.id}`;
    }, 600);
  } catch (error) {
    console.error("Global pick failed", error);
    if (typeof window.showToast === "function") {
      window.showToast({
        label: "Connection issue",
        message: "The Vault could not connect. Try again soon.",
        tone: "error",
      });
    }
  } finally {
    window.runFlicPick.pending = false;
    if (indicator) {
      indicator.removeAttribute("aria-busy");
      if ("disabled" in indicator) {
        indicator.disabled = false;
      }
    }
  }
};

try {
  const pendingToastRaw = sessionStorage.getItem("flicToast");
  if (pendingToastRaw && typeof window.showToast === "function") {
    sessionStorage.removeItem("flicToast");
    let pendingToast = pendingToastRaw;
    try {
      pendingToast = JSON.parse(pendingToastRaw);
    } catch (err) {
      pendingToast = pendingToastRaw;
    }
    window.showToast(pendingToast);
  }
} catch (err) {
  console.warn("Failed to restore toast message", err);
}
