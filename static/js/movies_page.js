(function () {
  document.addEventListener("DOMContentLoaded", () => {
    const pageDataElement = document.getElementById("movies-page-data");
    let pageData = {};
    if (pageDataElement) {
      try {
        pageData = JSON.parse(pageDataElement.textContent || "{}");
      } catch (error) {
        console.warn("Failed to parse movies page data", error);
        pageData = {};
      }
    } else {
      pageData = window.__moviesPageData || {};
    }
    const form = document.getElementById("filters-form");
    const formBaseAction =
      (form && form.dataset.baseAction) ||
      (form?.action ? form.action.split("#")[0] : "") ||
      "/ui/movies";
    const heroStats = document.querySelector("[data-hero-stats]");
    const filtersDialog = document.querySelector("[data-filters-dialog]");
    const filtersOpenButton = document.querySelector("[data-filters-open]");
    const filtersCloseButton = document.querySelector("[data-filters-close]");
    const filtersApplyButton = document.querySelector("[data-filters-apply]");
    const filtersSummaryEl = document.querySelector("[data-filters-summary]");
    const editDialog = document.querySelector("[data-edit-dialog]");
    const editForm = document.getElementById("edit-form");
    const editMovieIdInput = document.getElementById("edit-movie-id");
    const editTitleInput = document.getElementById("edit-title");
    const editYearInput = document.getElementById("edit-year");
    const editRuntimeInput = document.getElementById("edit-runtime");
    const editPosterInput = document.getElementById("edit-poster");
    const editGenresInput = document.getElementById("edit-genres");
    const editPlotInput = document.getElementById("edit-plot");
    const editResolveInput = document.getElementById("edit-resolve-flag");
    const editStatusEl = document.getElementById("edit-status");
    const editSubmitButton = document.getElementById("edit-submit");
    const editCancelButton = document.querySelector("[data-edit-cancel]");
    const editCloseButton = document.querySelector("[data-edit-close]");
    const editLookupButton = document.getElementById("edit-lookup-button");
    const editLookupRetryButton = document.getElementById("edit-lookup-retry");
    const editLookupResults = document.getElementById("edit-lookup-results");
    const editLookupResultsBody = document.getElementById(
      "edit-lookup-results-body",
    );
    const heroPickButtons = document.querySelectorAll("[data-hero-pick]");
    const heroHistoryButtons = document.querySelectorAll("[data-hero-history]");
    const aiSearchForm = document.querySelector("[data-ai-search-form]");
    const aiSearchInput = document.getElementById("ai-search-input");
    const aiSearchStatus = document.querySelector("[data-ai-status]");
    const aiPlanContainer = document.querySelector("[data-ai-plan]");
    const aiPlanSummary = document.querySelector("[data-ai-summary]");
    const aiApplyButton = document.querySelector("[data-ai-apply]");
    const aiSubmitButton = document.querySelector("[data-ai-submit]");
    const resultsShell = document.querySelector("[data-results-shell]");
    const resultsTableSection = document.querySelector("[data-results-table]");
    const resultsPager = document.querySelector("[data-results-pager]");
    const resultsEmpty = document.querySelector("[data-results-empty]");
    const resultsEmptyMessage = resultsEmpty
      ? resultsEmpty.querySelector("p")
      : null;
    const resultsEmptyDefault = resultsEmptyMessage
      ? resultsEmptyMessage.textContent
      : "";
    let resultsGrid = document.querySelector("[data-results-grid]");

    let currentEditMovieId = null;
    let currentEditDetail = null;
    let lastEditTrigger = null;
    let currentLookupCandidates = [];
    let lookupRequestToken = 0;
    let aiRequestToken = 0;
    let lastAiPlan = null;

    const isDesktop = () => window.matchMedia("(min-width: 900px)").matches;
    let previousOverflow = document.body.style.overflow || "";

    const lockScroll = () => {
      previousOverflow = document.body.style.overflow || "";
      document.body.style.overflow = "hidden";
    };

    const unlockScroll = () => {
      document.body.style.overflow = previousOverflow;
    };

    const closeFilters = ({ restoreFocus = false } = {}) => {
      if (!filtersDialog) return;
      if (isDesktop()) {
        filtersDialog.setAttribute("aria-hidden", "false");
        if (filtersApplyButton) filtersApplyButton.hidden = true;
        unlockScroll();
        return;
      }
      if (!filtersDialog.classList.contains("is-open")) return;
      filtersDialog.classList.remove("is-open");
      filtersDialog.setAttribute("aria-hidden", "true");
      if (filtersApplyButton) filtersApplyButton.hidden = true;
      unlockScroll();
      if (restoreFocus && filtersOpenButton) {
        filtersOpenButton.focus();
      }
    };

    const openFilters = () => {
      if (!filtersDialog || isDesktop()) {
        return;
      }
      filtersDialog.classList.add("is-open");
      filtersDialog.setAttribute("aria-hidden", "false");
      if (filtersApplyButton) filtersApplyButton.hidden = false;
      lockScroll();
    };

    const syncHeroStats = () => {
      if (!heroStats) return;
      if (heroStats.tagName === "DETAILS") {
        if (isDesktop()) {
          heroStats.setAttribute("open", "");
        } else {
          heroStats.removeAttribute("open");
        }
      }
    };

    const syncDialogToViewport = () => {
      if (!filtersDialog) return;
      if (isDesktop()) {
        filtersDialog.classList.remove("is-open");
        filtersDialog.setAttribute("aria-hidden", "false");
        if (filtersApplyButton) filtersApplyButton.hidden = true;
        unlockScroll();
      } else if (!filtersDialog.classList.contains("is-open")) {
        filtersDialog.setAttribute("aria-hidden", "true");
      }
      syncHeroStats();
    };

    filtersOpenButton?.addEventListener("click", () => {
      openFilters();
    });

    filtersCloseButton?.addEventListener("click", () => {
      closeFilters({ restoreFocus: true });
    });

    filtersDialog?.addEventListener("click", (event) => {
      if (event.target === filtersDialog && !isDesktop()) {
        closeFilters({ restoreFocus: true });
      }
    });

    const scrollToHistory = () => {
      const memorySection = document.getElementById("flic-memory");
      if (memorySection) {
        memorySection.open = true;
        memorySection.scrollIntoView({ behavior: "smooth", block: "start" });
      } else if (window.location.pathname !== "/ui/movies") {
        window.location.href = "/ui/movies#flic-memory";
      }
    };

    const setActionBusy = (element, { busyLabel = "Working…" } = {}) => {
      if (!element || element.dataset.busyState === "true") {
        return () => {};
      }
      const labelTarget = element.querySelector("[data-action-label]");
      const originalText = labelTarget
        ? labelTarget.textContent
        : element.textContent;
      element.dataset.busyState = "true";
      element.dataset.busyLabelTarget = labelTarget ? "child" : "self";
      element.dataset.busyOriginal = originalText ?? "";
      const applyText = (value) => {
        if (labelTarget) {
          labelTarget.textContent = value;
        } else {
          element.textContent = value;
        }
      };
      element.classList.add("is-busy");
      element.setAttribute("aria-busy", "true");
      if ("disabled" in element) {
        element.disabled = true;
      }
      applyText(busyLabel);
      return () => {
        if (!element.dataset.busyState) return;
        applyText(element.dataset.busyOriginal || "");
        element.classList.remove("is-busy");
        element.removeAttribute("aria-busy");
        if ("disabled" in element) {
          element.disabled = false;
        }
        delete element.dataset.busyState;
        delete element.dataset.busyLabelTarget;
        delete element.dataset.busyOriginal;
      };
    };

    const setAiStatus = (message, isError = false) => {
      if (!aiSearchStatus) return;
      aiSearchStatus.textContent = message || "";
      aiSearchStatus.hidden = !message;
      aiSearchStatus.classList.toggle("is-error", Boolean(isError));
    };

    const ensureResultsGrid = () => {
      if (resultsGrid) return resultsGrid;
      if (!resultsShell) return null;
      const grid = document.createElement("div");
      grid.className = "grid";
      grid.dataset.resultsGrid = "true";
      resultsShell.prepend(grid);
      resultsGrid = grid;
      return grid;
    };

    const formatRating = (value, digits) => {
      if (typeof value !== "number" || !Number.isFinite(value)) return null;
      return value.toFixed(digits);
    };

    const buildMovieCard = (movie) => {
      const card = document.createElement("article");
      const flagged = Boolean(movie?.flagged);
      card.className = `card${flagged ? " card--flagged" : ""}`;
      card.dataset.movieCard = "true";
      card.dataset.movieId = String(movie.id);
      card.dataset.flagged = flagged ? "true" : "false";

      const link = document.createElement("a");
      link.className = "card-link";
      link.href = `/ui/movies/${movie.id}`;

      const media = document.createElement("div");
      media.className = "card-media";
      if (movie.poster_url) {
        const img = document.createElement("img");
        img.className = "poster";
        img.src = movie.poster_url;
        img.alt = `${movie.title} poster`;
        img.loading = "lazy";
        media.appendChild(img);
      } else {
        const poster = document.createElement("div");
        poster.className = "poster poster--empty poster-theme-default";
        poster.setAttribute("aria-hidden", "true");
        poster.textContent = "🍿";
        media.appendChild(poster);
      }
      link.appendChild(media);

      const body = document.createElement("div");
      body.className = "card-body";

      const titleRow = document.createElement("div");
      titleRow.className = "card-title-row";
      const title = document.createElement("h2");
      title.className = "card-title";
      title.textContent = movie.title || "Untitled";
      titleRow.appendChild(title);
      if (flagged) {
        const status = document.createElement("span");
        status.className = "card-status card-status--flagged";
        status.textContent = "Needs review";
        titleRow.appendChild(status);
      }
      body.appendChild(titleRow);

      const statline = document.createElement("div");
      statline.className = "card-statline";
      statline.setAttribute("aria-label", "Movie details");

      if (movie.year) {
        const stat = document.createElement("span");
        stat.className = "card-stat";
        stat.textContent = String(movie.year);
        statline.appendChild(stat);
      }
      if (movie.runtime) {
        const stat = document.createElement("span");
        stat.className = "card-stat";
        stat.textContent = `${movie.runtime} min`;
        statline.appendChild(stat);
      }
      const imdb = formatRating(movie.imdb_rating, 1);
      if (imdb) {
        const stat = document.createElement("span");
        stat.className = "card-stat card-stat--rating";
        stat.title = "IMDb rating";
        stat.textContent = imdb;
        statline.appendChild(stat);
      }
      if (typeof movie.rt_score === "number") {
        const stat = document.createElement("span");
        stat.className = "card-stat card-stat--rating";
        stat.title = "Rotten Tomatoes score";
        stat.textContent = `${movie.rt_score}%`;
        statline.appendChild(stat);
      }
      body.appendChild(statline);

      const genres = Array.isArray(movie.genres)
        ? movie.genres
            .map((genre) => (typeof genre === "string" ? genre : genre?.name))
            .filter(Boolean)
        : [];
      if (genres.length) {
        const chips = document.createElement("div");
        chips.className = "card-chips";
        chips.setAttribute("aria-label", "Genres");
        genres.slice(0, 3).forEach((label) => {
          const chip = document.createElement("span");
          chip.className = "card-chip";
          chip.textContent = label;
          chips.appendChild(chip);
        });
        body.appendChild(chips);
      }

      link.appendChild(body);
      card.appendChild(link);

      return card;
    };

    const renderAiResults = (items = []) => {
      const grid = ensureResultsGrid();
      if (!grid) return;
      grid.innerHTML = "";
      if (Array.isArray(items)) {
        items.forEach((movie) => {
          if (!movie || !movie.id) return;
          grid.appendChild(buildMovieCard(movie));
        });
      }

      const hasItems = Array.isArray(items) && items.length > 0;
      grid.hidden = !hasItems;
      if (resultsEmpty) {
        resultsEmpty.hidden = hasItems;
        if (resultsEmptyMessage) {
          resultsEmptyMessage.textContent = hasItems
            ? resultsEmptyDefault || resultsEmptyMessage.textContent
            : "No matches from AI search yet.";
        }
      }
      resultsTableSection?.setAttribute("hidden", "");
      resultsPager?.setAttribute("hidden", "");
      attachFlagButtons();
      attachEditButtons();
      if (resultsShell) {
        resultsShell.dataset.aiActive = "true";
      }
    };

    const runQuickPick = (indicator) => {
      const releaseBusy = indicator
        ? setActionBusy(indicator, { busyLabel: "Picking…" })
        : () => {};
      if (typeof window.runFlicPick === "function") {
        return Promise.resolve(window.runFlicPick({ indicator })).finally(
          releaseBusy,
        );
      }
      window.location.href = "/ui/movies";
      releaseBusy();
      return null;
    };

    const forEachNode = (nodeList, callback) => {
      if (!nodeList || typeof callback !== "function") {
        return;
      }
      Array.prototype.forEach.call(nodeList, callback);
    };

    forEachNode(heroPickButtons, (button) => {
      button.addEventListener("click", () => runQuickPick(button));
    });

    forEachNode(heroHistoryButtons, (button) => {
      button.addEventListener("click", scrollToHistory);
    });

    const dialogMediaQuery = window.matchMedia("(min-width: 900px)");
    dialogMediaQuery.addEventListener("change", syncDialogToViewport);
    syncDialogToViewport();
    const taglines = Array.isArray(pageData.taglines) ? pageData.taglines : [];
    let current = taglines.indexOf(pageData.initialTagline);
    if (current < 0) current = 0;
    const taglineEl = document.getElementById("tagline");
    if (taglines.length && taglineEl) {
      setInterval(() => {
        current = (current + 1) % taglines.length;
        taglineEl.textContent = taglines[current];
      }, 12000);
    }

    const pageContext = pageData.pageContext || "grid";
    const total = Number(pageData.total ?? 0);
    const totalPages = Number(pageData.totalPages ?? 0);
    let currentPage = Number(pageData.page ?? 1);
    if (!Number.isFinite(currentPage) || currentPage < 1) currentPage = 1;

    const ADMIN_TOKEN_KEY = "vaultAdminToken";
    const getAdminToken = () => {
      try {
        return sessionStorage.getItem(ADMIN_TOKEN_KEY) || "";
      } catch (error) {
        console.warn("Failed to read admin token", error);
        return "";
      }
    };

    const setAdminToken = (token) => {
      try {
        if (token) {
          sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
        } else {
          sessionStorage.removeItem(ADMIN_TOKEN_KEY);
        }
      } catch (error) {
        console.warn("Failed to persist admin token", error);
      }
    };

    const promptForAdminToken = (message) => {
      const input = window.prompt(
        message || "Enter admin token to continue.",
        getAdminToken() || "",
      );
      if (input === null) return null;
      const trimmed = input.trim();
      setAdminToken(trimmed);
      return trimmed || null;
    };

    const withAdminAuth = (headers = {}) => {
      const token = getAdminToken();
      return token ? { ...headers, Authorization: `Bearer ${token}` } : headers;
    };

    const parseErrorDetail = async (response) => {
      if (!response || typeof response.json !== "function") return null;
      try {
        const payload = await response.json();
        if (payload && typeof payload.detail === "string") {
          return payload.detail;
        }
      } catch (error) {
        return null;
      }
      return null;
    };

    const authFetch = async (url, options = {}, { authPrompt } = {}) => {
      const mergedOptions = {
        ...options,
        headers: withAdminAuth(options.headers || {}),
      };
      const response = await fetch(url, mergedOptions);
      if (response.status !== 401) {
        return response;
      }
      const token = promptForAdminToken(
        authPrompt || "Admin token required for this action.",
      );
      if (!token) {
        return response;
      }
      return fetch(url, {
        ...options,
        headers: withAdminAuth(options.headers || {}),
      });
    };

    const showToastMessage = (message) => {
      if (typeof window.showToast === "function") {
        window.showToast(message);
      }
    };

    const copyToClipboard = async (text) => {
      if (!text) return false;
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(text);
          return true;
        }
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.setAttribute("aria-hidden", "true");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
        return true;
      } catch (error) {
        console.warn("Clipboard copy failed", error);
        return false;
      }
    };
    if (pageContext === "grid" && typeof window.showToast === "function") {
      if (Number.isFinite(total) && total > 0) {
        showToastMessage(`I found ${total} titles.`);
      } else if (Number.isFinite(total)) {
        showToastMessage("Nothing matched—want me to widen the net?");
      }
    }

    const resetEditStatus = () => {
      if (!editStatusEl) return;
      editStatusEl.textContent = "";
      editStatusEl.hidden = true;
      editStatusEl.classList.remove("is-error");
    };

    const setEditStatus = (message, isError = false) => {
      if (!editStatusEl) return;
      editStatusEl.textContent = message;
      editStatusEl.hidden = !message;
      editStatusEl.classList.toggle("is-error", Boolean(isError));
    };

    const clearLookupResults = ({ hideRetry = false } = {}) => {
      currentLookupCandidates = [];
      if (editLookupResultsBody) {
        editLookupResultsBody.innerHTML = "";
      }
      if (editLookupResults) {
        editLookupResults.hidden = true;
      }
      if (hideRetry && editLookupRetryButton) {
        editLookupRetryButton.hidden = true;
      }
    };

    const setLookupButtonsPending = (pending) => {
      const buttons = [editLookupButton, editLookupRetryButton];
      buttons.forEach((button) => {
        if (!button) return;
        button.disabled = pending;
        if (pending) {
          button.setAttribute("aria-busy", "true");
        } else {
          button.removeAttribute("aria-busy");
        }
      });
    };

    const applyLookupCandidate = (candidate) => {
      if (!candidate) return;
      if (editTitleInput) editTitleInput.value = candidate.title ?? "";
      if (editYearInput)
        editYearInput.value =
          candidate.year !== null && candidate.year !== undefined
            ? String(candidate.year)
            : "";
      if (editRuntimeInput)
        editRuntimeInput.value =
          candidate.runtime !== null && candidate.runtime !== undefined
            ? String(candidate.runtime)
            : "";
      if (editPosterInput) editPosterInput.value = candidate.poster_url || "";
      if (editPlotInput)
        editPlotInput.value = candidate.synopsis || candidate.overview || "";
      if (editGenresInput && Array.isArray(candidate.genres)) {
        editGenresInput.value = candidate.genres.join(", ");
      }
      setEditStatus(`Applied details from "${candidate.title || "match"}".`);
    };

    const renderLookupCandidates = (candidates) => {
      if (!editLookupResultsBody || !editLookupResults) return;
      editLookupResultsBody.innerHTML = "";

      if (!Array.isArray(candidates) || !candidates.length) {
        editLookupResults.hidden = true;
        return;
      }

      candidates.forEach((candidate, index) => {
        const row = document.createElement("tr");

        const titleCell = document.createElement("td");
        const titleStrong = document.createElement("strong");
        titleStrong.textContent = candidate.title || "Untitled";
        titleCell.appendChild(titleStrong);
        row.appendChild(titleCell);

        const yearCell = document.createElement("td");
        yearCell.textContent =
          candidate.year !== null && candidate.year !== undefined
            ? String(candidate.year)
            : "—";
        row.appendChild(yearCell);

        const runtimeCell = document.createElement("td");
        runtimeCell.textContent = candidate.runtime
          ? `${candidate.runtime} min`
          : "—";
        row.appendChild(runtimeCell);

        const idsCell = document.createElement("td");
        const ids = [];
        if (candidate.tmdb_id) ids.push(`TMDb ${candidate.tmdb_id}`);
        if (candidate.imdb_id) ids.push(`IMDb ${candidate.imdb_id}`);
        idsCell.textContent = ids.length ? ids.join(" • ") : "—";
        row.appendChild(idsCell);

        const synopsisCell = document.createElement("td");
        synopsisCell.textContent = candidate.synopsis || "—";
        row.appendChild(synopsisCell);

        const actionsCell = document.createElement("td");
        actionsCell.className = "edit-lookup-table__actions";
        const applyButton = document.createElement("button");
        applyButton.type = "button";
        applyButton.className = "button-ghost";
        applyButton.textContent = "Use";
        applyButton.addEventListener("click", () => {
          applyLookupCandidate(currentLookupCandidates[index]);
        });
        actionsCell.appendChild(applyButton);
        row.appendChild(actionsCell);

        editLookupResultsBody.appendChild(row);
      });

      editLookupResults.hidden = false;
    };

    const fetchLookupCandidates = async () => {
      if (!currentEditMovieId) return;

      const params = new URLSearchParams();
      const titleValue = editTitleInput?.value?.trim();
      if (titleValue) {
        params.set("title", titleValue);
      }
      const yearValueRaw = editYearInput?.value?.trim();
      if (yearValueRaw) {
        const parsedYear = Number.parseInt(yearValueRaw, 10);
        if (!Number.isNaN(parsedYear)) {
          params.set("year", String(parsedYear));
        }
      }
      params.set("limit", "5");

      const query = params.toString();
      const requestId = ++lookupRequestToken;

      setLookupButtonsPending(true);
      setEditStatus("Finding matches…");

      try {
        const response = await fetch(
          query
            ? `/movies/${currentEditMovieId}/lookup?${query}`
            : `/movies/${currentEditMovieId}/lookup`,
          {
            headers: { Accept: "application/json" },
          },
        );

        if (requestId !== lookupRequestToken) {
          return;
        }

        if (response.status === 404) {
          clearLookupResults();
          setEditStatus(
            "No matches found—try adjusting the title or year.",
            true,
          );
          return;
        }

        if (response.status === 503) {
          setEditStatus("Lookup service is temporarily unavailable.", true);
          return;
        }

        if (!response.ok) {
          setEditStatus(`Lookup failed (${response.status}).`, true);
          return;
        }

        const payload = await response.json();
        const items = Array.isArray(payload?.items) ? payload.items : [];
        currentLookupCandidates = items;
        renderLookupCandidates(items);
        if (items.length) {
          setEditStatus(
            items.length === 1
              ? "Found 1 match."
              : `Found ${items.length} matches.`,
          );
        } else {
          clearLookupResults();
          setEditStatus(
            "No matches found—try adjusting the title or year.",
            true,
          );
        }
      } catch (error) {
        console.error("Lookup failed", error);
        if (requestId === lookupRequestToken) {
          setEditStatus(
            "Lookup failed—check your connection and try again.",
            true,
          );
        }
      } finally {
        if (requestId === lookupRequestToken) {
          setLookupButtonsPending(false);
          if (editLookupRetryButton) {
            editLookupRetryButton.hidden = false;
          }
        }
      }
    };

    const resetEditForm = () => {
      if (editTitleInput) editTitleInput.value = "";
      if (editYearInput) editYearInput.value = "";
      if (editRuntimeInput) editRuntimeInput.value = "";
      if (editPosterInput) editPosterInput.value = "";
      if (editGenresInput) editGenresInput.value = "";
      if (editPlotInput) editPlotInput.value = "";
      if (editResolveInput) editResolveInput.checked = false;
      if (editMovieIdInput) editMovieIdInput.value = "";
      resetEditStatus();
      clearLookupResults({ hideRetry: true });
      setLookupButtonsPending(false);
      lookupRequestToken += 1;
    };

    const closeEditDialog = ({ restoreFocus = false } = {}) => {
      if (!editDialog) return;
      if (editDialog.classList.contains("is-open")) {
        editDialog.classList.remove("is-open");
        editDialog.setAttribute("aria-hidden", "true");
        unlockScroll();
      }
      resetEditForm();
      const trigger = restoreFocus && lastEditTrigger ? lastEditTrigger : null;
      currentEditMovieId = null;
      currentEditDetail = null;
      if (trigger && typeof trigger.focus === "function") {
        trigger.focus();
      }
      lastEditTrigger = null;
    };

    const parseGenresInput = (value) =>
      (value || "")
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item.length);

    const populateEditForm = (detail) => {
      if (!detail) return;
      currentEditDetail = detail;
      if (editMovieIdInput) editMovieIdInput.value = String(detail.id);
      if (editTitleInput) editTitleInput.value = detail.title || "";
      if (editYearInput) editYearInput.value = detail.year ?? "";
      if (editRuntimeInput) editRuntimeInput.value = detail.runtime ?? "";
      if (editPosterInput) editPosterInput.value = detail.poster_url || "";
      if (editPlotInput) editPlotInput.value = detail.plot || "";
      if (editGenresInput)
        editGenresInput.value = (detail.genres || []).join(", ");
      if (editResolveInput) editResolveInput.checked = Boolean(detail.flagged);
    };

    const openEditDialog = async (movieId) => {
      if (!editDialog || !movieId) return;
      currentEditMovieId = Number(movieId);
      resetEditForm();
      editDialog.classList.add("is-open");
      editDialog.setAttribute("aria-hidden", "false");
      lockScroll();
      setEditStatus("Loading metadata…");
      if (editSubmitButton) {
        editSubmitButton.disabled = true;
        editSubmitButton.setAttribute("aria-busy", "true");
      }
      try {
        const response = await fetch(`/movies/${movieId}/detail`);
        if (!response.ok) {
          throw new Error(`Failed to load detail (${response.status})`);
        }
        const detail = await response.json();
        populateEditForm(detail);
        setEditStatus("");
        if (editStatusEl) editStatusEl.hidden = true;
        if (editTitleInput) editTitleInput.focus();
        fetchLookupCandidates();
      } catch (error) {
        console.error("Failed to load movie detail", error);
        closeEditDialog();
        showToastMessage("Could not load that movie—try again?");
        return;
      } finally {
        if (editSubmitButton) {
          editSubmitButton.disabled = false;
          editSubmitButton.removeAttribute("aria-busy");
        }
      }
    };

    editCancelButton?.addEventListener("click", () => {
      closeEditDialog({ restoreFocus: true });
    });

    editCloseButton?.addEventListener("click", () => {
      closeEditDialog({ restoreFocus: true });
    });

    editDialog?.addEventListener("click", (event) => {
      if (event.target === editDialog) {
        closeEditDialog({ restoreFocus: true });
      }
    });

    editLookupButton?.addEventListener("click", () => {
      fetchLookupCandidates();
    });

    editLookupRetryButton?.addEventListener("click", () => {
      fetchLookupCandidates();
    });

    const searchInput = document.getElementById("search-q");
    const orderSelect = document.getElementById("order-by");
    const pageInput = form?.querySelector('input[name="page"]');

    const hiddenGenresInput = document.getElementById("genres-input");
    const hiddenMoodsInput = document.getElementById("moods-input");
    const hiddenYearMinInput = document.getElementById("year-min-input");
    const hiddenYearMaxInput = document.getElementById("year-max-input");
    const hiddenRuntimeInput = document.getElementById("runtime-max-input");

    const parseList = (value) =>
      (value || "")
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item.length);

    const toNumber = (value) => {
      if (value === null || value === undefined || value === "") return null;
      const parsed = Number.parseInt(value, 10);
      return Number.isNaN(parsed) ? null : parsed;
    };

    let submitTimer = null;
    const scheduleSubmit = (delay = 120) => {
      if (!form) return;
      if (submitTimer) {
        clearTimeout(submitTimer);
      }
      submitTimer = window.setTimeout(() => {
        submitTimer = null;
        submitSearch();
      }, delay);
    };

    const genreChips = Array.from(
      document.querySelectorAll('[data-filter-group="genres"] .chip-select'),
    );
    const moodChips = Array.from(
      document.querySelectorAll('[data-filter-group="moods"] .chip-select'),
    );
    const genreOrder = genreChips
      .map((chip) => chip.dataset.filterValue)
      .filter(Boolean);
    const moodOrder = moodChips
      .map((chip) => chip.dataset.filterValue)
      .filter(Boolean);
    const selectedGenres = new Set(parseList(hiddenGenresInput?.value));
    const selectedMoods = new Set(parseList(hiddenMoodsInput?.value));
    let presetChips = Array.from(
      document.querySelectorAll(".chip-preset[data-filters]"),
    );
    const PRESET_STORAGE_KEY = "flicActivePreset";

    const yearPills = document.querySelectorAll(
      "[data-year-pills] .pill-button",
    );
    const yearCustomContainer = document.getElementById("year-custom");
    const yearCustomMinInput = document.getElementById("year-custom-min");
    const yearCustomMaxInput = document.getElementById("year-custom-max");

    let yearState = {
      mode: "any",
      min: toNumber(hiddenYearMinInput?.value),
      max: toNumber(hiddenYearMaxInput?.value),
    };
    if (yearState.min !== null || yearState.max !== null) {
      if (yearState.min !== null && yearState.max !== null) {
        const matchesPreset = Array.from(yearPills).some((button) => {
          const range = button.dataset.yearRange;
          if (!range || range === "custom") return false;
          const [start, end] = range.split("-");
          return (
            Number(start) === yearState.min && Number(end) === yearState.max
          );
        });
        yearState.mode = matchesPreset ? "decade" : "custom";
      } else {
        yearState.mode = "custom";
      }
    }

    const runtimePills = document.querySelectorAll(
      "[data-runtime-pills] .pill-button",
    );
    const runtimeCustomContainer = document.getElementById("runtime-custom");
    const runtimeCustomInput = document.getElementById("runtime-custom-input");
    let runtimeValue = toNumber(hiddenRuntimeInput?.value);

    const orderedFromSet = (set, order) => {
      const ordered = order.filter((value) => set.has(value));
      const extras = Array.from(set).filter((value) => !order.includes(value));
      return [...ordered, ...extras];
    };

    const getFiltersSnapshot = () => {
      const genresArray = orderedFromSet(selectedGenres, genreOrder);
      const moodsArray = orderedFromSet(selectedMoods, moodOrder);
      return {
        q: searchInput?.value.trim() || null,
        genres: genresArray,
        moods: moodsArray,
        year_min: yearState.min,
        year_max: yearState.max,
        runtime_max: runtimeValue,
        order_by: orderSelect?.value || "title_asc",
      };
    };

    const canonicalList = (value) => {
      if (!Array.isArray(value)) return [];
      return value
        .map((item) => {
          if (typeof item === "string") return item.trim();
          if (item === null || item === undefined) return "";
          return String(item).trim();
        })
        .filter((item) => item.length)
        .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
    };

    const canonicalFilters = (filters = {}) => ({
      q:
        typeof filters.q === "string" && filters.q.trim()
          ? filters.q.trim()
          : null,
      order_by: filters.order_by || "title_asc",
      year_min: typeof filters.year_min === "number" ? filters.year_min : null,
      year_max: typeof filters.year_max === "number" ? filters.year_max : null,
      runtime_max:
        typeof filters.runtime_max === "number" ? filters.runtime_max : null,
      genres: canonicalList(filters.genres),
      moods: canonicalList(filters.moods),
    });

    const loadStoredPreset = () => {
      try {
        const raw = sessionStorage.getItem(PRESET_STORAGE_KEY);
        return raw ? JSON.parse(raw) : null;
      } catch (err) {
        console.warn("Failed to read preset selection", err);
        return null;
      }
    };

    const rememberPresetSelection = (chip, filtersString) => {
      if (!filtersString) return;
      try {
        sessionStorage.setItem(
          PRESET_STORAGE_KEY,
          JSON.stringify({
            filters: filtersString,
            label: chip?.dataset.presetName || chip?.textContent?.trim() || "",
          }),
        );
      } catch (err) {
        console.warn("Failed to persist preset selection", err);
      }
    };

    const clearPresetSelection = () => {
      try {
        sessionStorage.removeItem(PRESET_STORAGE_KEY);
      } catch (err) {
        console.warn("Failed to clear preset selection", err);
      }
    };

    const filtersMatchSnapshot = (presetFilters, snapshotFilters) => {
      if (!presetFilters || !snapshotFilters) return false;
      const left = canonicalFilters(presetFilters);
      const right = canonicalFilters(snapshotFilters);
      const arraysEqual = (a, b) =>
        a.length === b.length && a.every((value, idx) => value === b[idx]);
      return (
        left.q === right.q &&
        left.order_by === right.order_by &&
        left.year_min === right.year_min &&
        left.year_max === right.year_max &&
        left.runtime_max === right.runtime_max &&
        arraysEqual(left.genres, right.genres) &&
        arraysEqual(left.moods, right.moods)
      );
    };

    const syncPresetHighlights = () => {
      const snapshot = getFiltersSnapshot();
      const stored = loadStoredPreset();
      let activeChip = null;
      if (stored?.filters) {
        let parsed = null;
        try {
          parsed = JSON.parse(stored.filters);
        } catch (err) {
          parsed = null;
        }
        if (parsed && filtersMatchSnapshot(parsed, snapshot)) {
          activeChip =
            presetChips.find(
              (chip) => chip.getAttribute("data-filters") === stored.filters,
            ) || null;
        } else {
          clearPresetSelection();
        }
      }
      presetChips.forEach((chip) => {
        const isActive = chip === activeChip;
        chip.classList.toggle("is-active", isActive);
        if (isActive) {
          chip.setAttribute("aria-current", "true");
        } else {
          chip.removeAttribute("aria-current");
        }
      });
    };

    const queueResultsScroll = () => {
      try {
        sessionStorage.setItem("flicScrollAnchor", "results");
      } catch (err) {
        console.warn("Failed to persist scroll anchor", err);
      }
    };

    const markFiltersCustom = () => {
      clearPresetSelection();
      syncPresetHighlights();
      queueResultsScroll();
    };

    const ORDER_LABELS = {
      title_asc: "Title A→Z",
      title_desc: "Title Z→A",
      year_desc: "Newest first",
      runtime_asc: "Shortest runtime",
      imdb_desc: "Highest IMDb",
      rt_desc: "Highest Rotten Tomatoes",
      flic: "Flic Score (smart mix)",
    };

    const updateFilterSummary = () => {
      if (!filtersSummaryEl) return;
      const snapshot = getFiltersSnapshot();
      const parts = [];
      const {
        genres,
        moods,
        runtime_max: runtimeMax,
        year_min: yearMin,
        year_max: yearMax,
        order_by: orderBy,
      } = snapshot;

      if (genres.length) {
        const label = genres.slice(0, 2).join(", ");
        parts.push(genres.length > 2 ? `${label}…` : label);
      }

      if (moods.length) {
        const label = moods.slice(0, 2).join(", ");
        parts.push(moods.length > 2 ? `${label} moods` : label);
      }

      if (typeof runtimeMax === "number") {
        parts.push(`≤ ${runtimeMax} min`);
      }

      if (typeof yearMin === "number" || typeof yearMax === "number") {
        const start = typeof yearMin === "number" ? yearMin : "Any";
        const end = typeof yearMax === "number" ? yearMax : "Now";
        parts.push(`${start}–${end}`);
      }

      if (orderBy && orderBy !== "title_asc") {
        parts.push(ORDER_LABELS[orderBy] || orderBy);
      }

      filtersSummaryEl.textContent = parts.length
        ? parts.join(" • ")
        : "Adjust search";
    };

    const syncHiddenInputs = () => {
      if (hiddenGenresInput) {
        hiddenGenresInput.value = orderedFromSet(
          selectedGenres,
          genreOrder,
        ).join(", ");
      }
      if (hiddenYearMinInput) {
        hiddenYearMinInput.value = yearState.min ?? "";
      }
      if (hiddenYearMaxInput) {
        hiddenYearMaxInput.value = yearState.max ?? "";
      }
      if (hiddenRuntimeInput) {
        hiddenRuntimeInput.value = runtimeValue ?? "";
      }
      if (hiddenMoodsInput) {
        hiddenMoodsInput.value = orderedFromSet(selectedMoods, moodOrder).join(
          ", ",
        );
      }
    };

    const setChipState = (chips, selection) => {
      chips.forEach((chip) => {
        const value = chip.dataset.filterValue;
        if (!value) return;
        chip.classList.toggle("is-active", selection.has(value));
      });
    };

    const updateChipsFromState = () => {
      setChipState(genreChips, selectedGenres);
      setChipState(moodChips, selectedMoods);
    };

    const ensureYearControlsFromState = () => {
      yearPills.forEach((button) => {
        const range = button.dataset.yearRange;
        if (!range) return;
        if (range === "custom") {
          button.classList.toggle("is-active", yearState.mode === "custom");
        } else if (range === "") {
          button.classList.toggle("is-active", yearState.mode === "any");
        } else if (yearState.min !== null && yearState.max !== null) {
          const [start, end] = range.split("-");
          const isMatch =
            Number(start) === yearState.min && Number(end) === yearState.max;
          button.classList.toggle("is-active", isMatch);
        } else {
          button.classList.remove("is-active");
        }
      });

      if (yearState.mode === "custom") {
        yearCustomContainer?.removeAttribute("hidden");
        if (yearCustomMinInput) yearCustomMinInput.value = yearState.min ?? "";
        if (yearCustomMaxInput) yearCustomMaxInput.value = yearState.max ?? "";
      } else {
        yearCustomContainer?.setAttribute("hidden", "");
        if (yearCustomMinInput) yearCustomMinInput.value = "";
        if (yearCustomMaxInput) yearCustomMaxInput.value = "";
      }
    };

    const ensureRuntimeControlsFromState = () => {
      runtimePills.forEach((button) => {
        const raw = button.dataset.runtimeMax;
        if (raw === "custom") {
          button.classList.toggle(
            "is-active",
            runtimeValue !== null &&
              !Array.from(runtimePills).some((pill) => {
                const preset = pill.dataset.runtimeMax;
                if (!preset || preset === "custom") return false;
                return Number(preset) === runtimeValue;
              }),
          );
        } else if (!raw) {
          button.classList.toggle("is-active", runtimeValue === null);
        } else {
          button.classList.toggle("is-active", runtimeValue === Number(raw));
        }
      });

      const matchesPreset =
        runtimeValue === null ||
        Array.from(runtimePills).some((button) => {
          const raw = button.dataset.runtimeMax;
          return raw && raw !== "custom" && Number(raw) === runtimeValue;
        });

      if (runtimeValue === null || matchesPreset) {
        runtimeCustomContainer?.setAttribute("hidden", "");
        if (runtimeCustomInput) runtimeCustomInput.value = "";
      } else {
        runtimeCustomContainer?.removeAttribute("hidden");
        if (runtimeCustomInput) runtimeCustomInput.value = runtimeValue ?? "";
      }
    };

    const refreshUI = () => {
      updateChipsFromState();
      ensureYearControlsFromState();
      ensureRuntimeControlsFromState();
      syncHiddenInputs();
      updateFilterSummary();
      syncPresetHighlights();
    };

    const attachChipToggle = (chip, selection) => {
      if (!chip) return;
      const value = chip.dataset.filterValue;
      if (!value) return;
      chip.addEventListener("click", () => {
        markFiltersCustom();
        if (selection.has(value)) {
          selection.delete(value);
        } else {
          selection.add(value);
        }
        refreshUI();
        queueResultsScroll();
        scheduleSubmit();
      });
    };

    genreChips.forEach((chip) => attachChipToggle(chip, selectedGenres));
    moodChips.forEach((chip) => attachChipToggle(chip, selectedMoods));

    yearPills.forEach((button) => {
      const range = button.dataset.yearRange ?? "";
      button.addEventListener("click", () => {
        markFiltersCustom();
        if (range === "custom") {
          yearState.mode = "custom";
          yearCustomContainer?.removeAttribute("hidden");
          yearState.min = toNumber(yearCustomMinInput?.value ?? null);
          yearState.max = toNumber(yearCustomMaxInput?.value ?? null);
          if (yearCustomMinInput && !yearCustomMinInput.value) {
            yearCustomMinInput.focus();
          }
        } else if (range === "") {
          yearState = { mode: "any", min: null, max: null };
        } else {
          const [start, end] = range.split("-");
          yearState = {
            mode: "decade",
            min: Number(start),
            max: Number(end),
          };
        }
        refreshUI();
        scheduleSubmit(range === "custom" ? 240 : 0);
      });
    });

    const handleYearCustomInput = () => {
      markFiltersCustom();
      yearState.mode = "custom";
      yearCustomContainer?.removeAttribute("hidden");
      yearState.min = toNumber(yearCustomMinInput?.value ?? null);
      yearState.max = toNumber(yearCustomMaxInput?.value ?? null);
      refreshUI();
      scheduleSubmit(240);
    };

    yearCustomMinInput?.addEventListener("input", handleYearCustomInput);
    yearCustomMaxInput?.addEventListener("input", handleYearCustomInput);

    runtimePills.forEach((button) => {
      const raw = button.dataset.runtimeMax ?? "";
      button.addEventListener("click", () => {
        markFiltersCustom();
        if (raw === "custom") {
          runtimeCustomContainer?.removeAttribute("hidden");
          runtimeValue = toNumber(runtimeCustomInput?.value ?? null);
          runtimeCustomInput?.focus();
        } else if (raw === "") {
          runtimeValue = null;
        } else {
          runtimeValue = toNumber(raw);
          runtimeCustomContainer?.setAttribute("hidden", "");
          if (runtimeCustomInput) runtimeCustomInput.value = "";
        }
        refreshUI();
        scheduleSubmit(raw === "custom" ? 240 : 0);
      });
    });

    runtimeCustomInput?.addEventListener("input", () => {
      markFiltersCustom();
      runtimeValue = toNumber(runtimeCustomInput.value);
      runtimeCustomContainer?.removeAttribute("hidden");
      refreshUI();
      scheduleSubmit(240);
    });

    const submitSearch = ({ resetPage = true } = {}) => {
      if (!form) return;
      if (resetPage && pageInput) pageInput.value = "1";
      syncHiddenInputs();
      closeFilters();
      if (form && formBaseAction) {
        form.action = formBaseAction;
      }
      form.requestSubmit();
    };

    filtersApplyButton?.addEventListener("click", () => {
      submitSearch({ resetPage: false });
    });

    orderSelect?.addEventListener("change", () => {
      markFiltersCustom();
      if (pageInput) pageInput.value = "1";
      scheduleSubmit();
    });

    const reset = () => {
      if (!form) return;
      clearPresetSelection();
      if (searchInput) searchInput.value = "";
      selectedGenres.clear();
      selectedMoods.clear();
      yearState = { mode: "any", min: null, max: null };
      runtimeValue = null;
      if (orderSelect) orderSelect.value = "title_asc";
      if (pageInput) pageInput.value = "1";
      if (yearCustomMinInput) yearCustomMinInput.value = "";
      if (yearCustomMaxInput) yearCustomMaxInput.value = "";
      if (runtimeCustomInput) runtimeCustomInput.value = "";
      refreshUI();
      syncHiddenInputs();
      submitSearch();
    };

    const clearFilterByKey = (key, value) => {
      switch (key) {
        case "q":
          if (searchInput) searchInput.value = "";
          break;
        case "genre":
          if (value) selectedGenres.delete(value);
          break;
        case "mood":
          if (value) selectedMoods.delete(value);
          break;
        case "year":
          yearState = { mode: "any", min: null, max: null };
          if (yearCustomMinInput) yearCustomMinInput.value = "";
          if (yearCustomMaxInput) yearCustomMaxInput.value = "";
          break;
        case "runtime":
          runtimeValue = null;
          if (runtimeCustomInput) runtimeCustomInput.value = "";
          break;
        default:
          break;
      }
      markFiltersCustom();
      refreshUI();
      syncHiddenInputs();
      submitSearch();
    };

    document.querySelectorAll("[data-clear-filter]").forEach((button) => {
      button.addEventListener("click", () => {
        const key = button.dataset.clearFilter;
        const value = button.dataset.filterValue;
        clearFilterByKey(key, value);
      });
    });
    document
      .getElementById("clear-active-filters")
      ?.addEventListener("click", reset);

    const parseCsv = (raw) =>
      (raw || "")
        .split(",")
        .map((item) => item.replace(/\+/g, " ").trim())
        .filter(Boolean);

    const ensureActiveFilters = () => {
      if (document.querySelector(".chip-active")) return;
      const root = document.querySelector("[data-active-filters-root]");
      if (!root) return;

      const entries = [];
      if (searchInput && searchInput.value.trim()) {
        entries.push({
          key: "q",
          label: `Search: ${searchInput.value.trim()}`,
        });
      }
      const genresInput = document.getElementById("genres-input");
      parseCsv(genresInput?.value).forEach((value) => {
        entries.push({ key: "genre", label: value, value });
      });
      const moodsInput = document.getElementById("moods-input");
      parseCsv(moodsInput?.value).forEach((value) => {
        entries.push({ key: "mood", label: value, value });
      });
      const yearMinInput = document.getElementById("year-min-input");
      const yearMaxInput = document.getElementById("year-max-input");
      const yMin = yearMinInput?.value?.trim();
      const yMax = yearMaxInput?.value?.trim();
      if (yMin || yMax) {
        entries.push({
          key: "year",
          label: `Years: ${yMin || "Any"}–${yMax || "Now"}`,
        });
      }
      const runtimeInput = document.getElementById("runtime-max-input");
      if (runtimeInput?.value?.trim()) {
        entries.push({
          key: "runtime",
          label: `≤ ${runtimeInput.value.trim()} min`,
          value: runtimeInput.value.trim(),
        });
      }

      if (!entries.length) {
        root.hidden = true;
        return;
      }

      root.innerHTML = `
        <div class="active-filters__label">Active</div>
        <div class="active-filters__chips"></div>
        <button type="button" class="button-ghost" id="clear-active-filters-js">Clear all</button>
      `;
      const chipsContainer = root.querySelector(".active-filters__chips");
      entries.forEach((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "chip chip-active";
        button.dataset.clearFilter = item.key;
        if (item.value) button.dataset.filterValue = item.value;
        button.innerHTML = `${item.label} <span aria-hidden="true">×</span>`;
        button.addEventListener("click", () =>
          clearFilterByKey(item.key, item.value),
        );
        chipsContainer.appendChild(button);
      });
      root.hidden = false;
      root
        .querySelector("#clear-active-filters-js")
        ?.addEventListener("click", reset);
    };

    ensureActiveFilters();

    const applyFilters = (filters, options = {}) => {
      if (!form) return;
      if (searchInput) searchInput.value = filters.q || "";
      selectedGenres.clear();
      (filters.genres || []).forEach((value) => selectedGenres.add(value));
      selectedMoods.clear();
      (filters.moods || []).forEach((value) => selectedMoods.add(value));
      yearState = { mode: "any", min: null, max: null };
      if (
        typeof filters.year_min === "number" ||
        typeof filters.year_max === "number"
      ) {
        yearState.min =
          typeof filters.year_min === "number" ? filters.year_min : null;
        yearState.max =
          typeof filters.year_max === "number" ? filters.year_max : null;
        if (yearState.min !== null && yearState.max !== null) {
          const matchesPreset = Array.from(yearPills).some((button) => {
            const range = button.dataset.yearRange;
            if (!range || range === "custom" || range === "") return false;
            const [start, end] = range.split("-");
            return (
              Number(start) === yearState.min && Number(end) === yearState.max
            );
          });
          yearState.mode = matchesPreset ? "decade" : "custom";
        } else {
          yearState.mode = "custom";
        }
      }
      runtimeValue =
        typeof filters.runtime_max === "number" ? filters.runtime_max : null;
      if (orderSelect) {
        orderSelect.value = filters.order_by || "title_asc";
      }
      if (pageInput) pageInput.value = "1";
      refreshUI();
      syncHiddenInputs();
      if (options.scrollToResults) {
        queueResultsScroll();
      }
      submitSearch();
    };

    const applyAiPlan = () => {
      if (!lastAiPlan) return;
      clearPresetSelection();
      applyFilters(lastAiPlan, { scrollToResults: true });
    };

    aiApplyButton?.addEventListener("click", applyAiPlan);

    aiSearchForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!aiSearchInput) return;
      const query = aiSearchInput.value.trim();
      if (!query) {
        setAiStatus("Describe what you want to watch first.", true);
        aiSearchInput.focus();
        return;
      }

      const releaseBusy = setActionBusy(aiSubmitButton, {
        busyLabel: "Thinking…",
      });
      setAiStatus("");
      aiRequestToken += 1;
      const requestId = aiRequestToken;

      try {
        const response = await fetch("/api/ai/search", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ query, page: 1, page_size: 24 }),
        });

        if (!response.ok) {
          let detail = null;
          try {
            const payload = await response.json();
            detail = payload?.detail || null;
          } catch (err) {
            detail = null;
          }
          throw new Error(detail || `AI search failed (${response.status}).`);
        }

        const payload = await response.json();
        if (requestId !== aiRequestToken) return;
        lastAiPlan = payload.plan || null;
        if (aiPlanSummary) {
          aiPlanSummary.textContent = payload.explanation || "AI plan ready.";
        }
        if (aiPlanContainer) {
          aiPlanContainer.hidden = !lastAiPlan;
        }
        if (aiApplyButton) {
          aiApplyButton.disabled = !lastAiPlan;
        }
        renderAiResults(payload.items || []);
      } catch (error) {
        console.error("AI search failed", error);
        lastAiPlan = null;
        if (aiPlanContainer) aiPlanContainer.hidden = true;
        setAiStatus("AI search failed—try again in a moment.", true);
      } finally {
        releaseBusy();
      }
    });

    const attachPresetChip = (chip) => {
      if (!chip) return;
      chip.addEventListener("click", () => {
        try {
          const raw = chip.getAttribute("data-filters");
          if (!raw) return;
          const data = JSON.parse(raw);
          rememberPresetSelection(chip, raw);
          applyFilters(data, { scrollToResults: true });
        } catch (err) {
          console.error("Failed to apply preset", err);
        }
      });
    };

    presetChips.forEach(attachPresetChip);

    const presetsContainer = document.querySelector("#fliclists .chip-scroll");
    const savePresetButton = document.getElementById("save-preset");
    if (savePresetButton) {
      savePresetButton.addEventListener("click", async () => {
        if (!form || savePresetButton.dataset.pending === "true") {
          return;
        }
        const suggestedName = searchInput?.value.trim() || "";
        const rawName = window.prompt("Name this Fliclist", suggestedName);
        if (rawName === null) {
          return;
        }
        const name = rawName.trim();
        if (!name) {
          if (typeof window.showToast === "function") {
            window.showToast("Give the preset a name first.");
          }
          return;
        }

        const snapshot = getFiltersSnapshot();
        const payload = {
          name,
          filters: {
            q: snapshot.q,
            genres: snapshot.genres,
            moods: snapshot.moods,
            year_min: snapshot.year_min,
            year_max: snapshot.year_max,
            runtime_max: snapshot.runtime_max,
            order_by: snapshot.order_by,
          },
        };

        savePresetButton.dataset.pending = "true";
        savePresetButton.setAttribute("aria-busy", "true");
        savePresetButton.disabled = true;

        try {
          const response = await authFetch(
            "/fliclists/",
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify(payload),
            },
            { authPrompt: "Admin token required to save Fliclists." },
          );

          if (response.status === 401) {
            if (typeof window.showToast === "function") {
              window.showToast("Admin token required to save presets.");
            }
            return;
          }

          if (response.status === 201) {
            const preset = await response.json();
            if (typeof window.showToast === "function") {
              window.showToast(`Saved "${preset.name}" to Fliclists.`);
            }
            if (presetsContainer) {
              const chip = document.createElement("button");
              chip.type = "button";
              chip.className = "chip chip-preset";
              chip.textContent = preset.name;
              chip.dataset.presetName = preset.name;
              chip.setAttribute("data-filters", JSON.stringify(preset.filters));
              presetsContainer.insertBefore(chip, savePresetButton);
              attachPresetChip(chip);
              presetChips.push(chip);
              syncPresetHighlights();
            }
            return;
          }

          let detailMessage = null;
          try {
            const errorPayload = await response.json();
            detailMessage = errorPayload?.detail ?? null;
          } catch (err) {
            detailMessage = null;
          }
          if (detailMessage && typeof window.showToast === "function") {
            window.showToast(detailMessage);
          } else if (typeof window.showToast === "function") {
            window.showToast("I could not save that preset—try again?");
          }
        } catch (error) {
          console.error("Failed to save preset", error);
          if (typeof window.showToast === "function") {
            window.showToast("Network hiccup—try again soon?");
          }
        } finally {
          delete savePresetButton.dataset.pending;
          savePresetButton.removeAttribute("aria-busy");
          savePresetButton.disabled = false;
        }
      });
    }

    form?.addEventListener("submit", syncHiddenInputs);

    refreshUI();

    const resultsTable = document.getElementById("results-table-table");
    const updateMovieDisplays = (movie) => {
      if (!movie || !movie.id) return;
      const title = movie.title || "";
      document
        .querySelectorAll(`[data-movie-card][data-movie-id="${movie.id}"] h2`)
        .forEach((heading) => {
          heading.textContent = title;
        });

      document
        .querySelectorAll(`[data-movie-row][data-movie-id="${movie.id}"]`)
        .forEach((row) => {
          row.dataset.title = title.toLowerCase();
          row.dataset.year = movie.year ?? "";
          row.dataset.runtime = movie.runtime ?? "";
          row.dataset.rating = movie.imdb_rating ?? "";

          const titleCell = row.querySelector('[data-label="Title"]');
          if (titleCell) {
            const link = titleCell.querySelector("a");
            if (link) link.textContent = title;
          }

          const yearCell = row.querySelector('[data-label="Year"]');
          if (yearCell) yearCell.textContent = movie.year ?? "—";

          const runtimeCell = row.querySelector('[data-label="Runtime"]');
          if (runtimeCell)
            runtimeCell.textContent = movie.runtime
              ? String(movie.runtime)
              : "—";

          const ratingCell = row.querySelector('[data-label="IMDb"]');
          if (ratingCell)
            ratingCell.textContent = movie.imdb_rating
              ? String(movie.imdb_rating)
              : "—";

          const genresCell = row.querySelector('[data-label="Genres"]');
          if (genresCell) {
            const genreNames = Array.isArray(movie.genres)
              ? movie.genres
                  .map((genre) =>
                    typeof genre === "string" ? genre : genre.name,
                  )
                  .filter(Boolean)
              : [];
            genresCell.textContent = genreNames.length
              ? genreNames.join(", ")
              : "—";
          }
        });
    };

    const FLAG_REASONS = [
      "Metadata cleanup",
      "Poster/backdrop issue",
      "Missing poster",
      "Broken link",
      "Wrong runtime/year",
      "Needs runtime",
      "Other",
    ];

    let flagDialogStylesInjected = false;

    const ensureFlagDialogStyles = () => {
      if (flagDialogStylesInjected) return;
      const style = document.createElement("style");
      style.textContent = `
      .flag-dialog-overlay {
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.35);
        display: grid;
        place-items: center;
        z-index: 1000;
      }
      .flag-dialog {
        background: #111;
        color: #f5f5f5;
        border-radius: 12px;
        padding: 16px;
        max-width: 420px;
        width: 90%;
        box-shadow: 0 14px 40px rgba(0,0,0,0.4);
      }
      .flag-dialog h3 {
        margin: 0 0 8px 0;
        font-size: 1.1rem;
      }
      .flag-dialog label {
        display: block;
        font-size: 0.9rem;
        margin: 8px 0 4px 0;
      }
      .flag-dialog select,
      .flag-dialog textarea {
        width: 100%;
        border-radius: 8px;
        border: 1px solid #333;
        background: #1a1a1a;
        color: #f5f5f5;
        padding: 8px;
        box-sizing: border-box;
      }
      .flag-dialog textarea {
        min-height: 80px;
        resize: vertical;
      }
      .flag-dialog__actions {
        display: flex;
        gap: 8px;
        justify-content: flex-end;
        margin-top: 12px;
      }
      .flag-dialog__actions button {
        border-radius: 8px;
        border: none;
        padding: 8px 12px;
        cursor: pointer;
      }
      .flag-dialog__actions .button-primary {
        background: #e1a228;
        color: #111;
      }
      .flag-dialog__actions .button-ghost {
        background: transparent;
        color: #f5f5f5;
        border: 1px solid #333;
      }
      `;
      document.head.append(style);
      flagDialogStylesInjected = true;
    };

    const openFlagDialog = (defaultReason) =>
      new Promise((resolve) => {
        ensureFlagDialogStyles();
        const overlay = document.createElement("div");
        overlay.className = "flag-dialog-overlay";
        const dialog = document.createElement("div");
        dialog.className = "flag-dialog";
        dialog.innerHTML = `
          <h3>Flag this movie</h3>
          <label for="flag-reason">Reason</label>
          <select id="flag-reason">
            ${FLAG_REASONS.map((reason) => {
              const selected = reason === defaultReason ? "selected" : "";
              return `<option value="${reason}" ${selected}>${reason}</option>`;
            }).join("")}
          </select>
          <label for="flag-notes">Notes (optional)</label>
          <textarea id="flag-notes" maxlength="500" placeholder="What needs a fix?"></textarea>
          <div class="flag-dialog__actions">
            <button type="button" class="button-ghost" data-flag-cancel>Cancel</button>
            <button type="button" class="button-primary" data-flag-save>Save</button>
          </div>
        `;
        overlay.append(dialog);
        document.body.append(overlay);

        const cleanup = () => overlay.remove();
        overlay.addEventListener("click", (event) => {
          if (event.target === overlay) {
            cleanup();
            resolve(null);
          }
        });
        dialog
          .querySelector("[data-flag-cancel]")
          ?.addEventListener("click", () => {
            cleanup();
            resolve(null);
          });
        dialog
          .querySelector("[data-flag-save]")
          ?.addEventListener("click", () => {
            const reason = dialog.querySelector("#flag-reason")?.value || "";
            const notes =
              dialog.querySelector("#flag-notes")?.value.trim() || null;
            cleanup();
            resolve({ reason, notes });
          });
      });

    const updateFlagUI = (movieId, flagged) => {
      const flagValue = flagged ? "true" : "false";
      document
        .querySelectorAll(`[data-flag-button][data-movie-id="${movieId}"]`)
        .forEach((button) => {
          button.dataset.flagged = flagValue;
          button.classList.toggle("is-flagged", flagged);
          button.setAttribute("aria-pressed", flagValue);
          const isTableButton = button.classList.contains("flag-toggle--table");
          const buttonLabel = flagged
            ? isTableButton
              ? "Resolve"
              : "Resolve flag"
            : isTableButton
              ? "Flag"
              : "🚩";
          button.textContent = buttonLabel;
          const ariaLabel = flagged ? "Resolve flag" : "Flag to fix";
          button.setAttribute("aria-label", ariaLabel);
        });
      document
        .querySelectorAll(`[data-movie-card][data-movie-id="${movieId}"]`)
        .forEach((card) => {
          card.dataset.flagged = flagValue;
          card.classList.toggle("card--flagged", flagged);
        });
      document
        .querySelectorAll(`[data-movie-row][data-movie-id="${movieId}"]`)
        .forEach((row) => {
          row.dataset.flagged = flagValue;
          row.classList.toggle("is-flagged", flagged);
          const statusCell = row.querySelector(".data-table__cell-status");
          if (statusCell && !statusCell.querySelector("[data-flag-button]")) {
            statusCell.textContent = flagged ? "Needs review" : "—";
          }
        });
    };

    const attachFlagButtons = () => {
      document.querySelectorAll("[data-flag-button]").forEach((button) => {
        if (button.dataset.flagHandlerAttached === "true") {
          return;
        }
        button.dataset.flagHandlerAttached = "true";
        button.addEventListener("click", async () => {
          const movieId = button.dataset.movieId;
          if (!movieId || button.dataset.flagBusy === "true") return;
          const currentlyFlagged = button.dataset.flagged === "true";
          try {
            button.dataset.flagBusy = "true";
            if (currentlyFlagged) {
              const response = await authFetch(
                `/movies/${movieId}/flag`,
                { method: "DELETE" },
                { authPrompt: "Admin token required to resolve flags." },
              );
              if (response.status === 401) {
                showToastMessage("Admin token required to update flags.");
                return;
              }
              if (!response.ok && response.status !== 204) {
                const detail = await parseErrorDetail(response);
                throw new Error(detail || "Failed to clear flag");
              }
              updateFlagUI(movieId, false);
              showToastMessage("Flag cleared.");
            } else {
              const defaultReason =
                button.dataset.flagDefault || "Metadata cleanup";
              const dialogResult = await openFlagDialog(defaultReason);
              if (!dialogResult) {
                return;
              }
              const { reason, notes } = dialogResult;
              const response = await authFetch(
                `/movies/${movieId}/flag`,
                {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                  },
                  body: JSON.stringify({
                    reason: reason || null,
                    notes: notes || null,
                  }),
                },
                { authPrompt: "Admin token required to manage flags." },
              );
              if (response.status === 401) {
                showToastMessage("Admin token required to update flags.");
                return;
              }
              if (!response.ok) {
                const detail = await parseErrorDetail(response);
                throw new Error(detail || "Failed to flag movie");
              }
              updateFlagUI(movieId, true);
              showToastMessage("Flag saved.");
            }
          } catch (error) {
            console.error("Flag toggle failed", error);
            const message =
              error && error.message
                ? error.message
                : "Could not update that flag—try again soon?";
            showToastMessage(message);
          } finally {
            delete button.dataset.flagBusy;
          }
        });
      });
    };

    const attachEditButtons = () => {
      document.querySelectorAll("[data-edit-button]").forEach((button) => {
        if (button.dataset.editHandlerAttached === "true") {
          return;
        }
        button.dataset.editHandlerAttached = "true";
        button.addEventListener("click", () => {
          const movieId = button.dataset.movieId;
          if (!movieId) return;
          lastEditTrigger = button;
          openEditDialog(movieId);
        });
      });
    };

    attachFlagButtons();
    attachEditButtons();

    if (resultsTable) {
      const headers = resultsTable.querySelectorAll("[data-order-by-asc]");
      const filtersForm = document.getElementById("filters-form");
      const orderSelect = document.getElementById("order-by");
      const pageInput = filtersForm?.querySelector('input[name="page"]');

      const submitSort = (orderBy) => {
        if (orderSelect) {
          orderSelect.value = orderBy;
        }
        if (pageInput) {
          pageInput.value = "1";
        }
        if (filtersForm?.requestSubmit) {
          filtersForm.requestSubmit();
          return;
        }
        if (filtersForm) {
          filtersForm.submit();
          return;
        }
        const url = new URL(window.location.href);
        url.searchParams.set("order_by", orderBy);
        url.searchParams.set("page", "1");
        window.location.assign(url.toString());
      };

      headers.forEach((header) => {
        const handleSort = () => {
          const asc = header.dataset.orderByAsc;
          const desc = header.dataset.orderByDesc || asc;
          if (!asc) return;
          const currentOrder = orderSelect?.value || "";
          const nextOrder = currentOrder === asc ? desc : asc;
          submitSort(nextOrder);
        };
        header.addEventListener("click", handleSort);
        header.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            handleSort();
          }
        });
      });
    }

    attachFlagButtons();

    const manualAddForm = document.getElementById("manual-add-form");
    if (manualAddForm) {
      const titleInput = document.getElementById("manual-add-title");
      const yearInput = document.getElementById("manual-add-year");
      const statusEl = document.getElementById("manual-add-status");
      const submitButton = document.getElementById("manual-add-submit");
      const previewContainer = document.getElementById("manual-add-preview");
      const previewTitle = document.getElementById("manual-add-preview-title");
      const previewMeta = document.getElementById("manual-add-preview-meta");
      const previewOverview = document.getElementById(
        "manual-add-preview-overview",
      );
      const previewGenres = document.getElementById(
        "manual-add-preview-genres",
      );
      const previewPoster = document.getElementById(
        "manual-add-preview-poster",
      );
      const confirmButton = document.getElementById("manual-add-confirm");
      const cancelButton = document.getElementById("manual-add-cancel");
      const confirmMinimalButton = document.getElementById(
        "manual-add-confirm-minimal",
      );
      const totalFact = document.querySelector("[data-total-entries]");
      const tableBody = document.querySelector("#results-table-table tbody");
      const detailsRoot = document.getElementById("manual-add");

      let currentPreview = null;
      let lastPayload = null;

      const setStatus = (message, isError = false) => {
        if (!statusEl) return;
        statusEl.textContent = message;
        statusEl.classList.toggle("is-error", Boolean(isError));
        statusEl.hidden = message === "";
      };

      const resetPreview = () => {
        currentPreview = null;
        if (previewContainer) {
          previewContainer.setAttribute("hidden", "");
        }
        if (previewTitle) previewTitle.textContent = "";
        if (previewMeta) previewMeta.textContent = "";
        if (previewOverview) previewOverview.textContent = "";
        if (previewGenres) previewGenres.textContent = "";
        if (previewPoster) previewPoster.innerHTML = "";
        if (confirmMinimalButton) confirmMinimalButton.hidden = true;
        if (confirmButton) {
          confirmButton.disabled = false;
          confirmButton.removeAttribute("aria-busy");
        }
      };

      const renderPreview = (preview) => {
        if (!previewContainer) return;
        previewContainer.removeAttribute("hidden");
        if (previewTitle)
          previewTitle.textContent = preview.title || "Untitled";

        const metaParts = [];
        if (preview.year) metaParts.push(preview.year);
        if (preview.runtime) metaParts.push(`${preview.runtime} min`);
        if (preview.source)
          metaParts.push(`from ${preview.source.toUpperCase()}`);
        if (preview.release_date && !preview.year)
          metaParts.push(preview.release_date);
        if (previewMeta) previewMeta.textContent = metaParts.join(" · ");

        if (previewOverview) {
          previewOverview.textContent =
            preview.overview || "No description available yet.";
        }

        if (previewGenres) {
          const genresLabel = (preview.genres || []).join(", ");
          previewGenres.textContent = genresLabel
            ? `Genres: ${genresLabel}`
            : "";
        }

        if (previewPoster) {
          previewPoster.innerHTML = "";
          if (preview.poster_url) {
            const img = document.createElement("img");
            img.src = preview.poster_url;
            img.alt = `${preview.title || "Movie"} poster`;
            img.className = "manual-add-preview__poster";
            previewPoster.appendChild(img);
          }
        }
      };

      manualAddForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!submitButton || !titleInput) return;

        const title = titleInput.value.trim();
        const yearRaw = yearInput?.value.trim() ?? "";
        if (!title) {
          setStatus("Add a title before saving.", true);
          titleInput.focus();
          return;
        }

        let yearValue = null;
        if (yearRaw) {
          const parsed = Number.parseInt(yearRaw, 10);
          if (Number.isNaN(parsed)) {
            setStatus("Year must be a number.", true);
            yearInput?.focus();
            return;
          }
          yearValue = parsed;
        }

        if (submitButton.dataset.pending === "true") {
          return;
        }

        submitButton.dataset.pending = "true";
        submitButton.disabled = true;
        submitButton.setAttribute("aria-busy", "true");
        setStatus("Looking up info…");
        resetPreview();

        const payload =
          yearValue === null ? { title } : { title, year: yearValue };
        lastPayload = { ...payload };

        try {
          const response = await fetch("/ui/movies/manual-add/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          let body = null;
          try {
            body = await response.json();
          } catch (err) {
            body = null;
          }

          if (!response.ok) {
            const detail =
              body?.detail ?? "Unable to find details for that movie.";
            setStatus(detail, true);
            if (response.status === 409) {
              if (typeof window.showToast === "function") {
                window.showToast(detail);
              }
              currentPreview = null;
              return;
            }
            if (previewContainer && confirmMinimalButton) {
              previewContainer.removeAttribute("hidden");
              if (previewOverview) {
                previewOverview.textContent = detail;
                previewOverview.classList.add("manual-add-preview__body");
              }
              confirmMinimalButton.hidden = false;
            }
            if (confirmButton) {
              confirmButton.disabled = true;
            }
            currentPreview = null;
            return;
          }

          currentPreview = body;
          setStatus("Review the details before adding.");
          renderPreview(body);
          if (confirmButton) confirmButton.disabled = false;
          if (confirmButton) confirmButton.focus();
        } catch (error) {
          console.error("Manual add preview failed", error);
          setStatus("Network hiccup—try again soon?", true);
        } finally {
          submitButton.removeAttribute("aria-busy");
          submitButton.disabled = false;
          delete submitButton.dataset.pending;
        }
      });

      const addRowToTable = (moviePayload) => {
        if (!tableBody || !moviePayload) return;
        const row = document.createElement("tr");
        const lowerTitle = (moviePayload.title || "").toString().toLowerCase();
        row.dataset.title = lowerTitle;
        row.dataset.vaultId = String(moviePayload.id);
        row.dataset.year = moviePayload.year ?? "";
        row.dataset.runtime = moviePayload.runtime ?? "";
        row.dataset.rating = "";
        row.dataset.movieRow = "true";
        row.dataset.movieId = String(moviePayload.id);
        row.dataset.flagged = "false";

        const titleCell = document.createElement("td");
        titleCell.setAttribute("data-label", "Title");
        const link = document.createElement("a");
        link.href = `/ui/movies/${moviePayload.id}`;
        link.textContent = moviePayload.title;
        titleCell.appendChild(link);

        const vaultCell = document.createElement("td");
        vaultCell.setAttribute("data-label", "Vault ID");
        const paddedId = String(moviePayload.id).padStart(4, "0");
        vaultCell.textContent = `V${paddedId}`;

        const yearCell = document.createElement("td");
        yearCell.setAttribute("data-label", "Year");
        yearCell.textContent = moviePayload.year ?? "—";

        const runtimeCell = document.createElement("td");
        runtimeCell.setAttribute("data-label", "Runtime");
        runtimeCell.textContent = moviePayload.runtime
          ? `${moviePayload.runtime}`
          : "—";

        const ratingCell = document.createElement("td");
        ratingCell.setAttribute("data-label", "IMDb");
        ratingCell.textContent = "—";

        const genresCell = document.createElement("td");
        genresCell.setAttribute("data-label", "Genres");
        const genres =
          moviePayload.genres || moviePayload.metadata?.genres || [];
        genresCell.textContent = genres.length ? genres.join(", ") : "—";

        const statusCell = document.createElement("td");
        statusCell.setAttribute("data-label", "Status");
        statusCell.textContent = "—";

        row.appendChild(titleCell);
        row.appendChild(vaultCell);
        row.appendChild(yearCell);
        row.appendChild(runtimeCell);
        row.appendChild(ratingCell);
        row.appendChild(genresCell);
        row.appendChild(statusCell);

        row.classList.remove("is-flagged");

        tableBody.appendChild(row);
        attachFlagButtons();
        attachEditButtons();
      };

      const finalizeCreate = async (metadataOverride) => {
        if (!lastPayload) {
          setStatus("Start with a preview first.", true);
          return;
        }

        const payload = { ...lastPayload };
        if (metadataOverride !== undefined) {
          if (metadataOverride !== null) {
            payload.metadata = metadataOverride;
          }
        } else if (currentPreview) {
          payload.metadata = currentPreview;
        }

        if (confirmButton) {
          confirmButton.dataset.pending = "true";
          confirmButton.disabled = true;
          confirmButton.setAttribute("aria-busy", "true");
        }
        if (confirmMinimalButton) {
          confirmMinimalButton.disabled = true;
          confirmMinimalButton.setAttribute("aria-busy", "true");
        }
        setStatus("Saving…");

        try {
          const response = await authFetch(
            "/ui/movies/manual-add",
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            },
            { authPrompt: "Admin token required to add movies." },
          );
          let body = null;
          try {
            body = await response.json();
          } catch (err) {
            body = null;
          }

          if (response.status === 401) {
            setStatus("Admin token required to add movies.", true);
            if (typeof window.showToast === "function") {
              window.showToast("Admin token required to add movies.");
            }
            return;
          }

          if (!response.ok) {
            const detail = body?.detail ?? "Unable to add that movie right now";
            setStatus(detail, true);
            if (typeof window.showToast === "function") {
              window.showToast(detail);
            }
            return;
          }

          if (titleInput) titleInput.value = "";
          if (yearInput) yearInput.value = "";
          setStatus("Added to your library.");
          if (typeof window.showToast === "function") {
            window.showToast(`Added "${body.title}".`);
          }

          if (totalFact) {
            const current = Number.parseInt(
              totalFact.textContent.replace(/[^0-9]/g, ""),
              10,
            );
            if (!Number.isNaN(current)) {
              totalFact.textContent = String(current + 1);
            }
          }

          addRowToTable(body);
          resetPreview();
          lastPayload = null;
          if (detailsRoot) {
            detailsRoot.removeAttribute("open");
          }
        } catch (error) {
          console.error("Manual add failed", error);
          setStatus("Network hiccup—try again soon?", true);
        } finally {
          if (confirmButton) {
            confirmButton.removeAttribute("aria-busy");
            confirmButton.disabled = false;
            delete confirmButton.dataset.pending;
          }
          if (confirmMinimalButton) {
            confirmMinimalButton.removeAttribute("aria-busy");
            confirmMinimalButton.disabled = false;
          }
        }
      };

      confirmButton?.addEventListener("click", () => {
        finalizeCreate();
      });

      confirmMinimalButton?.addEventListener("click", () => {
        finalizeCreate({ source: "manual" });
      });

      cancelButton?.addEventListener("click", () => {
        resetPreview();
        setStatus("Cancelled. Adjust the title or year to try again.");
      });
    }

    const arraysEqualCI = (a, b) => {
      if (!Array.isArray(a) || !Array.isArray(b)) return false;
      if (a.length !== b.length) return false;
      const normalize = (items) =>
        items.map((item) => item.toLowerCase()).sort();
      const normA = normalize(a);
      const normB = normalize(b);
      return normA.every((value, index) => value === normB[index]);
    };

    editForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!currentEditMovieId) {
        closeEditDialog();
        return;
      }

      const detail = currentEditDetail || {};
      let hasChanges = false;
      const payload = {};

      const titleValue = editTitleInput ? editTitleInput.value.trim() : "";
      if (titleValue === "" && titleValue !== (detail.title || "")) {
        setEditStatus("Title cannot be empty.", true);
        editTitleInput?.focus();
        return;
      }
      if (titleValue && titleValue !== (detail.title || "")) {
        payload.title = titleValue;
        hasChanges = true;
      }

      if (editYearInput && editYearInput.value !== "") {
        const yearValue = Number.parseInt(editYearInput.value, 10);
        if (!Number.isNaN(yearValue) && yearValue !== (detail.year ?? null)) {
          payload.year = yearValue;
          hasChanges = true;
        }
      }

      if (editRuntimeInput && editRuntimeInput.value !== "") {
        const runtimeValue = Number.parseInt(editRuntimeInput.value, 10);
        if (
          !Number.isNaN(runtimeValue) &&
          runtimeValue !== (detail.runtime ?? null)
        ) {
          payload.runtime = runtimeValue;
          hasChanges = true;
        }
      }

      const plotValue = editPlotInput ? editPlotInput.value.trim() : "";
      if (plotValue !== (detail.plot || "")) {
        payload.plot = plotValue;
        hasChanges = true;
      }

      const posterValue = editPosterInput ? editPosterInput.value.trim() : "";
      if (posterValue !== (detail.poster_url || "")) {
        payload.poster_url = posterValue;
        hasChanges = true;
      }

      const genresList = parseGenresInput(
        editGenresInput ? editGenresInput.value : "",
      );
      const originalGenres = Array.isArray(detail.genres) ? detail.genres : [];
      if (!arraysEqualCI(genresList, originalGenres)) {
        payload.genres = genresList;
        hasChanges = true;
      }

      if (editResolveInput && editResolveInput.checked) {
        payload.resolve_flag = true;
        hasChanges = true;
      }

      if (!hasChanges) {
        showToastMessage("No changes to save.");
        closeEditDialog({ restoreFocus: true });
        return;
      }

      try {
        if (editSubmitButton) {
          editSubmitButton.disabled = true;
          editSubmitButton.setAttribute("aria-busy", "true");
        }
        setEditStatus("Saving changes…");
        const response = await authFetch(
          `/movies/${currentEditMovieId}`,
          {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
          },
          { authPrompt: "Admin token required to edit movies." },
        );
        if (response.status === 401) {
          setEditStatus("Admin token required to save changes.", true);
          return;
        }
        if (!response.ok) {
          throw new Error(`Update failed (${response.status})`);
        }
        const updated = await response.json();
        updateMovieDisplays(updated);
        updateFlagUI(String(updated.id), updated.flagged);
        showToastMessage("Movie updated.");
        closeEditDialog({ restoreFocus: true });
      } catch (error) {
        console.error("Failed to update movie", error);
        setEditStatus("Could not save changes—try again?", true);
      } finally {
        if (editSubmitButton) {
          editSubmitButton.disabled = false;
          editSubmitButton.removeAttribute("aria-busy");
        }
      }
    });

    const loadMemory = () => {
      const list = document.getElementById("memory-list");
      if (!list) return;
      fetch("/fliclists/history")
        .then((resp) => (resp.ok ? resp.json() : Promise.reject()))
        .then((items) => {
          if (!items.length) {
            list.innerHTML =
              '<li class="memory-placeholder">No recent picks yet.</li>';
            return;
          }
          list.innerHTML = "";
          items.forEach((entry) => {
            const li = document.createElement("li");
            const link = document.createElement("a");
            link.href = `/ui/movies/${entry.movie_id}`;
            link.textContent = `#${entry.movie_id} · picked ${new Date(entry.created_at).toLocaleString()}`;
            li.appendChild(link);
            list.appendChild(li);
          });
        })
        .catch(() => {
          list.innerHTML =
            '<li class="memory-placeholder">I couldn\'t load memory.</li>';
        });
    };

    loadMemory();

    const copyVaultButton = document.querySelector("[data-copy-vault]");
    if (copyVaultButton) {
      copyVaultButton.addEventListener("click", async () => {
        const vaultId = copyVaultButton.dataset.vaultId;
        if (!vaultId) return;
        const formatted = `V${String(vaultId).padStart(4, "0")}`;
        const copied = await copyToClipboard(formatted);
        if (copied) {
          showToastMessage(`Copied ${formatted}`);
        } else {
          showToastMessage("Could not copy ID—try again.");
        }
      });
    }

    const goToPage = (target) => {
      if (!form || !pageInput) return;
      if (!totalPages || totalPages <= 1) return;
      const desired = Number(target);
      if (Number.isNaN(desired)) return;
      const clamped = Math.max(1, Math.min(totalPages, desired));
      if (clamped === currentPage) return;
      pageInput.value = String(clamped);
      currentPage = clamped;
      syncHiddenInputs();
      form.requestSubmit();
    };

    document.querySelectorAll("[data-goto-page]").forEach((control) => {
      control.addEventListener("click", (event) => {
        if (control.getAttribute("data-disabled") === "true") {
          event.preventDefault();
          return;
        }
        const targetPage = Number(control.getAttribute("data-goto-page"));
        if (!Number.isNaN(targetPage)) {
          event.preventDefault();
          goToPage(targetPage);
        }
      });
    });

    const doPick = async () => {
      const releaseBusy = pickButton
        ? setActionBusy(pickButton, { busyLabel: "Picking…" })
        : () => {};
      const snapshot = getFiltersSnapshot();
      const params = new URLSearchParams();
      if (snapshot.genres?.length) params.set("genre", snapshot.genres[0]);
      if (snapshot.moods?.length) params.set("mood", snapshot.moods[0]);
      if (typeof snapshot.year_min === "number")
        params.set("year_min", snapshot.year_min);
      if (typeof snapshot.year_max === "number")
        params.set("year_max", snapshot.year_max);
      if (typeof snapshot.runtime_max === "number")
        params.set("runtime_max", snapshot.runtime_max);
      try {
        const response = await fetch(`/movies/picks?${params.toString()}`);
        if (response.status === 404) {
          window.showToast("Nothing matched—want me to widen the net?");
          return;
        }
        if (!response.ok) {
          window.showToast("I hit a snag—try again?");
          return;
        }
        const data = await response.json();
        const successMessage = `I queued "${data.title}" for you.`;
        if (typeof window.persistToastMessage === "function") {
          window.persistToastMessage(successMessage);
        }
        window.showToast(successMessage);
        loadMemory();
        setTimeout(() => {
          window.location.href = `/ui/movies/${data.id}`;
        }, 600);
      } catch (error) {
        console.error(error);
        window.showToast("Network hiccup—try again soon?");
      } finally {
        releaseBusy();
      }
    };

    const pickButton = document.getElementById("pick-button");
    pickButton?.addEventListener("click", doPick);
    window.addEventListener("flic:trigger-pick", (event) => {
      if (event && typeof event.preventDefault === "function") {
        event.preventDefault();
      }
      doPick();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      if (editDialog && editDialog.classList.contains("is-open")) {
        closeEditDialog({ restoreFocus: true });
        return;
      }
      if (
        filtersDialog &&
        filtersDialog.classList.contains("is-open") &&
        !isDesktop()
      ) {
        closeFilters({ restoreFocus: true });
      }
    });
    try {
      const pendingAnchor = sessionStorage.getItem("flicScrollAnchor");
      if (pendingAnchor === "results") {
        sessionStorage.removeItem("flicScrollAnchor");
        const resultsShell = document.getElementById("results");
        if (resultsShell) {
          const rect = resultsShell.getBoundingClientRect();
          const navHeightVar = getComputedStyle(
            document.documentElement,
          ).getPropertyValue("--nav-height");
          const navHeight = Number.parseFloat(navHeightVar) || 72;
          const offset = navHeight + 24;
          const targetY = window.scrollY + rect.top - offset;
          window.scrollTo(0, targetY);
        }
      }
    } catch (err) {
      console.warn("Failed to restore scroll anchor", err);
    }
  });
})();
searchInput?.addEventListener("input", () => {
  markFiltersCustom();
});
