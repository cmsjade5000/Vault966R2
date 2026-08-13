(function () {
  const PREF_KEY = "movies:lastFilters";
  const RETURN_SURFACES = {
    "/ui/discover": {
      label: "← Back to Discover",
      message: "Returning to Discover…",
    },
    "/ui/match": {
      label: "← Back to Picker",
      message: "Returning to the Picker…",
    },
    "/ui/movies": {
      label: "← Back to Library",
      message: "Returning to the Library…",
    },
    "/ui/watchlist": {
      label: "← Back to Watchlist",
      message: "Returning to the Watchlist…",
    },
  };

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

  function readReturnSurface(rawUrl) {
    if (!rawUrl) return null;
    try {
      const url = new URL(rawUrl, window.location.origin);
      const surface = RETURN_SURFACES[url.pathname];
      if (
        url.origin !== window.location.origin ||
        url.username ||
        url.password ||
        !surface
      ) {
        return null;
      }
      return { ...surface, url };
    } catch (err) {
      console.warn("Failed to read return context", err);
      return null;
    }
  }

  function applyReturnSurface(link, context, source) {
    link.textContent = context.label;
    link.setAttribute("href", context.url.toString());
    link.dataset.vaultBusyMessage = context.message;
    link.dataset.backContext = source;
  }

  window.VaultBackLinkSupport = {
    buildUrl,
    readReturnSurface,
  };

  const link = document.querySelector("[data-back-link]");
  if (!link) return;

  if (link.dataset.backContext === "explicit") {
    const explicitContext = readReturnSurface(link.getAttribute("href"));
    if (explicitContext) {
      applyReturnSurface(link, explicitContext, "explicit");
    } else {
      link.dataset.backContext = "default";
    }
  } else {
    const referrerContext = readReturnSurface(document.referrer);
    if (referrerContext) {
      applyReturnSurface(link, referrerContext, "referrer");
    }
  }

  link.addEventListener("click", (event) => {
    const context =
      readReturnSurface(link.getAttribute("href")) ||
      readReturnSurface("/ui/movies");
    try {
      const params =
        link.dataset.backContext === "default" &&
        context.url.pathname === "/ui/movies"
          ? readPersistedFilters()
          : null;
      const url = buildUrl(context.url, params);
      event.preventDefault();
      if (typeof window.setVaultBusy === "function") {
        window.setVaultBusy(
          link.dataset.vaultBusyMessage || "Returning to the Library…",
          { delay: 0 },
        );
      }
      window.location.href = url;
    } catch (err) {
      console.warn("Failed to restore filters", err);
    }
  });
})();
