(function () {
  const revealPosterFallback = (image) => {
    const frame = image?.closest?.("[data-discover-poster-frame]");
    const fallback = frame?.querySelector?.("[data-discover-poster-fallback]");
    if (!frame || !fallback) return false;

    image.hidden = true;
    fallback.hidden = false;
    frame.dataset.posterState = "fallback";
    return true;
  };

  const markPosterLoaded = (image) => {
    const frame = image?.closest?.("[data-discover-poster-frame]");
    if (!frame) return false;
    frame.dataset.posterState = "loaded";
    return true;
  };

  const setupPosterFallbacks = (root) => {
    const images = Array.from(root.querySelectorAll("[data-discover-poster]"));
    images.forEach((image) => {
      image.addEventListener("load", () => markPosterLoaded(image), {
        once: true,
      });
      image.addEventListener("error", () => revealPosterFallback(image), {
        once: true,
      });

      if (image.complete) {
        if (image.naturalWidth > 0) {
          markPosterLoaded(image);
        } else {
          revealPosterFallback(image);
        }
      }
    });
    return images.length;
  };

  window.VaultDiscoverSupport = {
    markPosterLoaded,
    revealPosterFallback,
    setupPosterFallbacks,
  };

  document.addEventListener("DOMContentLoaded", () => {
    setupPosterFallbacks(document);

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

    const onIdle =
      window.requestIdleCallback ||
      ((callback) => window.setTimeout(callback, 32));

    if (document.querySelector("[data-selected-for-you]")) {
      onIdle(() => {
        recordEvent("personalized_recommendations_shown", {
          context: "selected_for_you",
        });
      });
    }

    document.addEventListener("click", (event) => {
      const target = event.target?.closest ? event.target : null;
      if (!target) return;

      const exploreLink = target.closest("[data-discover-rail-link]");
      if (exploreLink) {
        recordEvent("discover_rail_opened", {
          context: exploreLink.dataset.railKey,
        });
      }

      const detailLink = target.closest("[data-movie-detail-link]");
      if (detailLink) {
        recordEvent("movie_details_opened", {
          movie_id: Number(
            detailLink.dataset.movieId ||
              detailLink.closest("[data-movie-id]")?.dataset.movieId,
          ),
          context: detailLink.dataset.eventContext,
        });
      }
    });

    document.addEventListener("vault:preference-updated", (event) => {
      recordEvent("preference_toggled", {
        movie_id: event.detail.movieId,
        context: event.detail.type,
      });
    });
  });
})();
