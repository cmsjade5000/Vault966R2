(() => {
  document.addEventListener("DOMContentLoaded", () => {
    const pairingsContainer = document.querySelector("[data-discover-pairings]");
    const genresContainer = document.querySelector("[data-discover-genres]");
    const refreshButtons = Array.from(
      document.querySelectorAll("[data-discover-refresh]"),
    );
    if (!pairingsContainer && !genresContainer) return;

    let isBusy = false;

    const setBusy = (busy) => {
      isBusy = busy;
      refreshButtons.forEach((button) => {
        button.classList.toggle("is-busy", busy);
        button.disabled = busy;
      });
    };

    const buildPosterNode = (movie) => {
      if (movie.poster_url) {
        const img = document.createElement("img");
        img.src = movie.poster_url;
        img.alt = `${movie.title} poster`;
        img.loading = "lazy";
        return img;
      }
      const placeholder = document.createElement("div");
      const theme = movie.poster_theme || "poster-theme-default";
      placeholder.className = `poster poster--empty ${theme}`;
      placeholder.setAttribute("aria-hidden", "true");
      placeholder.textContent = "🍿";
      return placeholder;
    };

    const buildReasons = (reasons) => {
      if (!Array.isArray(reasons) || reasons.length === 0) return null;
      const wrapper = document.createElement("div");
      wrapper.className = "discover-card-reasons";
      reasons.forEach((reason) => {
        const chip = document.createElement("span");
        chip.className = "chip chip-reason";
        chip.textContent = reason;
        wrapper.appendChild(chip);
      });
      return wrapper;
    };

    const buildPreferenceButton = (movie, type, label, active) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `preference-button${active ? " is-active" : ""}`;
      button.setAttribute("data-preference-button", "");
      button.setAttribute("data-preference-type", type);
      button.setAttribute("data-movie-id", movie.id);
      button.setAttribute("aria-pressed", active ? "true" : "false");
      button.textContent = label;
      return button;
    };

    const buildCardActions = (movie) => {
      const actions = document.createElement("div");
      actions.className = "discover-card-actions";
      const label = document.createElement("span");
      label.className = "discover-card-actions__label";
      label.textContent = movie.title;
      actions.appendChild(label);
      const reasons = buildReasons(movie.reasons);
      if (reasons) actions.appendChild(reasons);
      actions.appendChild(
        buildPreferenceButton(movie, "like", "Like", movie.liked),
      );
      actions.appendChild(
        buildPreferenceButton(movie, "watchlist", "Watchlist", movie.watchlist),
      );
      return actions;
    };

    const buildPairingPosterCard = (movie) => {
      const card = document.createElement("div");
      card.className = "discover-pairing__poster-card";
      card.setAttribute("data-movie-card", "");
      card.setAttribute("data-movie-id", movie.id);
      card.dataset.liked = movie.liked ? "true" : "false";
      card.dataset.watchlist = movie.watchlist ? "true" : "false";

      const link = document.createElement("a");
      link.className = "discover-pairing__poster-link";
      link.href = `/ui/movies/${movie.id}`;
      link.setAttribute("aria-label", `View details for ${movie.title}`);
      link.appendChild(buildPosterNode(movie));
      card.appendChild(link);

      card.appendChild(buildCardActions(movie));
      return card;
    };

    const buildPairingCard = (pairing) => {
      const article = document.createElement("article");
      article.className = "discover-pairing";

      const posters = document.createElement("div");
      posters.className = "discover-pairing__posters";
      posters.appendChild(buildPairingPosterCard(pairing.primary));
      posters.appendChild(buildPairingPosterCard(pairing.secondary));
      article.appendChild(posters);

      const meta = document.createElement("div");
      meta.className = "discover-pairing__meta";
      const chip = document.createElement("span");
      chip.className = "chip chip-flic";
      chip.textContent = "Double Feature";
      meta.appendChild(chip);

      const heading = document.createElement("h3");
      heading.textContent = `${pairing.primary.title} + ${pairing.secondary.title}`;
      meta.appendChild(heading);

      const description = document.createElement("p");
      description.textContent =
        pairing.theme_label || "Two picks that travel well together.";
      meta.appendChild(description);

      const pairingReasons = buildReasons(pairing.pairing_reasons);
      if (pairingReasons) {
        pairingReasons.className = "discover-pairing__reasons";
        meta.appendChild(pairingReasons);
      }

      const runtime = document.createElement("div");
      runtime.className = "discover-pairing__runtime";
      runtime.textContent = pairing.total_runtime
        ? `${pairing.total_runtime} total`
        : "Runtime varies";
      meta.appendChild(runtime);

      article.appendChild(meta);
      return article;
    };

    const buildGenreCard = (entry) => {
      const movie = entry.movie;
      const article = document.createElement("article");
      article.className = "discover-genre-card";
      article.setAttribute("role", "listitem");
      article.setAttribute("data-movie-card", "");
      article.setAttribute("data-movie-id", movie.id);
      article.dataset.liked = movie.liked ? "true" : "false";
      article.dataset.watchlist = movie.watchlist ? "true" : "false";

      const link = document.createElement("a");
      link.className = "discover-genre-card__link";
      link.href = `/ui/movies/${movie.id}`;
      link.setAttribute("aria-label", `View details for ${movie.title}`);

      const poster = document.createElement("div");
      poster.className = "discover-genre-card__poster";
      poster.appendChild(buildPosterNode(movie));
      const tag = document.createElement("span");
      tag.className = "discover-genre-card__tag";
      tag.textContent = entry.genre;
      poster.appendChild(tag);
      link.appendChild(poster);

      const meta = document.createElement("div");
      meta.className = "discover-genre-card__meta";
      const title = document.createElement("h3");
      title.textContent = movie.title;
      meta.appendChild(title);
      const year = document.createElement("span");
      year.textContent = movie.year || "—";
      meta.appendChild(year);
      link.appendChild(meta);

      article.appendChild(link);
      article.appendChild(buildCardActions(movie));
      return article;
    };

    const renderPairings = (pairings) => {
      if (!pairingsContainer) return;
      pairingsContainer.replaceChildren();
      if (!Array.isArray(pairings) || pairings.length === 0) {
        const empty = document.createElement("p");
        empty.className = "memory-placeholder";
        empty.textContent = "No pairings ready yet.";
        pairingsContainer.appendChild(empty);
        return;
      }
      pairings.forEach((pairing) => {
        pairingsContainer.appendChild(buildPairingCard(pairing));
      });
    };

    const renderGenres = (entries) => {
      if (!genresContainer) return;
      genresContainer.replaceChildren();
      if (!Array.isArray(entries) || entries.length === 0) {
        const empty = document.createElement("p");
        empty.className = "memory-placeholder";
        empty.textContent = "No genre picks ready yet.";
        genresContainer.appendChild(empty);
        return;
      }
      entries.forEach((entry) => {
        genresContainer.appendChild(buildGenreCard(entry));
      });
    };

    const fetchRefresh = async () => {
      if (isBusy) return;
      setBusy(true);
      try {
        const seed = Math.floor(Date.now() / 1000);
        const url = new URL("/api/discover/refresh", window.location.origin);
        url.searchParams.set("seed", String(seed));
        const response = await fetch(url.toString(), {
          headers: { Accept: "application/json" },
        });
        if (!response.ok) {
          throw new Error("Refresh failed");
        }
        const payload = await response.json();
        if (payload && typeof payload === "object") {
          renderPairings(payload.pairings || []);
          renderGenres(payload.genre_spotlights || []);
        }
      } catch (error) {
        console.warn("Discover refresh failed", error);
        if (typeof window.showToast === "function") {
          window.showToast("Couldn’t refresh picks—try again soon.");
        }
      } finally {
        setBusy(false);
      }
    };

    refreshButtons.forEach((button) => {
      button.addEventListener("click", () => {
        fetchRefresh();
      });
    });

    const ROTATE_MS = 120000;
    setInterval(() => {
      if (document.hidden) return;
      fetchRefresh();
    }, ROTATE_MS);
  });
})();
