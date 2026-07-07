(function () {
  const getPreferenceState = (type, payload) =>
    type === "like" ? Boolean(payload.liked) : Boolean(payload.watchlist);

  const buildPreferenceLabel = (type, active, title) => {
    const movieTitle = title || "movie";
    if (type === "like") {
      return `${active ? "Unlike" : "Like"} ${movieTitle}`;
    }
    return `${active ? "Remove" : "Add"} ${movieTitle} ${
      active ? "from" : "to"
    } watchlist`;
  };

  const updatePreferenceButtons = (root, movieId, payload) => {
    root
      .querySelectorAll(`[data-preference-button][data-movie-id="${movieId}"]`)
      .forEach((button) => {
        const type = button.dataset.preferenceType;
        const active = getPreferenceState(type, payload);
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
        button.setAttribute(
          "aria-label",
          buildPreferenceLabel(type, active, button.dataset.movieTitle),
        );
      });

    root
      .querySelectorAll(`[data-movie-card][data-movie-id="${movieId}"]`)
      .forEach((card) => {
        card.dataset.liked = payload.liked ? "true" : "false";
        card.dataset.watchlist = payload.watchlist ? "true" : "false";
      });
  };

  const updateWatchlistEmptyState = (root) => {
    if (!root.body?.classList.contains("watchlist-page")) {
      return;
    }

    const grid = root.querySelector("[data-watchlist-grid]");
    const emptyState = root.querySelector("[data-watchlist-empty]");
    if (!grid || !emptyState) {
      return;
    }

    const count = grid.querySelectorAll("[data-movie-card]").length;
    const isEmpty = count === 0;
    grid.hidden = isEmpty;
    emptyState.hidden = !isEmpty;

    const total = root.querySelector("[data-watchlist-total]");
    if (total) {
      total.textContent = String(count);
    }

    const totalLabel = root.querySelector("[data-watchlist-total-label]");
    if (totalLabel) {
      totalLabel.textContent = count === 1 ? "movie" : "movies";
    }
  };

  const removeUnwatchedCard = (root, movieId, payload) => {
    if (!root.body?.classList.contains("watchlist-page") || payload.watchlist) {
      return;
    }
    root
      .querySelectorAll(`[data-movie-card][data-movie-id="${movieId}"]`)
      .forEach((card) => card.remove());
    updateWatchlistEmptyState(root);
  };

  window.VaultMoviePreferencesSupport = {
    buildPreferenceLabel,
    getPreferenceState,
    removeUnwatchedCard,
    updatePreferenceButtons,
    updateWatchlistEmptyState,
  };

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-preference-button]");
    if (!button || button.dataset.preferenceBusy === "true") return;

    event.preventDefault();
    event.stopPropagation();

    const movieId = Number(button.dataset.movieId);
    const type = button.dataset.preferenceType;
    if (!Number.isInteger(movieId) || !["like", "watchlist"].includes(type)) {
      return;
    }

    const method = button.classList.contains("is-active") ? "DELETE" : "POST";
    button.dataset.preferenceBusy = "true";
    button.disabled = true;

    try {
      const response = await fetch(`/movies/${movieId}/${type}`, {
        method,
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("Preference update failed");

      const payload = await response.json();
      updatePreferenceButtons(document, movieId, payload);
      removeUnwatchedCard(document, movieId, payload);
      document.dispatchEvent(
        new CustomEvent("vault:preference-updated", {
          detail: { movieId, type, payload },
        }),
      );
    } catch {
      window.showToast?.("Could not update that preference—try again.");
    } finally {
      delete button.dataset.preferenceBusy;
      button.disabled = false;
    }
  });
})();
