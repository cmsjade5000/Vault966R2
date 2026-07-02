(function () {
  const parseGenresInput = (value = "") =>
    value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

  const arraysEqualCaseInsensitive = (left, right) => {
    if (!Array.isArray(left) || !Array.isArray(right)) return false;
    if (left.length !== right.length) return false;
    const normalize = (items) =>
      items.map((item) => String(item).toLowerCase()).sort();
    return normalize(left).every(
      (value, index) => value === normalize(right)[index],
    );
  };

  const buildMovieUpdate = (detail, values) => {
    const payload = {};
    const title = values.title.trim();
    if (!title) throw new Error("Title cannot be empty.");
    if (title !== (detail.title || "")) payload.title = title;

    ["year", "runtime"].forEach((key) => {
      const raw = values[key].trim();
      if (!raw) return;
      const parsed = Number.parseInt(raw, 10);
      if (Number.isFinite(parsed) && parsed !== (detail[key] ?? null)) {
        payload[key] = parsed;
      }
    });

    ["plot", "poster_url"].forEach((key) => {
      const value = values[key].trim();
      if (value !== (detail[key] || "")) payload[key] = value;
    });

    const genres = parseGenresInput(values.genres);
    if (!arraysEqualCaseInsensitive(genres, detail.genres || [])) {
      payload.genres = genres;
    }
    return payload;
  };

  window.VaultMovieDetailEditSupport = {
    arraysEqualCaseInsensitive,
    buildMovieUpdate,
    parseGenresInput,
  };

  document.addEventListener("DOMContentLoaded", () => {
    const dialog = document.querySelector("[data-edit-dialog]");
    const form = document.getElementById("edit-form");
    if (!dialog || !form) return;

    const fields = {
      movieId: document.getElementById("edit-movie-id"),
      title: document.getElementById("edit-title"),
      year: document.getElementById("edit-year"),
      runtime: document.getElementById("edit-runtime"),
      posterUrl: document.getElementById("edit-poster"),
      genres: document.getElementById("edit-genres"),
      plot: document.getElementById("edit-plot"),
    };
    const status = document.getElementById("edit-status");
    const submitButton = document.getElementById("edit-submit");
    const deleteButton = document.getElementById("edit-delete-button");
    const lookupButton = document.getElementById("edit-lookup-button");
    const lookupRetryButton = document.getElementById("edit-lookup-retry");
    const lookupHint = document.getElementById("edit-lookup-hint");
    const lookupEmpty = document.getElementById("edit-lookup-empty");
    const lookupCards = document.getElementById("edit-lookup-cards");
    const lookupResults = document.getElementById("edit-lookup-results");
    const lookupBody = document.getElementById("edit-lookup-results-body");
    let currentDetail = null;
    let currentMovieId = null;
    let lookupRequestId = 0;

    const setStatus = (message, isError = false) => {
      if (!status) return;
      status.textContent = message;
      status.hidden = !message;
      status.classList.toggle("is-error", isError);
    };

    const setPending = (button, pending) => {
      if (!button) return;
      button.disabled = pending;
      button.toggleAttribute("aria-busy", pending);
    };

    const authFetch = (url, options) => fetch(url, options);

    const clearLookup = () => {
      lookupRequestId += 1;
      lookupBody?.replaceChildren();
      lookupCards?.replaceChildren();
      if (lookupResults) lookupResults.hidden = true;
      if (lookupCards) lookupCards.hidden = true;
      if (lookupHint) lookupHint.hidden = true;
      if (lookupEmpty) lookupEmpty.hidden = true;
      if (lookupRetryButton) lookupRetryButton.hidden = true;
    };

    const resetForm = () => {
      form.reset();
      if (fields.movieId) fields.movieId.value = "";
      setStatus("");
      clearLookup();
    };

    const closeDialog = ({ restoreFocus = false } = {}) => {
      dialogController?.close({ restoreFocus });
    };

    const dialogController = window.VaultDialog?.bind(dialog, {
      closeSelector: "[data-edit-close], [data-edit-cancel]",
      onClose: () => {
        resetForm();
        currentDetail = null;
        currentMovieId = null;
      },
    });

    const populateForm = (detail) => {
      currentDetail = detail;
      if (fields.movieId) fields.movieId.value = String(detail.id);
      if (fields.title) fields.title.value = detail.title || "";
      if (fields.year) fields.year.value = detail.year ?? "";
      if (fields.runtime) fields.runtime.value = detail.runtime ?? "";
      if (fields.posterUrl) fields.posterUrl.value = detail.poster_url || "";
      if (fields.genres) fields.genres.value = (detail.genres || []).join(", ");
      if (fields.plot) fields.plot.value = detail.plot || "";
    };

    const applyCandidate = (candidate) => {
      if (fields.title) fields.title.value = candidate.title || "";
      if (fields.year) fields.year.value = candidate.year ?? "";
      if (fields.runtime) fields.runtime.value = candidate.runtime ?? "";
      if (fields.posterUrl) fields.posterUrl.value = candidate.poster_url || "";
      if (fields.genres)
        fields.genres.value = (candidate.genres || []).join(", ");
      if (fields.plot)
        fields.plot.value = candidate.synopsis || candidate.overview || "";
      setStatus(`Applied details from "${candidate.title || "match"}".`);
    };

    const candidateAction = (candidate) => {
      if (candidate.source === "vault" || candidate.vault_id) {
        const link = document.createElement("a");
        link.className = "button-ghost";
        link.href = `/ui/movies/${candidate.vault_id}`;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = "Open";
        return link;
      }
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button-ghost";
      button.textContent = "Replace";
      button.addEventListener("click", () => applyCandidate(candidate));
      return button;
    };

    const renderCandidateCard = (candidate) => {
      const card = document.createElement("div");
      card.className = "edit-lookup-card";

      const poster = document.createElement("div");
      poster.className = "edit-lookup-card__poster";
      if (candidate.poster_url) {
        const image = document.createElement("img");
        image.src = candidate.poster_url;
        image.alt = `${candidate.title || "Match"} poster`;
        image.loading = "lazy";
        poster.append(image);
      } else {
        poster.textContent = "—";
      }

      const info = document.createElement("div");
      info.className = "edit-lookup-card__info";
      const title = document.createElement("div");
      title.className = "edit-lookup-card__title";
      title.textContent = candidate.title || "Untitled";
      const meta = document.createElement("div");
      meta.className = "edit-lookup-card__meta";
      const parts = [
        candidate.year || "—",
        candidate.runtime ? `${candidate.runtime} min` : "—",
      ];
      if (Number.isFinite(candidate.match_confidence)) {
        parts.push(`${Math.round(candidate.match_confidence * 100)}% match`);
      }
      meta.textContent = parts.join(" • ");
      info.append(title, meta);

      const action = document.createElement("div");
      action.className = "edit-lookup-card__action";
      action.append(candidateAction(candidate));
      card.append(poster, info, action);
      return card;
    };

    const renderCandidateRow = (candidate) => {
      const row = document.createElement("tr");
      const values = [
        candidate.poster_url ? "Poster available" : "—",
        candidate.title || "Untitled",
        candidate.year || "—",
        candidate.runtime ? `${candidate.runtime} min` : "—",
        Number.isFinite(candidate.match_confidence)
          ? `${Math.round(candidate.match_confidence * 100)}%`
          : "—",
        [
          candidate.vault_label,
          candidate.tmdb_id ? `TMDb ${candidate.tmdb_id}` : "",
          candidate.imdb_id ? `IMDb ${candidate.imdb_id}` : "",
        ]
          .filter(Boolean)
          .join(" • ") || "—",
        candidate.synopsis || "—",
      ];
      values.forEach((value, index) => {
        const cell = document.createElement("td");
        if (index === 0 && candidate.poster_url) {
          const image = document.createElement("img");
          image.className = "edit-lookup-poster";
          image.src = candidate.poster_url;
          image.alt = `${candidate.title || "Match"} poster`;
          image.loading = "lazy";
          cell.replaceChildren(image);
        } else {
          cell.textContent = String(value);
        }
        row.append(cell);
      });
      const action = document.createElement("td");
      action.className = "edit-lookup-table__actions";
      action.append(candidateAction(candidate));
      row.append(action);
      return row;
    };

    const renderCandidates = (items, message = "") => {
      lookupBody?.replaceChildren(...items.map(renderCandidateRow));
      lookupCards?.replaceChildren(...items.map(renderCandidateCard));
      const cardsOnly = window.matchMedia("(max-width: 900px)").matches;
      if (lookupResults) lookupResults.hidden = cardsOnly || !items.length;
      if (lookupCards) lookupCards.hidden = !cardsOnly || !items.length;
      if (lookupHint) lookupHint.hidden = !items.length;
      if (lookupEmpty) {
        lookupEmpty.textContent =
          message || "No matches found—try adjusting the title or year.";
        lookupEmpty.hidden = Boolean(items.length);
      }
    };

    const findMatches = async () => {
      if (!currentMovieId) return;
      const requestId = ++lookupRequestId;
      const params = new URLSearchParams({ limit: "5" });
      const title = fields.title?.value.trim();
      const year = fields.year?.value.trim();
      if (title) params.set("title", title);
      if (year) params.set("year", year);

      setPending(lookupButton, true);
      setPending(lookupRetryButton, true);
      setStatus("Finding matches…");
      try {
        const response = await fetch(
          `/movies/${currentMovieId}/lookup?${params.toString()}`,
          { headers: { Accept: "application/json" } },
        );
        if (requestId !== lookupRequestId) return;
        if (!response.ok) {
          renderCandidates(
            [],
            "No matches found—try adjusting the title or year.",
          );
          setStatus("No matches found—try adjusting the title or year.", true);
          return;
        }
        const payload = await response.json();
        const items = Array.isArray(payload.items) ? payload.items : [];
        renderCandidates(items, payload.notice || "");
        setStatus(
          items.length
            ? `Found ${items.length} ${items.length === 1 ? "match" : "matches"}.`
            : payload.notice || "No matches found.",
          !items.length && !payload.notice,
        );
      } catch {
        renderCandidates(
          [],
          "Lookup failed—check your connection and try again.",
        );
        setStatus("Lookup failed—check your connection and try again.", true);
      } finally {
        if (requestId === lookupRequestId) {
          setPending(lookupButton, false);
          setPending(lookupRetryButton, false);
          if (lookupRetryButton) lookupRetryButton.hidden = false;
        }
      }
    };

    const openDialog = async (button) => {
      const movieId = Number(button.dataset.movieId);
      if (!Number.isInteger(movieId)) return;
      currentMovieId = movieId;
      resetForm();
      currentMovieId = movieId;
      dialogController?.open(button);
      setPending(submitButton, true);
      setStatus("Loading metadata…");
      try {
        const response = await fetch(`/movies/${movieId}/detail`, {
          headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error("Detail request failed");
        populateForm(await response.json());
        setStatus("");
        fields.title?.focus();
        findMatches();
      } catch {
        closeDialog();
        window.showToast?.({
          label: "Load failed",
          message: "Movie metadata could not load. Try again.",
          tone: "error",
        });
      } finally {
        setPending(submitButton, false);
      }
    };

    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-edit-button]");
      if (button) openDialog(button);
    });
    lookupButton?.addEventListener("click", findMatches);
    lookupRetryButton?.addEventListener("click", findMatches);

    deleteButton?.addEventListener("click", async () => {
      if (!currentMovieId || !currentDetail) return;
      const title = fields.title?.value.trim() || currentDetail.title;
      if (
        !window.confirm(
          `Delete "${title}" from Vault 966? This cannot be undone.`,
        )
      ) {
        return;
      }
      setPending(deleteButton, true);
      setStatus("Deleting movie…");
      try {
        const response = await authFetch(`/movies/${currentMovieId}`, {
          method: "DELETE",
        });
        if (!response.ok && response.status !== 204) {
          throw new Error("Delete failed");
        }
        window.location.assign("/ui/movies");
      } catch {
        setStatus("Could not delete that movie—try again?", true);
      } finally {
        setPending(deleteButton, false);
      }
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!currentMovieId || !currentDetail) return;

      let payload;
      try {
        payload = buildMovieUpdate(currentDetail, {
          title: fields.title?.value || "",
          year: fields.year?.value || "",
          runtime: fields.runtime?.value || "",
          poster_url: fields.posterUrl?.value || "",
          genres: fields.genres?.value || "",
          plot: fields.plot?.value || "",
        });
      } catch (error) {
        setStatus(error.message, true);
        fields.title?.focus();
        return;
      }

      if (!Object.keys(payload).length) {
        window.showToast?.({
          label: "No changes",
          message: "Nothing changed, so the movie was left as-is.",
          tone: "notice",
        });
        closeDialog({ restoreFocus: true });
        return;
      }

      setPending(submitButton, true);
      setStatus("Saving changes…");
      try {
        const response = await authFetch(`/movies/${currentMovieId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error("Update failed");
        window.showToast?.({
          label: "Movie updated",
          message: "Changes saved to the Vault.",
          tone: "success",
        });
        window.location.reload();
      } catch {
        setStatus("Could not save changes—try again?", true);
      } finally {
        setPending(submitButton, false);
      }
    });
  });
})();
