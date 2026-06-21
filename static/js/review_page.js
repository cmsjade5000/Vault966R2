(function () {
  const readError = async (response) => {
    try {
      const payload = await response.json();
      return payload?.message || payload?.detail || null;
    } catch (error) {
      return null;
    }
  };

  const appendMeta = (container, label, value) => {
    const item = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = `${label}: `;
    item.appendChild(strong);
    item.appendChild(document.createTextNode(value || "Missing"));
    container.appendChild(item);
  };

  const providerLink = (label, href) => {
    const link = document.createElement("a");
    link.className = "research-link";
    link.href = href;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = label;
    return link;
  };

  const providerLabel = (source) => {
    if (source === "omdb") return "OMDb";
    return "TMDB";
  };

  const canApplyCandidate = (candidate) => {
    if (!candidate) return false;
    if (candidate.source === "omdb") return Boolean(candidate.imdb_id);
    return Boolean(candidate.tmdb_id);
  };

  const selectionSource = (candidate) =>
    candidate?.source === "omdb" ? "omdb" : "tmdb";

  const buildApplyPayload = (search, candidate) => ({
    title: search.title,
    year: search.year,
    source: selectionSource(candidate),
    tmdb_id: candidate.tmdb_id || null,
    imdb_id: candidate.imdb_id || null,
  });

  const parseSearchForm = (form) => {
    const data = new FormData(form);
    const title = String(data.get("title") || "").trim();
    const yearText = String(data.get("year") || "").trim();
    const year = yearText ? Number.parseInt(yearText, 10) : null;
    if (!title) {
      throw new Error("Enter a title to search.");
    }
    if (
      year !== null &&
      (!Number.isInteger(year) || year < 1870 || year > 2100)
    ) {
      throw new Error("Year must be between 1870 and 2100, or left blank.");
    }
    return {
      key: `${title}\n${year ?? ""}`,
      title,
      year,
    };
  };

  window.VaultReviewPageSupport = {
    buildApplyPayload,
    canApplyCandidate,
    parseSearchForm,
    providerLabel,
    selectionSource,
  };

  const initFlagMatcher = (root) => {
    const movieId = root.dataset.movieId;
    const form = root.querySelector("[data-flag-match-search]");
    const status = root.querySelector("[data-flag-match-status]");
    const results = root.querySelector("[data-flag-match-results]");
    const submitButton = form?.querySelector('button[type="submit"]');
    if (!movieId || !form || !status || !results || !submitButton) return;

    let currentSearch = null;

    const setPending = (pending) => {
      submitButton.disabled = pending;
      submitButton.toggleAttribute("aria-busy", pending);
    };

    const setStatus = (message, isError = false) => {
      status.textContent = message;
      status.classList.toggle("is-error", isError);
    };

    const buildCandidateDetails = (candidate) => {
      const details = document.createElement("details");
      details.className = "flag-match-card__details";

      const summary = document.createElement("summary");
      summary.textContent = "More details";
      details.appendChild(summary);

      const content = document.createElement("div");
      content.className = "flag-match-card__details-body";

      const ids = document.createElement("div");
      ids.className = "flag-match-card__ids";
      appendMeta(
        ids,
        "TMDB",
        candidate.tmdb_id ? String(candidate.tmdb_id) : "",
      );
      appendMeta(ids, "IMDb", candidate.imdb_id || "");
      content.appendChild(ids);

      if (candidate.runtime || typeof candidate.match_confidence === "number") {
        const secondary = document.createElement("p");
        secondary.className = "flag-match-card__secondary";
        const parts = [];
        if (candidate.runtime) parts.push(`${candidate.runtime} minutes`);
        if (typeof candidate.match_confidence === "number") {
          parts.push(
            `${Math.round(candidate.match_confidence * 100)}% title/year match`,
          );
        }
        secondary.textContent = parts.join(" · ");
        content.appendChild(secondary);
      }

      if (candidate.synopsis) {
        const synopsis = document.createElement("p");
        synopsis.className = "flag-match-card__synopsis";
        synopsis.textContent = candidate.synopsis;
        content.appendChild(synopsis);
      }

      const links = document.createElement("div");
      links.className = "candidate-research-links";
      if (candidate.tmdb_id) {
        links.appendChild(
          providerLink(
            "View on TMDB",
            `https://www.themoviedb.org/movie/${candidate.tmdb_id}`,
          ),
        );
      }
      if (candidate.imdb_id) {
        links.appendChild(
          providerLink(
            "View on IMDb",
            `https://www.imdb.com/title/${candidate.imdb_id}/`,
          ),
        );
      }
      if (links.childElementCount) content.appendChild(links);

      details.appendChild(content);
      return details;
    };

    const renderCandidates = (items) => {
      results.replaceChildren();
      results.hidden = false;

      items.forEach((candidate) => {
        const article = document.createElement("article");
        article.className = "flag-match-card";

        const poster = document.createElement("div");
        poster.className = "flag-match-card__poster";
        if (candidate.poster_url) {
          const image = document.createElement("img");
          image.src = candidate.poster_url;
          image.alt = `${candidate.title || "Movie"} poster`;
          image.loading = "lazy";
          poster.appendChild(image);
        } else {
          poster.textContent = "No poster";
        }

        const body = document.createElement("div");
        body.className = "flag-match-card__body";
        const heading = document.createElement("h4");
        heading.textContent = candidate.title || "Untitled";
        body.appendChild(heading);

        const summary = document.createElement("p");
        summary.className = "flag-match-card__summary";
        const provider = `${providerLabel(candidate.source)} result`;
        const year = candidate.year ? String(candidate.year) : "Year unknown";
        summary.textContent = `${year} · ${provider}`;
        body.appendChild(summary);

        body.appendChild(buildCandidateDetails(candidate));

        const actions = document.createElement("div");
        actions.className = "flag-match-card__actions";
        const choose = document.createElement("button");
        choose.type = "button";
        choose.className = "button-secondary";
        choose.textContent = "Use this match";
        choose.disabled = !canApplyCandidate(candidate);
        choose.addEventListener("click", async () => {
          if (!currentSearch) {
            setStatus(
              "Search again before selecting from edited results.",
              true,
            );
            return;
          }
          if (!canApplyCandidate(candidate)) return;
          const confirmed = window.confirm(
            `Use ${candidate.title || "this movie"} (${candidate.year || "year unknown"}) for this Vault entry?`,
          );
          if (!confirmed) return;

          choose.disabled = true;
          choose.setAttribute("aria-busy", "true");
          setStatus("Applying the selected match…");
          try {
            const response = await fetch(
              `/ui/movies/health/review/${movieId}/matches/apply`,
              {
                method: "POST",
                headers: {
                  Accept: "application/json",
                  "Content-Type": "application/json",
                },
                body: JSON.stringify(
                  buildApplyPayload(currentSearch, candidate),
                ),
              },
            );
            if (!response.ok) {
              const detail = await readError(response);
              throw new Error(
                detail || `Could not apply match (${response.status})`,
              );
            }
            const payload = await response.json();
            window.persistToastMessage?.(payload.message || "Movie matched.");
            window.location.assign(
              "/ui/movies/health?view=flags#review-workbench",
            );
          } catch (error) {
            setStatus(error.message || "Could not apply that match.", true);
            choose.disabled = false;
            choose.removeAttribute("aria-busy");
          }
        });
        actions.appendChild(choose);
        article.appendChild(poster);
        article.appendChild(body);
        article.appendChild(actions);
        results.appendChild(article);
      });
    };

    const search = async () => {
      let searchState;
      try {
        searchState = parseSearchForm(form);
      } catch (error) {
        setStatus(error.message, true);
        return;
      }

      currentSearch = searchState;
      submitButton.textContent = "Search again";
      const { title, year } = searchState;
      const params = new URLSearchParams({ title });
      if (year !== null) params.set("year", String(year));
      setPending(true);
      setStatus("Searching TMDB and OMDb...");
      results.hidden = true;
      results.replaceChildren();

      try {
        const response = await fetch(
          `/ui/movies/health/review/${movieId}/matches?${params}`,
          { headers: { Accept: "application/json" } },
        );
        if (!response.ok) {
          const detail = await readError(response);
          throw new Error(detail || `Lookup failed (${response.status})`);
        }
        const payload = await response.json();
        const items = Array.isArray(payload.items) ? payload.items : [];
        if (!items.length) {
          setStatus(
            "No matches found. Change the title or remove the year.",
            true,
          );
          return;
        }
        renderCandidates(items);
        setStatus(
          `${items.length} option${items.length === 1 ? "" : "s"} found. Review before selecting.`,
        );
      } catch (error) {
        setStatus(error.message || "Lookup failed. Try again.", true);
      } finally {
        setPending(false);
      }
    };

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      search();
    });

    form.addEventListener("input", () => {
      if (!currentSearch) return;
      try {
        const nextSearch = parseSearchForm(form);
        if (nextSearch.key === currentSearch.key) return;
      } catch (error) {
        // The submit handler will show validation once the user retries.
      }
      currentSearch = null;
      submitButton.textContent = "Search matches";
      setStatus("Search again to refresh candidates before selecting.");
    });

    if (form.dataset.autoSearch === "true") {
      try {
        parseSearchForm(form);
        search();
      } catch (error) {
        setStatus("Enter a title to search.", true);
      }
    }
  };

  document.querySelectorAll("[data-flag-match]").forEach(initFlagMatcher);

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-confirm]");
    if (!button) return;
    if (!window.confirm(button.dataset.confirm)) {
      event.preventDefault();
    }
  });
})();
