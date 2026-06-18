(function () {
  const calculateRailState = ({ clientWidth, scrollLeft, scrollWidth }) => {
    const maxScroll = Math.max(0, scrollWidth - clientWidth);
    const ratio = maxScroll > 0 ? scrollLeft / maxScroll : 0;
    return {
      atEnd: scrollLeft >= maxScroll - 2,
      atStart: scrollLeft <= 2,
      progressScale: Math.max(0.32, 0.32 + ratio * 0.68),
    };
  };

  const getScrollDistance = (clientWidth) => Math.max(clientWidth * 0.78, 240);

  const hydrateDeferredPoster = (image) => {
    const source = image?.dataset?.posterSrc;
    if (!source || image.dataset.posterHydrated === "true") return false;
    image.src = source;
    image.dataset.posterHydrated = "true";
    image.removeAttribute("data-poster-src");
    return true;
  };

  window.VaultDiscoverSupport = {
    calculateRailState,
    getScrollDistance,
    hydrateDeferredPoster,
  };

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

    const onIdle =
      window.requestIdleCallback ||
      ((callback) => window.setTimeout(callback, 1));

    const schedule = (callback) => {
      if (window.requestAnimationFrame) {
        window.requestAnimationFrame(callback);
      } else {
        window.setTimeout(callback, 16);
      }
    };

    const updateRailState = (railState) => {
      const state = calculateRailState(railState.track);

      if (railState.previous) railState.previous.disabled = state.atStart;
      if (railState.next) railState.next.disabled = state.atEnd;
      if (railState.progress) {
        railState.progress.style.transform = `scaleX(${state.progressScale})`;
      }
    };

    const scheduleRailStateUpdate = (railState) => {
      if (railState.pending) return;
      railState.pending = true;
      schedule(() => {
        railState.pending = false;
        updateRailState(railState);
      });
    };

    const setupDeferredPosters = () => {
      const images = Array.from(
        document.querySelectorAll("[data-deferred-poster]"),
      );
      if (!images.length) return;

      if (!("IntersectionObserver" in window)) {
        images.forEach(hydrateDeferredPoster);
        return;
      }

      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            hydrateDeferredPoster(entry.target);
            observer.unobserve(entry.target);
          });
        },
        { rootMargin: "480px 0px" },
      );
      images.forEach((image) => observer.observe(image));
    };

    const railStates = [];

    document.querySelectorAll("[data-discover-rail]").forEach((rail) => {
      const track = rail.querySelector(
        "[data-rail-viewport] .discover-rail__track",
      );
      if (!track) return;

      const railState = {
        track,
        previous: rail.querySelector("[data-rail-previous]"),
        next: rail.querySelector("[data-rail-next]"),
        progress: rail.querySelector("[data-rail-progress]"),
        pending: false,
      };
      railStates.push(railState);

      const scrollRail = (direction) => {
        track.scrollBy({
          left: direction * getScrollDistance(track.clientWidth),
          behavior: window.matchMedia("(prefers-reduced-motion: reduce)")
            .matches
            ? "auto"
            : "smooth",
        });
      };

      rail
        .querySelector("[data-rail-previous]")
        ?.addEventListener("click", () => scrollRail(-1));
      rail
        .querySelector("[data-rail-next]")
        ?.addEventListener("click", () => scrollRail(1));
      track.addEventListener(
        "scroll",
        () => scheduleRailStateUpdate(railState),
        {
          passive: true,
        },
      );
      updateRailState(railState);
    });

    setupDeferredPosters();

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

      const railLink = target.closest("[data-discover-rail-link]");
      if (railLink) {
        recordEvent("discover_rail_opened", {
          context: railLink.dataset.railKey,
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

    let resizePending = false;
    window.addEventListener("resize", () => {
      if (resizePending) return;
      resizePending = true;
      schedule(() => {
        resizePending = false;
        railStates.forEach(updateRailState);
      });
    });
  });
})();
