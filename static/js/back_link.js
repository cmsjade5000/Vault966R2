(function () {
  const link = document.querySelector("[data-back-link]");
  if (!link) return;

  const PREF_KEY = "movies:lastFilters";

  function readPersistedFilters() {
    try {
      const prefix = `${PREF_KEY}=`;
      const match = document.cookie
        .split(";")
        .map((item) => item.trim())
        .find((item) => item.startsWith(prefix));
      if (!match) return null;
      const raw = match.slice(prefix.length);
      if (!raw) return null;
      return JSON.parse(decodeURIComponent(raw));
    } catch (err) {
      console.warn("Failed to read movie filters cookie", err);
      return null;
    }
  }

  function buildUrl(baseUrl, paramsObj) {
    const url = new URL(baseUrl, window.location.origin);
    if (paramsObj) {
      Object.entries(paramsObj).forEach(([key, value]) => {
        if (
          value !== undefined &&
          value !== null &&
          String(value).trim() !== ""
        ) {
          url.searchParams.set(key, value);
        }
      });
    }
    return url.toString();
  }

  const referrer = document.referrer;
  if (referrer) {
    try {
      const url = new URL(referrer);
      if (url.origin === window.location.origin) {
        if (url.pathname.startsWith("/ui/discover")) {
          link.textContent = "← Back to Discover";
          link.setAttribute("href", "/ui/discover");
          link.dataset.vaultBusyMessage = "Returning to Discover…";
        } else if (url.pathname.startsWith("/ui/watchlist")) {
          link.textContent = "← Back to Watchlist";
          link.setAttribute("href", "/ui/watchlist");
          link.dataset.vaultBusyMessage = "Returning to the Watchlist…";
        } else if (url.pathname.startsWith("/ui/movies")) {
          link.textContent = "← Back to Library";
          link.setAttribute("href", "/ui/movies");
          link.dataset.vaultBusyMessage = "Returning to the Library…";
        }
      }
    } catch (err) {
      console.warn("Failed to read referrer", err);
    }
  }

  link.addEventListener("click", (event) => {
    const baseHref = link.getAttribute("href") || "/ui/movies";
    try {
      const params = baseHref.startsWith("/ui/movies")
        ? readPersistedFilters()
        : null;
      const url = buildUrl(baseHref, params);
      event.preventDefault();
      if (typeof window.setVaultBusy === "function") {
        window.setVaultBusy(
          link.dataset.vaultBusyMessage || "Returning to the Library…",
          { delay: 0 },
        );
      }
      window.setTimeout(() => {
        window.location.href = url;
      }, 400);
    } catch (err) {
      console.warn("Failed to restore filters", err);
    }
  });
})();
