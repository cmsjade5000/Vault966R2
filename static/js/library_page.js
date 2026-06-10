(function () {
  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("filters-form");
    const dialog = document.querySelector("[data-filters-dialog]");
    const genresInput = document.getElementById("genres-input");
    const yearMinInput = document.getElementById("year-min-input");
    const yearMaxInput = document.getElementById("year-max-input");
    const runtimeInput = document.getElementById("runtime-max-input");
    const presetInput = document.getElementById("preset-input");
    const selectedGenres = new Set(
      (genresInput?.value || "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean),
    );

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

    const openFilters = () => {
      if (!dialog) return;
      dialog.classList.add("is-open");
      dialog.setAttribute("aria-hidden", "false");
      document.body.classList.add("filters-open");
    };

    const closeFilters = () => {
      if (!dialog) return;
      dialog.classList.remove("is-open");
      dialog.setAttribute("aria-hidden", "true");
      document.body.classList.remove("filters-open");
    };

    document
      .querySelector("[data-filters-open]")
      ?.addEventListener("click", openFilters);
    document
      .querySelector("[data-filters-close]")
      ?.addEventListener("click", closeFilters);
    dialog?.addEventListener("click", (event) => {
      if (event.target === dialog) closeFilters();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeFilters();
    });

    document
      .querySelectorAll('[data-filter-group="genres"] [data-filter-value]')
      .forEach((button) => {
        const value = button.dataset.filterValue;
        button.classList.toggle("is-active", selectedGenres.has(value));
        button.addEventListener("click", () => {
          if (selectedGenres.has(value)) {
            selectedGenres.delete(value);
          } else {
            selectedGenres.add(value);
          }
          genresInput.value = Array.from(selectedGenres).join(", ");
          button.classList.toggle("is-active", selectedGenres.has(value));
          if (presetInput) presetInput.value = "";
        });
      });

    document.querySelectorAll("[data-year-range]").forEach((button) => {
      button.addEventListener("click", () => {
        const range = button.dataset.yearRange || "";
        if (range === "custom") {
          document.getElementById("year-custom")?.removeAttribute("hidden");
          return;
        }
        const [minimum = "", maximum = ""] = range.split("-");
        yearMinInput.value = minimum;
        yearMaxInput.value = maximum;
        if (presetInput) presetInput.value = "";
      });
    });
    document
      .getElementById("year-custom-min")
      ?.addEventListener("input", (event) => {
        yearMinInput.value = event.target.value;
      });
    document
      .getElementById("year-custom-max")
      ?.addEventListener("input", (event) => {
        yearMaxInput.value = event.target.value;
      });

    document.querySelectorAll("[data-runtime-max]").forEach((button) => {
      button.addEventListener("click", () => {
        const value = button.dataset.runtimeMax || "";
        if (value === "custom") {
          document.getElementById("runtime-custom")?.removeAttribute("hidden");
          return;
        }
        runtimeInput.value = value;
        if (presetInput) presetInput.value = "";
      });
    });
    document
      .getElementById("runtime-custom-input")
      ?.addEventListener("input", (event) => {
        runtimeInput.value = event.target.value;
      });

    document
      .querySelectorAll(".chip-preset[data-filters]")
      .forEach((button) => {
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
          const orderSelect = document.getElementById("order-by");
          if (orderSelect && filters.order_by)
            orderSelect.value = filters.order_by;
          form?.requestSubmit();
        });
      });

    const clearFilter = (key, value) => {
      if (key === "q") document.getElementById("search-q").value = "";
      if (key === "preset" && presetInput) presetInput.value = "";
      if (key === "genre") {
        selectedGenres.delete(value);
        genresInput.value = Array.from(selectedGenres).join(", ");
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
        window.location.href = "/ui/movies";
      });

    form?.addEventListener("submit", () => {
      const hasFilters = Boolean(
        genresInput?.value ||
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

    const updatePreferenceButtons = (movieId, payload) => {
      document
        .querySelectorAll(
          `[data-preference-button][data-movie-id="${movieId}"]`,
        )
        .forEach((button) => {
          const active =
            button.dataset.preferenceType === "like"
              ? payload.liked
              : payload.watchlist;
          button.classList.toggle("is-active", Boolean(active));
          button.setAttribute("aria-pressed", active ? "true" : "false");
          const title = button.dataset.movieTitle || "movie";
          if (button.dataset.preferenceType === "like") {
            button.setAttribute(
              "aria-label",
              `${active ? "Unlike" : "Like"} ${title}`,
            );
          } else {
            button.setAttribute(
              "aria-label",
              `${active ? "Remove" : "Add"} ${title} ${
                active ? "from" : "to"
              } watchlist`,
            );
          }
        });
    };
    document.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-preference-button]");
      if (!button) return;
      event.preventDefault();
      const movieId = Number(button.dataset.movieId);
      const type = button.dataset.preferenceType;
      const method = button.classList.contains("is-active") ? "DELETE" : "POST";
      button.disabled = true;
      try {
        const response = await fetch(`/movies/${movieId}/${type}`, {
          method,
          headers: { Accept: "application/json" },
        });
        if (!response.ok) return;
        updatePreferenceButtons(movieId, await response.json());
        recordEvent("preference_toggled", {
          movie_id: movieId,
          context: type,
        });
      } finally {
        button.disabled = false;
      }
    });

    document
      .getElementById("pick-button")
      ?.addEventListener("click", async () => {
        recordEvent("random_pick_requested", { context: "toolbar" });
        const params = new URLSearchParams();
        const firstGenre = selectedGenres.values().next().value;
        if (firstGenre) params.set("genre", firstGenre);
        if (yearMinInput?.value) params.set("year_min", yearMinInput.value);
        if (yearMaxInput?.value) params.set("year_max", yearMaxInput.value);
        if (runtimeInput?.value) params.set("runtime_max", runtimeInput.value);
        const response = await fetch(`/movies/picks?${params.toString()}`);
        if (!response.ok) return;
        const movie = await response.json();
        window.location.href = `/ui/movies/${movie.id}`;
      });
  });
})();
