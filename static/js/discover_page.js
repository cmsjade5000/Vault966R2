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

  window.VaultDiscoverSupport = {
    calculateRailState,
    getScrollDistance,
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

    const updateRailState = (rail) => {
      const track = rail.querySelector(
        "[data-rail-viewport] .discover-rail__track",
      );
      if (!track) return;

      const previous = rail.querySelector("[data-rail-previous]");
      const next = rail.querySelector("[data-rail-next]");
      const progress = rail.querySelector("[data-rail-progress]");
      const state = calculateRailState(track);

      if (previous) previous.disabled = state.atStart;
      if (next) next.disabled = state.atEnd;
      if (progress) {
        progress.style.transform = `scaleX(${state.progressScale})`;
      }
    };

    document.querySelectorAll("[data-discover-rail]").forEach((rail) => {
      const track = rail.querySelector(
        "[data-rail-viewport] .discover-rail__track",
      );
      if (!track) return;

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
      track.addEventListener("scroll", () => updateRailState(rail), {
        passive: true,
      });
      updateRailState(rail);
    });

    const indexLinks = Array.from(
      document.querySelectorAll(".discover-index a"),
    );
    const sections = indexLinks
      .map((link) => document.querySelector(link.getAttribute("href")))
      .filter(Boolean);
    if ("IntersectionObserver" in window && sections.length) {
      const observer = new IntersectionObserver(
        (entries) => {
          const visible = entries
            .filter((entry) => entry.isIntersecting)
            .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
          if (!visible) return;
          indexLinks.forEach((link) => {
            link.classList.toggle(
              "is-active",
              link.getAttribute("href") === `#${visible.target.id}`,
            );
          });
        },
        { rootMargin: "-20% 0px -65% 0px", threshold: [0.1, 0.4] },
      );
      sections.forEach((section) => observer.observe(section));
    }

    if (document.querySelector("[data-selected-for-you]")) {
      recordEvent("personalized_recommendations_shown", {
        context: "selected_for_you",
      });
    }

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

    document.addEventListener("vault:preference-updated", (event) => {
      recordEvent("preference_toggled", {
        movie_id: event.detail.movieId,
        context: event.detail.type,
      });
    });

    window.addEventListener("resize", () => {
      document
        .querySelectorAll("[data-discover-rail]")
        .forEach(updateRailState);
    });
  });
})();
