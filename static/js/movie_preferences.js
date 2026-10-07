(function () {
  const watchlistStates = new WeakMap();
  const pendingMovies = new Set();

  const isWatchlistPage = (root) =>
    root.body?.classList.contains("watchlist-page");

  const getWatchlistState = (root) => {
    if (!watchlistStates.has(root)) {
      watchlistStates.set(root, { removal: null, notice: null, busy: false });
    }
    return watchlistStates.get(root);
  };

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

  const updateWatchlistEmptyState = (root, savedDelta = 0) => {
    if (!isWatchlistPage(root)) {
      return;
    }

    const grid = root.querySelector("[data-watchlist-grid]");
    const emptyState = root.querySelector("[data-watchlist-empty]");
    if (!grid || !emptyState) {
      return;
    }

    const count = grid.querySelectorAll("[data-movie-card]").length;
    const view = root.querySelector("[data-watchlist-view]");
    const total = root.querySelector("[data-watchlist-total]");
    const previousTotal = Number(
      view?.dataset.watchlistSavedTotal ?? total?.textContent ?? count,
    );
    const savedTotal = Math.max(
      count,
      (Number.isFinite(previousTotal) ? previousTotal : count) + savedDelta,
    );
    if (view) view.dataset.watchlistSavedTotal = String(savedTotal);
    grid.hidden = count === 0;
    emptyState.hidden = savedTotal !== 0;
    const noResults = root.querySelector("[data-watchlist-no-results]");
    if (noResults) noResults.hidden = savedTotal === 0 || count !== 0;

    if (total) {
      total.textContent = String(savedTotal);
    }

    const totalLabel = root.querySelector("[data-watchlist-total-label]");
    if (totalLabel) {
      totalLabel.textContent = savedTotal === 1 ? "movie" : "movies";
    }
    const results = root.querySelector("[data-watchlist-results]");
    if (results) results.textContent = String(count);
    const resultLabel = root.querySelector("[data-watchlist-result-label]");
    if (resultLabel) resultLabel.textContent = count === 1 ? "movie" : "movies";
  };

  const focusWatchlistControl = (root) => {
    const target =
      root.querySelector(
        '[data-watchlist-grid] [data-preference-type="watchlist"]',
      ) ||
      root.querySelector(
        "[data-watchlist-view] input, [data-watchlist-view] a",
      );
    target?.focus();
  };

  const clearRemoval = (state) => {
    state.removal?.entries.forEach(({ placeholder }) => placeholder?.remove());
    state.removal = null;
  };

  const ensureWatchlistNotice = (root) => {
    const state = getWatchlistState(root);
    if (state.notice) return state.notice;
    const grid = root.querySelector("[data-watchlist-grid]");
    if (!grid?.parentNode || !root.createElement) return null;

    const notice = root.createElement("div");
    notice.className = "watchlist-undo";
    notice.dataset.watchlistUndo = "";
    const message = root.createElement("p");
    message.className = "watchlist-undo__message";
    message.setAttribute("role", "status");
    message.setAttribute("aria-live", "polite");
    message.setAttribute("aria-atomic", "true");
    const actions = root.createElement("div");
    actions.className = "watchlist-undo__actions";
    const undo = root.createElement("button");
    undo.type = "button";
    undo.className = "button-primary";
    undo.textContent = "Undo removal";
    undo.dataset.watchlistUndoAction = "undo";
    const dismiss = root.createElement("button");
    dismiss.type = "button";
    dismiss.className = "button-secondary";
    dismiss.textContent = "Dismiss";
    dismiss.dataset.watchlistUndoAction = "dismiss";
    actions.appendChild(undo);
    actions.appendChild(dismiss);
    notice.appendChild(message);
    notice.appendChild(actions);
    grid.parentNode.insertBefore(notice, grid);
    undo.addEventListener("click", () => undoWatchlistRemoval(root));
    dismiss.addEventListener("click", () => {
      if (state.busy) return;
      const needsFocus = notice.contains(root.activeElement);
      clearRemoval(state);
      notice.hidden = true;
      if (needsFocus) focusWatchlistControl(root);
    });
    state.notice = { element: notice, message, undo, dismiss };
    return state.notice;
  };

  const announceWatchlistError = (root, message) => {
    const state = getWatchlistState(root);
    const notice = ensureWatchlistNotice(root);
    if (!notice) return;
    notice.element.hidden = false;
    notice.message.textContent = state.removal
      ? `${message} You can still undo removal of ${state.removal.title}.`
      : message;
    notice.undo.hidden = !state.removal;
  };

  const setWatchlistBusy = (root, busy) => {
    const state = getWatchlistState(root);
    state.busy = busy;
    if (busy) {
      state.busyButtons = Array.from(
        root.querySelectorAll('[data-preference-type="watchlist"]'),
        (button) => [button, button.disabled],
      );
      state.busyButtons.forEach(([button]) => (button.disabled = true));
    } else {
      state.busyButtons?.forEach(([button, disabled]) => {
        button.disabled = disabled;
      });
      state.busyButtons = null;
    }
    if (state.notice) {
      state.notice.undo.disabled = busy;
      state.notice.dismiss.disabled = busy;
    }
  };

  const dispatchPreferenceUpdate = (root, movieId, type, payload) => {
    root.dispatchEvent(
      new CustomEvent("vault:preference-updated", {
        detail: { movieId, type, payload },
      }),
    );
  };

  const requestPreference = async (movieId, type, method) => {
    const response = await fetch(`/movies/${movieId}/${type}`, {
      method,
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error("Preference update failed");
    const payload = await response.json();
    if (
      typeof payload?.liked !== "boolean" ||
      typeof payload?.watchlist !== "boolean" ||
      getPreferenceState(type, payload) !== (method === "POST")
    ) {
      throw new Error("Unexpected preference response");
    }
    return payload;
  };

  const undoWatchlistRemoval = async (root) => {
    const state = getWatchlistState(root);
    const removal = state.removal;
    if (!removal || state.busy || pendingMovies.has(removal.movieId)) return;
    pendingMovies.add(removal.movieId);
    const needsFocus = state.notice.element.contains(root.activeElement);
    setWatchlistBusy(root, true);
    let restored = false;
    try {
      const payload = await requestPreference(
        removal.movieId,
        "watchlist",
        "POST",
      );
      const grid = root.querySelector("[data-watchlist-grid]");
      removal.entries.forEach(({ card, placeholder }) => {
        if (placeholder?.parentNode) {
          placeholder.parentNode.replaceChild(card, placeholder);
        } else if (grid && !card.isConnected) {
          grid.appendChild(card);
        }
      });
      updatePreferenceButtons(root, removal.movieId, payload);
      updateWatchlistEmptyState(root, 1);
      state.removal = null;
      state.notice.undo.hidden = true;
      state.notice.message.textContent = `${removal.title} restored to your watchlist.`;
      dispatchPreferenceUpdate(root, removal.movieId, "watchlist", payload);
      restored = true;
    } catch {
      state.notice.message.textContent = `Could not restore ${removal.title}. Try Undo again.`;
    } finally {
      pendingMovies.delete(removal.movieId);
      setWatchlistBusy(root, false);
      if (
        needsFocus &&
        (root.activeElement === root.body ||
          state.notice.element.contains(root.activeElement))
      ) {
        if (!restored) state.notice.undo.focus();
        else if (removal.trigger?.isConnected) removal.trigger.focus();
        else focusWatchlistControl(root);
      }
    }
  };

  const removeUnwatchedCard = (root, movieId, payload, trigger = null) => {
    if (!isWatchlistPage(root) || payload.watchlist) {
      return;
    }
    const cards = Array.from(
      root.querySelectorAll(`[data-movie-card][data-movie-id="${movieId}"]`),
    );
    if (!cards.length) return;
    const state = getWatchlistState(root);
    clearRemoval(state);
    const notice = ensureWatchlistNotice(root);
    const entries = cards.map((card) => {
      const placeholder = root.createComment?.("watchlist removal");
      if (placeholder && card.parentNode) {
        card.parentNode.insertBefore(placeholder, card);
      }
      card.remove();
      return { card, placeholder };
    });
    updateWatchlistEmptyState(root, -1);
    if (!notice) return;
    const title = trigger?.dataset.movieTitle || "Movie";
    state.removal = { movieId, title, entries, trigger };
    notice.element.hidden = false;
    notice.message.textContent = `${title} removed from your watchlist. Undo is available until you dismiss it, remove another movie, or leave this page.`;
    notice.undo.hidden = false;
    notice.undo.disabled = state.busy;
    notice.dismiss.disabled = state.busy;
    notice.undo.setAttribute("aria-label", `Undo removal of ${title}`);
    return state.removal;
  };

  window.VaultMoviePreferencesSupport = {
    buildPreferenceLabel,
    getPreferenceState,
    removeUnwatchedCard,
    undoWatchlistRemoval,
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
    if (
      !Number.isInteger(movieId) ||
      !["like", "watchlist"].includes(type) ||
      pendingMovies.has(movieId)
    ) {
      return;
    }

    const watchlistRequest = isWatchlistPage(document) && type === "watchlist";
    if (watchlistRequest && getWatchlistState(document).busy) return;

    const method = button.classList.contains("is-active") ? "DELETE" : "POST";
    const hadFocus = button === document.activeElement;
    const wasDisabled = button.disabled;
    pendingMovies.add(movieId);
    if (watchlistRequest) setWatchlistBusy(document, true);
    button.dataset.preferenceBusy = "true";
    button.disabled = true;
    let removal = null;

    try {
      const payload = await requestPreference(movieId, type, method);
      const needsFocus =
        hadFocus &&
        (document.activeElement === button ||
          document.activeElement === document.body);
      updatePreferenceButtons(document, movieId, payload);
      removal = removeUnwatchedCard(document, movieId, payload, button);
      if (removal) removal.needsFocus = needsFocus;
      dispatchPreferenceUpdate(document, movieId, type, payload);
    } catch {
      if (watchlistRequest) {
        announceWatchlistError(
          document,
          "Could not update your watchlist. Try again.",
        );
      } else {
        window.showToast?.("Could not update that preference—try again.");
      }
    } finally {
      pendingMovies.delete(movieId);
      if (watchlistRequest) setWatchlistBusy(document, false);
      delete button.dataset.preferenceBusy;
      button.disabled = wasDisabled;
      if (removal?.needsFocus) {
        getWatchlistState(document).notice.undo.focus();
      } else if (hadFocus && document.activeElement === document.body) {
        button.focus();
      }
    }
  });
})();
