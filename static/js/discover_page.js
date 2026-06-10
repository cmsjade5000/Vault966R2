(function () {
  document.addEventListener("DOMContentLoaded", () => {
    const recordEvent = (eventName, options = {}) => {
      fetch("/ui/events", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          event_name: eventName,
          page: "discover",
          ...options,
        }),
        keepalive: true,
      }).catch(() => {});
    };

    document.querySelectorAll("[data-discover-rail-link]").forEach((link) => {
      link.addEventListener("click", () => {
        recordEvent("discover_rail_opened", {
          context: link.dataset.railKey,
        });
      });
    });
    document.querySelectorAll("[data-movie-detail-link]").forEach((link) => {
      link.addEventListener("click", () => {
        recordEvent("movie_details_opened", {
          movie_id: Number(
            link.dataset.movieId ||
              link.closest("[data-movie-id]")?.dataset.movieId,
          ),
          context: link.dataset.eventContext,
        });
      });
    });

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
        const payload = await response.json();
        const active = type === "like" ? payload.liked : payload.watchlist;
        button.classList.toggle("is-active", Boolean(active));
        button.setAttribute("aria-pressed", active ? "true" : "false");
        const title = button.dataset.movieTitle || "movie";
        if (type === "like") {
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
        recordEvent("preference_toggled", {
          movie_id: movieId,
          context: type,
        });
      } finally {
        button.disabled = false;
      }
    });
  });
})();
