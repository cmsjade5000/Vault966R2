(function () {
  const buildClearFilterUrl = (href, key) => {
    const url = new URL(href);
    if (key === "q") {
      url.searchParams.delete("q");
    }
    if (key === "preset") {
      url.searchParams.delete("preset");
    }
    url.searchParams.set("_filters", "1");
    url.searchParams.set("page", "1");
    return url.toString();
  };

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

  window.VaultLibrarySupport = {
    buildClearAllFiltersUrl,
    buildClearFilterUrl,
    buildPendingSummary,
    emptyFilterState,
    formatApplyLabel,
    formatPresetName,
    parseCsv,
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
        const orderSelect = document.getElementById("order-by");
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

    form?.addEventListener("submit", () => {
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

    const pickButton = document.getElementById("pick-button");
    pickButton?.addEventListener("click", async () => {
      if (pickButton.disabled) return;
      const releaseBusy =
        typeof window.setVaultBusy === "function"
          ? window.setVaultBusy("Vault is choosing a movie…", { delay: 0 })
          : () => {};
      pickButton.disabled = true;
      pickButton.classList.add("is-busy");
      pickButton.setAttribute("aria-busy", "true");
      pickButton.setAttribute("aria-label", "Choosing a random trusted movie");
      const busyStartedAt = Date.now();
      let navigating = false;
      try {
        recordEvent("random_pick_requested", { context: "toolbar" });
        const params = new URLSearchParams();
        const firstGenre = selectedGenres.values().next().value;
        const firstMood = parseCsv(moodsInput?.value || "")[0];
        if (firstGenre) params.set("genre", firstGenre);
        if (firstMood) params.set("mood", firstMood);
        if (yearMinInput?.value) params.set("year_min", yearMinInput.value);
        if (yearMaxInput?.value) params.set("year_max", yearMaxInput.value);
        if (runtimeInput?.value) params.set("runtime_max", runtimeInput.value);
        const response = await fetch(`/movies/picks?${params.toString()}`);
        if (response.status === 404) {
          window.showToast?.("Nothing matched—try widening the filters.");
          return;
        }
        if (!response.ok) {
          window.showToast?.("The Vault couldn’t choose right now. Try again.");
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
        window.showToast?.("The Vault couldn’t connect. Try again.");
      } finally {
        if (!navigating) {
          releaseBusy();
          pickButton.disabled = false;
          pickButton.classList.remove("is-busy");
          pickButton.removeAttribute("aria-busy");
          pickButton.setAttribute("aria-label", "Random trusted movie");
        }
      }
    });
  });
})();
