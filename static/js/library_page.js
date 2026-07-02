(function () {
  const buildClearFilterUrl = (href, key) => {
    const url = new URL(href);
    if (key === "q") {
      url.searchParams.delete("q");
    }
    if (key === "preset") {
      url.searchParams.delete("preset");
    }
    if (!hasActiveLibraryParams(url.searchParams)) {
      url.searchParams.delete("order_by");
    }
    url.searchParams.set("_filters", "1");
    url.searchParams.set("page", "1");
    return url.toString();
  };

  const hasActiveLibraryParams = (params) =>
    [
      "q",
      "preset",
      "genres",
      "moods",
      "year_min",
      "year_max",
      "runtime_min",
      "runtime_max",
      "semantic",
    ].some((key) => String(params.get(key) || "").trim());

  const buildClearAllFiltersUrl = (href) => {
    const url = new URL(href);
    [
      "q",
      "preset",
      "genres",
      "moods",
      "year_min",
      "year_max",
      "runtime_min",
      "runtime_max",
      "semantic",
      "order_by",
      "page",
    ].forEach((key) => url.searchParams.delete(key));
    url.searchParams.set("_filters", "1");
    url.searchParams.set("page", "1");
    return url.toString();
  };

  const parseCsv = (value = "") =>
    value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

  const formatPresetName = (value = "") =>
    value
      .split("-")
      .filter(Boolean)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");

  const buildPendingSummary = ({
    genres = [],
    presetName = "",
    runtimeMax = "",
    yearLabel = "",
  } = {}) => {
    const items = [];
    if (presetName) {
      items.push({ kind: "preset", label: `Fliclist: ${presetName}` });
    }
    genres.forEach((genre) => items.push({ kind: "genre", label: genre }));
    if (yearLabel) items.push({ kind: "year", label: yearLabel });
    if (runtimeMax) {
      items.push({ kind: "runtime", label: `≤ ${runtimeMax} min` });
    }
    return items;
  };

  const formatApplyLabel = (count) => {
    if (!count) return "Show results";
    return `Show results · ${count} ${count === 1 ? "filter" : "filters"}`;
  };

  const emptyFilterState = () => ({
    genres: [],
    presetName: "",
    runtimeMax: "",
    yearMax: "",
    yearMin: "",
  });

  const shouldShowCustomControl = ({
    hasPresetMatch = false,
    selected = false,
    value = "",
  } = {}) => selected || Boolean(value && !hasPresetMatch);

  const buildRecommendationParams = (
    {
      genres = [],
      moodsValue = "",
      runtimeMax = "",
      yearMax = "",
      yearMin = "",
    } = {},
    { includeRuntime = true } = {},
  ) => {
    const params = new URLSearchParams();
    const firstGenre = Array.from(genres).find(Boolean);
    const firstMood = parseCsv(moodsValue)[0];
    if (firstGenre) params.set("genre", firstGenre);
    if (firstMood) params.set("mood", firstMood);
    if (yearMin) params.set("year_min", yearMin);
    if (yearMax) params.set("year_max", yearMax);
    if (includeRuntime && runtimeMax) params.set("runtime_max", runtimeMax);
    return params;
  };

  const buildRecommendationUrl = (path, params = new URLSearchParams()) => {
    const query = params.toString();
    return query ? `${path}?${query}` : path;
  };

  const recommendationHasFilters = (params = new URLSearchParams()) =>
    Array.from(params.values()).some((value) => String(value).trim());

  const recommendationBusyMessage = (
    params = new URLSearchParams(),
    { kind = "pick", stage = "start" } = {},
  ) => {
    const filtered = recommendationHasFilters(params);
    if (stage === "slow") {
      return kind === "double-feature"
        ? "Still pairing movies from those filters…"
        : "Still checking trusted picks…";
    }
    if (stage === "long") {
      return "This is taking longer than usual…";
    }
    if (kind === "double-feature") {
      return filtered
        ? "Pairing movies from your filters…"
        : "Pairing two movies from the Vault…";
    }
    return filtered
      ? "Choosing from your filtered results…"
      : "Choosing from the full Vault…";
  };

  window.VaultLibrarySupport = {
    buildClearAllFiltersUrl,
    buildClearFilterUrl,
    buildPendingSummary,
    buildRecommendationParams,
    buildRecommendationUrl,
    emptyFilterState,
    formatApplyLabel,
    formatPresetName,
    parseCsv,
    recommendationBusyMessage,
    shouldShowCustomControl,
  };

  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("filters-form");
    const dialog = document.querySelector("[data-filters-dialog]");
    const genresInput = document.getElementById("genres-input");
    const moodsInput = document.getElementById("moods-input");
    const yearMinInput = document.getElementById("year-min-input");
    const yearMaxInput = document.getElementById("year-max-input");
    const runtimeInput = document.getElementById("runtime-max-input");
    const presetInput = document.getElementById("preset-input");
    const orderSelect = document.getElementById("order-by");
    const searchInput = document.getElementById("search-q");
    const applyButton = document.querySelector("[data-filters-apply]");
    const resetButton = document.querySelector("[data-filters-reset]");
    const summary = document.querySelector("[data-filters-summary]");
    const summaryEmpty = document.querySelector("[data-filters-summary-empty]");
    const yearCustom = document.getElementById("year-custom");
    const yearCustomMin = document.getElementById("year-custom-min");
    const yearCustomMax = document.getElementById("year-custom-max");
    const runtimeCustom = document.getElementById("runtime-custom");
    const runtimeCustomInput = document.getElementById("runtime-custom-input");
    const genreButtons = Array.from(
      document.querySelectorAll(
        '[data-filter-group="genres"] [data-filter-value]',
      ),
    );
    const yearButtons = Array.from(
      document.querySelectorAll("[data-year-range]"),
    );
    const runtimeButtons = Array.from(
      document.querySelectorAll("[data-runtime-max]"),
    );
    const presetButtons = Array.from(
      document.querySelectorAll(".chip-preset[data-filters]"),
    );
    const selectedGenres = new Set(parseCsv(genresInput?.value || ""));
    const initialSearchValue = searchInput?.value.trim() || "";
    let pendingPresetName = formatPresetName(presetInput?.value || "");
    let yearCustomSelected = false;
    let runtimeCustomSelected = false;

    const clearPendingPreset = () => {
      pendingPresetName = "";
      if (presetInput) presetInput.value = "";
    };

    const getMatchingYearButton = () => {
      const minimum = yearMinInput?.value || "";
      const maximum = yearMaxInput?.value || "";
      return yearButtons.find((button) => {
        const range = button.dataset.yearRange || "";
        if (range === "custom") return false;
        const [rangeMin = "", rangeMax = ""] = range.split("-");
        return rangeMin === minimum && rangeMax === maximum;
      });
    };

    const getMatchingRuntimeButton = () => {
      const value = runtimeInput?.value || "";
      return runtimeButtons.find((button) => {
        const presetValue = button.dataset.runtimeMax || "";
        return presetValue !== "custom" && presetValue === value;
      });
    };

    const getYearLabel = () => {
      const minimum = yearMinInput?.value || "";
      const maximum = yearMaxInput?.value || "";
      if (!minimum && !maximum) return "";
      const match = getMatchingYearButton();
      if (match?.dataset.yearLabel) return match.dataset.yearLabel;
      return `${minimum || "Any"}–${maximum || "Now"}`;
    };

    const syncControls = () => {
      genreButtons.forEach((button) => {
        button.classList.toggle(
          "is-active",
          selectedGenres.has(button.dataset.filterValue),
        );
      });

      const matchingYearButton = getMatchingYearButton();
      const hasYear = Boolean(yearMinInput?.value || yearMaxInput?.value);
      yearCustomSelected = shouldShowCustomControl({
        hasPresetMatch: Boolean(matchingYearButton),
        selected: yearCustomSelected,
        value: hasYear,
      });
      yearButtons.forEach((button) => {
        const isCustom = button.dataset.yearRange === "custom";
        button.classList.toggle(
          "is-active",
          isCustom
            ? yearCustomSelected
            : !yearCustomSelected && button === matchingYearButton,
        );
      });
      yearCustom?.toggleAttribute("hidden", !yearCustomSelected);
      if (yearCustomSelected) {
        if (yearCustomMin) yearCustomMin.value = yearMinInput?.value || "";
        if (yearCustomMax) yearCustomMax.value = yearMaxInput?.value || "";
      }

      const matchingRuntimeButton = getMatchingRuntimeButton();
      const hasRuntime = Boolean(runtimeInput?.value);
      runtimeCustomSelected = shouldShowCustomControl({
        hasPresetMatch: Boolean(matchingRuntimeButton),
        selected: runtimeCustomSelected,
        value: hasRuntime,
      });
      runtimeButtons.forEach((button) => {
        const isCustom = button.dataset.runtimeMax === "custom";
        button.classList.toggle(
          "is-active",
          isCustom
            ? runtimeCustomSelected
            : !runtimeCustomSelected && button === matchingRuntimeButton,
        );
      });
      runtimeCustom?.toggleAttribute("hidden", !runtimeCustomSelected);
      if (runtimeCustomSelected && runtimeCustomInput) {
        runtimeCustomInput.value = runtimeInput?.value || "";
      }

      presetButtons.forEach((button) => {
        button.classList.toggle(
          "is-active",
          button.dataset.presetName === pendingPresetName,
        );
      });
    };

    const renderSummary = () => {
      const items = buildPendingSummary({
        genres: Array.from(selectedGenres),
        presetName: pendingPresetName,
        runtimeMax: runtimeInput?.value || "",
        yearLabel: getYearLabel(),
      });
      if (summary) {
        summary.replaceChildren(
          ...items.map((item) => {
            const chip = document.createElement("span");
            chip.className = `filters-pending__chip filters-pending__chip--${item.kind}`;
            chip.textContent = item.label;
            return chip;
          }),
        );
      }
      if (summaryEmpty) summaryEmpty.hidden = items.length > 0;
      if (resetButton) {
        resetButton.disabled =
          items.length === 0 && !yearCustomSelected && !runtimeCustomSelected;
      }
      if (applyButton) applyButton.textContent = formatApplyLabel(items.length);
    };

    const syncFilterUi = () => {
      syncControls();
      renderSummary();
    };

    const recordEvent = (eventName, options = {}) => {
      const payload = {
        event_name: eventName,
        page: "library",
        ...options,
      };
      fetch("/ui/events", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(() => {});
    };

    const dialogController = window.VaultDialog?.bind(dialog, {
      bodyClass: "filters-open",
      closeSelector: "[data-filters-close]",
    });

    const openFilters = (event) => {
      if (!dialogController) return;
      syncFilterUi();
      dialogController.open(event?.currentTarget);
    };

    const closeFilters = () => {
      dialogController?.close();
    };

    document
      .querySelector("[data-filters-open]")
      ?.addEventListener("click", openFilters);

    genreButtons.forEach((button) => {
      const value = button.dataset.filterValue;
      button.addEventListener("click", () => {
        if (selectedGenres.has(value)) {
          selectedGenres.delete(value);
        } else {
          selectedGenres.add(value);
        }
        genresInput.value = Array.from(selectedGenres).join(", ");
        clearPendingPreset();
        syncFilterUi();
      });
    });

    yearButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const range = button.dataset.yearRange || "";
        if (range === "custom") {
          yearCustomSelected = true;
          clearPendingPreset();
          syncFilterUi();
          yearCustomMin?.focus();
          return;
        }
        const [minimum = "", maximum = ""] = range.split("-");
        yearMinInput.value = minimum;
        yearMaxInput.value = maximum;
        yearCustomSelected = false;
        clearPendingPreset();
        syncFilterUi();
      });
    });
    yearCustomMin?.addEventListener("input", (event) => {
      yearMinInput.value = event.target.value;
      yearCustomSelected = true;
      clearPendingPreset();
      syncFilterUi();
    });
    yearCustomMax?.addEventListener("input", (event) => {
      yearMaxInput.value = event.target.value;
      yearCustomSelected = true;
      clearPendingPreset();
      syncFilterUi();
    });

    runtimeButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const value = button.dataset.runtimeMax || "";
        if (value === "custom") {
          runtimeCustomSelected = true;
          clearPendingPreset();
          syncFilterUi();
          runtimeCustomInput?.focus();
          return;
        }
        runtimeInput.value = value;
        runtimeCustomSelected = false;
        clearPendingPreset();
        syncFilterUi();
      });
    });
    runtimeCustomInput?.addEventListener("input", (event) => {
      runtimeInput.value = event.target.value;
      runtimeCustomSelected = true;
      clearPendingPreset();
      syncFilterUi();
    });

    presetButtons.forEach((button) => {
      button.addEventListener("click", () => {
        let filters = {};
        try {
          filters = JSON.parse(button.dataset.filters || "{}");
        } catch {
          return;
        }
        selectedGenres.clear();
        (filters.genres || []).forEach((genre) => selectedGenres.add(genre));
        genresInput.value = Array.from(selectedGenres).join(", ");
        yearMinInput.value = filters.year_min || "";
        yearMaxInput.value = filters.year_max || "";
        runtimeInput.value = filters.runtime_max || "";
        if (presetInput) presetInput.value = "";
        pendingPresetName = button.dataset.presetName || "";
        yearCustomSelected = Boolean(
          (yearMinInput.value || yearMaxInput.value) &&
          !getMatchingYearButton(),
        );
        runtimeCustomSelected = Boolean(
          runtimeInput.value && !getMatchingRuntimeButton(),
        );
        if (orderSelect && filters.order_by)
          orderSelect.value = filters.order_by;
        syncFilterUi();
      });
    });

    resetButton?.addEventListener("click", () => {
      selectedGenres.clear();
      if (genresInput) genresInput.value = "";
      if (moodsInput) moodsInput.value = "";
      if (yearMinInput) yearMinInput.value = "";
      if (yearMaxInput) yearMaxInput.value = "";
      if (runtimeInput) runtimeInput.value = "";
      if (presetInput) presetInput.value = "";
      if (yearCustomMin) yearCustomMin.value = "";
      if (yearCustomMax) yearCustomMax.value = "";
      if (runtimeCustomInput) runtimeCustomInput.value = "";
      pendingPresetName = "";
      yearCustomSelected = false;
      runtimeCustomSelected = false;
      syncFilterUi();
    });

    syncFilterUi();

    const currentRecommendationParams = (options) =>
      buildRecommendationParams(
        {
          genres: selectedGenres,
          moodsValue: moodsInput?.value || "",
          runtimeMax: runtimeInput?.value || "",
          yearMax: yearMaxInput?.value || "",
          yearMin: yearMinInput?.value || "",
        },
        options,
      );

    const clearFilter = (key, value) => {
      if (key === "q") {
        window.location.assign(buildClearFilterUrl(window.location.href, "q"));
        return;
      }
      if (key === "preset") {
        if (presetInput) presetInput.value = "";
        window.location.assign(
          buildClearFilterUrl(window.location.href, "preset"),
        );
        return;
      }
      if (key === "genre") {
        selectedGenres.delete(value);
        genresInput.value = Array.from(selectedGenres).join(", ");
      }
      if (key === "mood" && moodsInput) {
        const remainingMoods = parseCsv(moodsInput.value).filter(
          (mood) => mood !== value,
        );
        moodsInput.value = remainingMoods.join(", ");
      }
      if (key === "year") {
        yearMinInput.value = "";
        yearMaxInput.value = "";
      }
      if (key === "runtime") runtimeInput.value = "";
      form?.requestSubmit();
    };
    document.querySelectorAll("[data-clear-filter]").forEach((button) => {
      button.addEventListener("click", () =>
        clearFilter(button.dataset.clearFilter, button.dataset.filterValue),
      );
    });
    document
      .getElementById("clear-active-filters")
      ?.addEventListener("click", () => {
        window.location.assign(buildClearAllFiltersUrl(window.location.href));
      });

    form?.addEventListener("submit", (event) => {
      const searchValue = searchInput?.value.trim() || "";
      const submittedBySearch =
        event.submitter?.id === "search-button" ||
        document.activeElement?.id === "search-q";
      if (
        orderSelect &&
        searchValue &&
        (submittedBySearch || searchValue !== initialSearchValue)
      ) {
        orderSelect.value = "title_asc";
      }
      const hasFilters = Boolean(
        genresInput?.value ||
        moodsInput?.value ||
        yearMinInput?.value ||
        yearMaxInput?.value ||
        runtimeInput?.value ||
        presetInput?.value,
      );
      recordEvent(
        document.getElementById("search-q")?.value
          ? "library_search_submitted"
          : "filters_applied",
        { context: hasFilters ? "filtered" : "all" },
      );
    });

    document.querySelectorAll("[data-view-change]").forEach((link) => {
      link.addEventListener("click", () => {
        recordEvent("view_changed", { context: link.dataset.viewChange });
      });
    });
    document.querySelectorAll("[data-movie-detail-link]").forEach((link) => {
      link.addEventListener("click", () => {
        const card = link.closest("[data-movie-id]");
        recordEvent("movie_details_opened", {
          movie_id: Number(card?.dataset.movieId),
          context: link.dataset.eventContext,
        });
      });
    });

    document.addEventListener("vault:preference-updated", (event) => {
      recordEvent("preference_toggled", {
        movie_id: event.detail.movieId,
        context: event.detail.type,
      });
    });

    const scheduleBusyUpdates = (releaseBusy, params, options = {}) => {
      if (typeof releaseBusy?.update !== "function") return () => {};
      const timers = [
        window.setTimeout(
          () =>
            releaseBusy.update(
              recommendationBusyMessage(params, { ...options, stage: "slow" }),
            ),
          3500,
        ),
        window.setTimeout(
          () =>
            releaseBusy.update(
              recommendationBusyMessage(params, { ...options, stage: "long" }),
            ),
          9000,
        ),
      ];
      return () => timers.forEach((timer) => window.clearTimeout(timer));
    };

    const pickButton = document.getElementById("pick-button");
    pickButton?.addEventListener("click", async () => {
      if (pickButton.disabled) return;
      const params = currentRecommendationParams({ includeRuntime: true });
      const releaseBusy =
        typeof window.setVaultBusy === "function"
          ? window.setVaultBusy(recommendationBusyMessage(params), { delay: 0 })
          : () => {};
      const clearBusyUpdates = scheduleBusyUpdates(releaseBusy, params);
      pickButton.disabled = true;
      pickButton.classList.add("is-busy");
      pickButton.setAttribute("aria-busy", "true");
      pickButton.setAttribute("aria-label", "Choosing a random trusted movie");
      const busyStartedAt = Date.now();
      let navigating = false;
      try {
        recordEvent("random_pick_requested", { context: "toolbar" });
        const response = await fetch(
          buildRecommendationUrl("/movies/picks", params),
        );
        if (response.status === 404) {
          window.showToast?.({
            label: "No match",
            message: "No trusted movie fits those filters yet.",
            tone: "notice",
          });
          return;
        }
        if (!response.ok) {
          window.showToast?.({
            label: "Pick failed",
            message: "The Vault could not choose right now. Try again.",
            tone: "error",
          });
          return;
        }
        const movie = await response.json();
        const remainingBusyTime = 650 - (Date.now() - busyStartedAt);
        if (remainingBusyTime > 0) {
          await new Promise((resolve) =>
            window.setTimeout(resolve, remainingBusyTime),
          );
        }
        navigating = true;
        window.location.href = `/ui/movies/${movie.id}`;
      } catch {
        window.showToast?.({
          label: "Connection issue",
          message: "The Vault could not connect. Try again.",
          tone: "error",
        });
      } finally {
        clearBusyUpdates();
        if (!navigating) {
          releaseBusy();
          pickButton.disabled = false;
          pickButton.classList.remove("is-busy");
          pickButton.removeAttribute("aria-busy");
          pickButton.setAttribute("aria-label", "Random trusted movie");
        }
      }
    });

    const doubleFeatureButton = document.getElementById(
      "double-feature-button",
    );
    const doubleFeatureDialog = document.querySelector(
      "[data-double-feature-dialog]",
    );
    const doubleFeatureController = window.VaultDialog?.bind(
      doubleFeatureDialog,
      { closeSelector: "[data-double-feature-close]" },
    );
    const doubleFeatureSummary = document.querySelector(
      "[data-double-feature-summary]",
    );
    const renderDoubleFeatureMovie = (prefix, movie) => {
      const title = document.querySelector(
        `[data-double-feature-${prefix}-title]`,
      );
      const meta = document.querySelector(
        `[data-double-feature-${prefix}-meta]`,
      );
      const link = document.querySelector(
        `[data-double-feature-${prefix}-link]`,
      );
      if (title) title.textContent = movie?.title || "Untitled";
      const details = [
        movie?.year,
        movie?.runtime ? `${movie.runtime} min` : "",
      ]
        .filter(Boolean)
        .join(" · ");
      if (meta) meta.textContent = details || "Runtime unavailable";
      if (link && movie?.id)
        link.setAttribute("href", `/ui/movies/${movie.id}`);
    };

    doubleFeatureButton?.addEventListener("click", async () => {
      if (doubleFeatureButton.disabled) return;
      const params = currentRecommendationParams({ includeRuntime: false });
      const releaseBusy =
        typeof window.setVaultBusy === "function"
          ? window.setVaultBusy(
              recommendationBusyMessage(params, { kind: "double-feature" }),
              { delay: 0 },
            )
          : () => {};
      const clearBusyUpdates = scheduleBusyUpdates(releaseBusy, params, {
        kind: "double-feature",
      });
      doubleFeatureButton.disabled = true;
      doubleFeatureButton.classList.add("is-busy");
      doubleFeatureButton.setAttribute("aria-busy", "true");
      doubleFeatureButton.setAttribute(
        "aria-label",
        "Choosing a double feature",
      );
      const busyStartedAt = Date.now();
      try {
        recordEvent("double_feature_requested", { context: "toolbar" });
        const response = await fetch(
          buildRecommendationUrl("/movies/double-feature", params),
        );
        if (response.status === 404) {
          window.showToast?.({
            label: "No pairing",
            message: "No double feature fits those filters yet.",
            tone: "notice",
          });
          return;
        }
        if (!response.ok) {
          window.showToast?.({
            label: "Pairing failed",
            message: "The Vault could not pair movies right now. Try again.",
            tone: "error",
          });
          return;
        }
        const pairing = await response.json();
        const remainingBusyTime = 650 - (Date.now() - busyStartedAt);
        if (remainingBusyTime > 0) {
          await new Promise((resolve) =>
            window.setTimeout(resolve, remainingBusyTime),
          );
        }
        renderDoubleFeatureMovie("primary", pairing.primary);
        renderDoubleFeatureMovie("secondary", pairing.secondary);
        if (doubleFeatureSummary) {
          doubleFeatureSummary.textContent = pairing.total_runtime
            ? `Two trusted picks, ${pairing.total_runtime} total.`
            : "Two trusted picks for the same movie night.";
        }
        doubleFeatureController?.open(doubleFeatureButton);
      } catch {
        window.showToast?.({
          label: "Connection issue",
          message: "The Vault could not connect. Try again.",
          tone: "error",
        });
      } finally {
        clearBusyUpdates();
        releaseBusy();
        doubleFeatureButton.disabled = false;
        doubleFeatureButton.classList.remove("is-busy");
        doubleFeatureButton.removeAttribute("aria-busy");
        doubleFeatureButton.setAttribute("aria-label", "Pick a double feature");
      }
    });
  });
})();
