(() => {
  const initNav = () => {
    const navToggle = document.querySelector("[data-nav-toggle]");
    const navMenu = document.querySelector("[data-nav-menu]");

    navToggle?.addEventListener("click", () => {
      const expanded = navToggle.getAttribute("aria-expanded") === "true";
      const next = !expanded;
      navToggle.setAttribute("aria-expanded", String(next));
      navMenu?.classList.toggle("is-open", next);
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initNav, { once: true });
  } else {
    initNav();
  }
})();

window.showToast = function (message) {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = "toast";
  const text = document.createElement("span");
  text.textContent = String(message ?? "");
  const button = document.createElement("button");
  button.setAttribute("aria-label", "Dismiss toast");
  button.textContent = "\u00d7";
  toast.appendChild(text);
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
    sessionStorage.setItem("flicToast", message);
  } catch (err) {
    console.warn("Failed to persist toast message", err);
  }
};

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
        window.showToast("Nothing matched\u2014want me to widen the net?");
      }
      return;
    }
    if (!response.ok) {
      if (typeof window.showToast === "function") {
        window.showToast("I hit a snag\u2014try again?");
      }
      return;
    }
    const data = await response.json();
    const successMessage = `I queued "${data.title}" for you.`;
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
      window.showToast("Network hiccup\u2014try again soon?");
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
  const pendingToast = sessionStorage.getItem("flicToast");
  if (pendingToast && typeof window.showToast === "function") {
    sessionStorage.removeItem("flicToast");
    window.showToast(pendingToast);
  }
} catch (err) {
  console.warn("Failed to restore toast message", err);
}
