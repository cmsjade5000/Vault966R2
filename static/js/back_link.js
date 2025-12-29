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

  link.addEventListener("click", (event) => {
    const params = readPersistedFilters();
    if (!params) {
      return;
    }
    try {
      const url = buildUrl(link.getAttribute("href") || "/ui/movies", params);
      event.preventDefault();
      window.location.href = url;
    } catch (err) {
      console.warn("Failed to restore filters", err);
    }
  });
})();
